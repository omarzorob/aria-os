"""
P2-8: Aria ADB Session Manager

High-level ADB device manager that handles device discovery, connect/disconnect
lifecycle, multi-device support, auto-reconnection, and event hooks.

Usage:
    manager = ADBManager()
    manager.on_connect(lambda dev: print(f"Connected: {dev.model}"))
    manager.auto_reconnect()
    device = manager.get_device()  # Returns an ADBBridge instance
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

# How often auto_reconnect checks the device status (seconds)
DEFAULT_RECONNECT_INTERVAL = 5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DeviceInfo:
    """Metadata about a connected ADB device."""

    serial: str
    model: str = "unknown"
    android_version: str = "unknown"
    is_authorized: bool = False
    is_online: bool = False
    manufacturer: str = "unknown"
    sdk_version: str = "unknown"

    def __str__(self) -> str:
        status = "online" if self.is_online else "offline"
        auth = "authorized" if self.is_authorized else "unauthorized"
        return f"{self.serial} ({self.model}, Android {self.android_version}, {status}, {auth})"


# ---------------------------------------------------------------------------
# ADB Manager
# ---------------------------------------------------------------------------


class ADBManager:
    """
    High-level ADB device session manager.

    Manages device discovery, selection, and lifecycle events.
    Provides a single point of access to the active ADBBridge instance.
    """

    class NoDeviceError(Exception):
        """Raised when no authorized Android device is available."""
        pass

    def __init__(self, adb_path: str = "adb") -> None:
        """
        Initialize the ADB manager.

        Args:
            adb_path: Path to the adb binary (default: "adb" from PATH).
        """
        self._adb_path = adb_path
        self._active_serial: Optional[str] = None
        self._bridge: Optional[ADBBridge] = None

        # Event hooks
        self._connect_callbacks: list[Callable[[DeviceInfo], None]] = []
        self._disconnect_callbacks: list[Callable[[DeviceInfo], None]] = []

        # Auto-reconnect thread
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_running = False
        self._last_known_devices: list[str] = []

        logger.info("ADBManager initialized (adb=%s)", adb_path)

    # ------------------------------------------------------------------
    # Device access
    # ------------------------------------------------------------------

    def get_device(self) -> ADBBridge:
        """
        Return an ADBBridge for the currently active device.

        If a device is already selected, returns the cached bridge.
        Otherwise auto-selects the first available authorized device.

        Returns:
            ADBBridge instance for the active device.

        Raises:
            NoDeviceError: If no authorized device is connected.
        """
        if self._bridge and self._active_serial:
            bridge = ADBBridge(
                adb_path=self._adb_path,
                device_serial=self._active_serial,
            )
            if bridge.is_device_connected():
                return bridge

        # Auto-select
        devices = self.list_devices()
        authorized = [d for d in devices if d.is_authorized and d.is_online]
        if not authorized:
            raise self.NoDeviceError(
                "No authorized Android device connected. "
                "Connect a device with USB debugging enabled or run: adb connect <ip>"
            )

        # Prefer previously selected device
        if self._active_serial:
            preferred = next((d for d in authorized if d.serial == self._active_serial), None)
            if preferred:
                device = preferred
            else:
                device = authorized[0]
        else:
            device = authorized[0]

        self._active_serial = device.serial
        self._bridge = ADBBridge(
            adb_path=self._adb_path,
            device_serial=device.serial,
        )
        logger.info("Active device: %s", device)
        return self._bridge

    def list_devices(self) -> list[DeviceInfo]:
        """
        List all currently connected ADB devices.

        Returns:
            List of DeviceInfo objects for every detected device.
        """
        try:
            result = subprocess.run(
                [self._adb_path, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            logger.error("adb binary not found at '%s'", self._adb_path)
            return []
        except subprocess.TimeoutExpired:
            logger.error("adb devices timed out")
            return []

        devices: list[DeviceInfo] = []
        lines = result.stdout.strip().splitlines()

        for line in lines[1:]:  # Skip "List of devices attached" header
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            status = parts[1]

            is_online = status == "device"
            is_authorized = status == "device"
            # "unauthorized" means USB debugging needs to be accepted on the device

            info = DeviceInfo(
                serial=serial,
                is_online=is_online,
                is_authorized=is_authorized,
            )

            # Get detailed info only for online devices
            if is_online:
                info = self._enrich_device_info(info)

            devices.append(info)

        return devices

    def select_device(self, serial: str) -> None:
        """
        Set the active device by serial number.

        Args:
            serial: ADB device serial (e.g., "emulator-5554" or "192.168.1.100:5555").

        Raises:
            ValueError: If the serial is not found in the connected device list.
        """
        devices = self.list_devices()
        device = next((d for d in devices if d.serial == serial), None)

        if device is None:
            available = [d.serial for d in devices]
            raise ValueError(
                f"Device '{serial}' not found. Available: {available}"
            )

        self._active_serial = serial
        self._bridge = ADBBridge(adb_path=self._adb_path, device_serial=serial)
        logger.info("Selected device: %s", device)

    # ------------------------------------------------------------------
    # Auto-reconnect
    # ------------------------------------------------------------------

    def auto_reconnect(self, interval: int = DEFAULT_RECONNECT_INTERVAL) -> None:
        """
        Start a background thread that monitors device connectivity.

        Fires on_connect / on_disconnect callbacks when devices appear
        or disappear. Attempts to re-establish the active device connection.

        Args:
            interval: Polling interval in seconds (default: 5).
        """
        if self._reconnect_running:
            logger.debug("auto_reconnect already running")
            return

        self._reconnect_running = True
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            args=(interval,),
            daemon=True,
            name="aria-adb-reconnect",
        )
        self._reconnect_thread.start()
        logger.info("ADB auto-reconnect started (interval=%ds)", interval)

    def stop_auto_reconnect(self) -> None:
        """Stop the auto-reconnect background thread."""
        self._reconnect_running = False
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=10)
        logger.info("ADB auto-reconnect stopped")

    def _reconnect_loop(self, interval: int) -> None:
        """Background loop that detects connect/disconnect events."""
        logger.debug("ADB reconnect loop started")
        while self._reconnect_running:
            try:
                devices = self.list_devices()
                current_serials = {d.serial for d in devices if d.is_online}
                last_serials = set(self._last_known_devices)

                # Newly connected
                for serial in current_serials - last_serials:
                    device = next((d for d in devices if d.serial == serial), None)
                    if device:
                        logger.info("Device connected: %s", device)
                        for cb in self._connect_callbacks:
                            try:
                                cb(device)
                            except Exception as e:
                                logger.warning("on_connect callback error: %s", e)

                # Disconnected
                for serial in last_serials - current_serials:
                    logger.warning("Device disconnected: %s", serial)
                    device = DeviceInfo(serial=serial, is_online=False)
                    for cb in self._disconnect_callbacks:
                        try:
                            cb(device)
                        except Exception as e:
                            logger.warning("on_disconnect callback error: %s", e)

                    # Clear cached bridge if it was for the disconnected device
                    if serial == self._active_serial:
                        self._bridge = None
                        logger.info("Active device bridge cleared for %s", serial)

                self._last_known_devices = list(current_serials)

            except Exception as exc:
                logger.debug("Reconnect loop error (non-fatal): %s", exc)

            time.sleep(interval)

        logger.debug("ADB reconnect loop stopped")

    # ------------------------------------------------------------------
    # Event hooks
    # ------------------------------------------------------------------

    def on_connect(self, callback: Callable[[DeviceInfo], None]) -> None:
        """
        Register a callback fired when a new device connects.

        Args:
            callback: Function receiving a DeviceInfo argument.
        """
        self._connect_callbacks.append(callback)

    def on_disconnect(self, callback: Callable[[DeviceInfo], None]) -> None:
        """
        Register a callback fired when a device disconnects.

        Args:
            callback: Function receiving a DeviceInfo argument.
        """
        self._disconnect_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _enrich_device_info(self, info: DeviceInfo) -> DeviceInfo:
        """
        Fetch detailed device properties from the connected device.

        Args:
            info: Partially-populated DeviceInfo.

        Returns:
            Updated DeviceInfo with model, version, etc.
        """
        try:
            bridge = ADBBridge(
                adb_path=self._adb_path,
                device_serial=info.serial,
            )
            props = bridge.get_device_info()
            info.model = props.get("model", "unknown")
            info.android_version = props.get("android_version", "unknown")
            info.manufacturer = props.get("manufacturer", "unknown")
            info.sdk_version = props.get("sdk_version", "unknown")
        except Exception as exc:
            logger.debug("Could not fetch device info for %s: %s", info.serial, exc)
        return info

    def __repr__(self) -> str:
        return (
            f"ADBManager(active={self._active_serial}, "
            f"reconnect={self._reconnect_running})"
        )
