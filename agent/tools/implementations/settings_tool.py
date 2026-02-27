"""
P1-28: Settings Tool

Provides device settings management via ADB shell commands.
Controls WiFi, Bluetooth, brightness, volume, DND, battery info, and flashlight.

Uses Android settings provider and sysfs paths where available.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from agent.android.adb_bridge import ADBBridge

logger = logging.getLogger(__name__)


@dataclass
class DeviceStatus:
    """Snapshot of current device settings state."""

    wifi_enabled: bool
    bluetooth_enabled: bool
    brightness: int          # 0-255
    volume_media: int        # 0-15
    volume_ring: int         # 0-7
    dnd_enabled: bool
    battery_level: int       # 0-100
    battery_charging: bool
    airplane_mode: bool
    screen_timeout_ms: int
    screen_orientation: str  # "portrait" or "landscape"
    data_enabled: bool

    def __str__(self) -> str:
        wifi = "On" if self.wifi_enabled else "Off"
        bt = "On" if self.bluetooth_enabled else "Off"
        return (
            f"Battery: {self.battery_level}% | "
            f"WiFi: {wifi} | BT: {bt} | "
            f"Brightness: {self.brightness}/255 | "
            f"Vol: {self.volume_media}/15"
        )


class SettingsTool:
    """
    Device settings control tool using ADB shell commands.

    Usage:
        settings = SettingsTool(adb_bridge)
        settings.set_wifi(True)
        settings.set_brightness(200)
        battery = settings.get_battery_level()
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the SettingsTool.

        Args:
            adb: ADBBridge instance.
        """
        self.adb = adb

    # ------------------------------------------------------------------
    # WiFi
    # ------------------------------------------------------------------

    def set_wifi(self, enabled: bool) -> bool:
        """
        Enable or disable WiFi.

        Args:
            enabled: True to enable, False to disable.

        Returns:
            True if command was sent successfully.
        """
        try:
            state = "enable" if enabled else "disable"
            self.adb._shell(f"svc wifi {state}")
            logger.info("WiFi: %s", state)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set WiFi: %s", e)
            return False

    def get_wifi_state(self) -> bool:
        """Return True if WiFi is currently enabled."""
        try:
            output = self.adb._shell("settings get global wifi_on")
            return output.strip() == "1"
        except ADBBridge.ADBError:
            return False

    def get_wifi_ssid(self) -> str:
        """Return the current WiFi SSID, or empty string if not connected."""
        try:
            output = self.adb._shell("dumpsys wifi | grep 'SSID' | head -2")
            match = re.search(r'SSID: "([^"]+)"', output)
            return match.group(1) if match else ""
        except ADBBridge.ADBError:
            return ""

    # ------------------------------------------------------------------
    # Bluetooth
    # ------------------------------------------------------------------

    def set_bluetooth(self, enabled: bool) -> bool:
        """
        Enable or disable Bluetooth.

        Args:
            enabled: True to enable, False to disable.

        Returns:
            True if command was sent.
        """
        try:
            state = "enable" if enabled else "disable"
            self.adb._shell(f"svc bluetooth {state}")
            logger.info("Bluetooth: %s", state)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set Bluetooth: %s", e)
            return False

    def get_bluetooth_state(self) -> bool:
        """Return True if Bluetooth is enabled."""
        try:
            output = self.adb._shell("settings get global bluetooth_on")
            return output.strip() == "1"
        except ADBBridge.ADBError:
            return False

    # ------------------------------------------------------------------
    # Brightness
    # ------------------------------------------------------------------

    def set_brightness(self, level: int, auto: bool = False) -> bool:
        """
        Set screen brightness.

        Args:
            level: Brightness level (0-255).
            auto: If True, enable auto-brightness.

        Returns:
            True if brightness was set.
        """
        try:
            if auto:
                self.adb._shell("settings put system screen_brightness_mode 1")
                logger.info("Auto-brightness enabled")
            else:
                level = max(0, min(255, level))
                self.adb._shell("settings put system screen_brightness_mode 0")
                self.adb._shell(f"settings put system screen_brightness {level}")
                logger.info("Brightness set to %d/255", level)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set brightness: %s", e)
            return False

    def get_brightness(self) -> int:
        """Return current brightness level (0-255)."""
        try:
            output = self.adb._shell("settings get system screen_brightness")
            return int(output.strip())
        except (ADBBridge.ADBError, ValueError):
            return -1

    def set_brightness_percent(self, percent: int) -> bool:
        """Set brightness as a percentage (0-100)."""
        return self.set_brightness(int(percent * 255 / 100))

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_volume(
        self,
        level: int,
        stream: str = "media",
    ) -> bool:
        """
        Set audio volume.

        Args:
            level: Volume level (0-100 as percentage).
            stream: Audio stream type ("media", "ring", "alarm", "notification").

        Returns:
            True if volume was set.
        """
        stream_ids = {
            "music": 3,
            "media": 3,
            "ring": 2,
            "alarm": 4,
            "notification": 5,
            "call": 0,
        }
        stream_id = stream_ids.get(stream.lower(), 3)

        try:
            # Get max volume for this stream
            output = self.adb._shell(
                f"media volume --get --stream {stream_id} 2>/dev/null || echo 'max=15'"
            )
            max_vol = 15
            match = re.search(r"max=(\d+)", output)
            if match:
                max_vol = int(match.group(1))

            target = int(level * max_vol / 100)
            self.adb._shell(f"media volume --set {target} --stream {stream_id}")
            logger.info("Volume (%s) set to %d%% (%d/%d)", stream, level, target, max_vol)
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to set volume: %s", e)
            return False

    # ------------------------------------------------------------------
    # Do Not Disturb
    # ------------------------------------------------------------------

    def set_dnd(self, enabled: bool) -> bool:
        """
        Enable or disable Do Not Disturb mode.

        Args:
            enabled: True to enable DND, False to disable.

        Returns:
            True if DND mode was changed.
        """
        try:
            if enabled:
                # DND mode: 2=all, 1=priority, 0=off (requires MANAGE_NOTIFICATIONS)
                self.adb._shell(
                    "cmd notification set_dnd on 2>/dev/null || "
                    "settings put global zen_mode 1"
                )
                logger.info("DND enabled")
            else:
                self.adb._shell(
                    "cmd notification set_dnd off 2>/dev/null || "
                    "settings put global zen_mode 0"
                )
                logger.info("DND disabled")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set DND: %s", e)
            return False

    def get_dnd_state(self) -> bool:
        """Return True if DND is enabled."""
        try:
            output = self.adb._shell("settings get global zen_mode")
            return output.strip() not in ("0", "null", "")
        except ADBBridge.ADBError:
            return False

    # ------------------------------------------------------------------
    # Battery
    # ------------------------------------------------------------------

    def get_battery_level(self) -> int:
        """
        Get current battery percentage.

        Returns:
            Battery level 0-100, or -1 on error.
        """
        try:
            output = self.adb._shell("dumpsys battery | grep -E 'level:' | head -1")
            match = re.search(r"level:\s*(\d+)", output)
            if match:
                return int(match.group(1))
            return -1
        except ADBBridge.ADBError:
            return -1

    def get_battery_info(self) -> dict[str, str]:
        """
        Get detailed battery information.

        Returns:
            Dict with keys: level, status, plugged, health, temperature.
        """
        try:
            output = self.adb._shell("dumpsys battery")
            info: dict[str, str] = {}

            for line in output.splitlines():
                line = line.strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    info[key.strip()] = val.strip()

            return {
                "level": info.get("level", "unknown"),
                "status": self._battery_status(info.get("status", "0")),
                "plugged": self._plugged_type(info.get("plugged", "0")),
                "health": self._battery_health(info.get("health", "0")),
                "temperature": f"{float(info.get('temperature', 0)) / 10:.1f}°C",
                "voltage": f"{int(info.get('voltage', 0)) / 1000:.2f}V",
            }

        except ADBBridge.ADBError as e:
            logger.error("Failed to get battery info: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Flashlight
    # ------------------------------------------------------------------

    def toggle_flashlight(self, on: Optional[bool] = None) -> bool:
        """
        Toggle or set the device flashlight (torch).

        Args:
            on: True to turn on, False to turn off, None to toggle.

        Returns:
            True if command was sent.
        """
        try:
            if on is True:
                self.adb._shell(
                    "cmd hardware_properties on-camera-torch 2>/dev/null || "
                    "am broadcast -a com.aria.TORCH_ON"
                )
            elif on is False:
                self.adb._shell(
                    "cmd hardware_properties off-camera-torch 2>/dev/null || "
                    "am broadcast -a com.aria.TORCH_OFF"
                )
            else:
                # Toggle: use quick settings tile
                self.adb._shell(
                    "cmd statusbar expand-quick-settings && sleep 0.3 || true"
                )
                # Try to find and click Flashlight tile
                from agent.android.screen_reader import ScreenReader
                reader = ScreenReader(self.adb)
                matches = reader.find_text_on_screen("Flashlight")
                if matches:
                    x, y = matches[0].center()
                    self.adb.tap(x, y)
                    import time
                    time.sleep(0.2)
                    self.adb._shell("cmd statusbar collapse")

            logger.info("Flashlight toggled")
            return True

        except ADBBridge.ADBError as e:
            logger.error("Failed to toggle flashlight: %s", e)
            return False

    # ------------------------------------------------------------------
    # Airplane mode
    # ------------------------------------------------------------------

    def set_airplane_mode(self, enabled: bool) -> bool:
        """
        Enable or disable airplane mode.

        Note: On Android 4.2+, airplane mode requires root or special permission.

        Args:
            enabled: True to enable, False to disable.

        Returns:
            True if mode was changed.
        """
        try:
            val = 1 if enabled else 0
            self.adb._shell(
                f"settings put global airplane_mode_on {val} && "
                f"am broadcast -a android.intent.action.AIRPLANE_MODE"
            )
            logger.info("Airplane mode: %s", "on" if enabled else "off")
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set airplane mode: %s", e)
            return False

    # ------------------------------------------------------------------
    # Screen
    # ------------------------------------------------------------------

    def set_screen_timeout(self, seconds: int) -> bool:
        """
        Set screen timeout duration.

        Args:
            seconds: Timeout in seconds (e.g., 30, 60, 300).

        Returns:
            True if set successfully.
        """
        try:
            ms = seconds * 1000
            self.adb._shell(f"settings put system screen_off_timeout {ms}")
            logger.info("Screen timeout: %ds", seconds)
            return True
        except ADBBridge.ADBError as e:
            logger.error("Failed to set screen timeout: %s", e)
            return False

    def wake_screen(self) -> bool:
        """Wake the device screen."""
        try:
            self.adb.press_key(26)  # POWER
            return True
        except ADBBridge.ADBError:
            return False

    def lock_screen(self) -> bool:
        """Lock the device screen."""
        try:
            self.adb.press_key(26)  # POWER
            return True
        except ADBBridge.ADBError:
            return False

    def get_device_status(self) -> DeviceStatus:
        """
        Get a comprehensive snapshot of device settings.

        Returns:
            DeviceStatus dataclass with all current settings.
        """
        try:
            # Get all at once via batch dumpsys
            battery_output = self.adb._shell("dumpsys battery")
            wifi_val = self.adb._shell("settings get global wifi_on").strip()
            bt_val = self.adb._shell("settings get global bluetooth_on").strip()
            brightness_val = self.adb._shell("settings get system screen_brightness").strip()
            zen_val = self.adb._shell("settings get global zen_mode").strip()
            airplane_val = self.adb._shell("settings get global airplane_mode_on").strip()
            timeout_val = self.adb._shell("settings get system screen_off_timeout").strip()

            # Parse battery
            batt_level = 0
            batt_charging = False
            for line in battery_output.splitlines():
                line = line.strip()
                if "level:" in line:
                    m = re.search(r"level:\s*(\d+)", line)
                    if m:
                        batt_level = int(m.group(1))
                if "status:" in line:
                    m = re.search(r"status:\s*(\d+)", line)
                    if m:
                        batt_charging = int(m.group(1)) == 2  # 2 = CHARGING

            return DeviceStatus(
                wifi_enabled=wifi_val == "1",
                bluetooth_enabled=bt_val == "1",
                brightness=int(brightness_val) if brightness_val.isdigit() else 128,
                volume_media=0,
                volume_ring=0,
                dnd_enabled=zen_val not in ("0", "null", ""),
                battery_level=batt_level,
                battery_charging=batt_charging,
                airplane_mode=airplane_val == "1",
                screen_timeout_ms=int(timeout_val) if timeout_val.isdigit() else 60000,
                screen_orientation="portrait",
                data_enabled=True,
            )

        except ADBBridge.ADBError as e:
            logger.error("Failed to get device status: %s", e)
            return DeviceStatus(
                wifi_enabled=False, bluetooth_enabled=False, brightness=128,
                volume_media=8, volume_ring=4, dnd_enabled=False,
                battery_level=-1, battery_charging=False, airplane_mode=False,
                screen_timeout_ms=60000, screen_orientation="portrait",
                data_enabled=True,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _battery_status(self, code: str) -> str:
        statuses = {
            "1": "unknown", "2": "charging", "3": "discharging",
            "4": "not_charging", "5": "full",
        }
        return statuses.get(code, "unknown")

    def _plugged_type(self, code: str) -> str:
        types = {"0": "unplugged", "1": "AC", "2": "USB", "4": "wireless"}
        return types.get(code, "unknown")

    def _battery_health(self, code: str) -> str:
        health = {
            "1": "unknown", "2": "good", "3": "overheat",
            "4": "dead", "5": "overvoltage", "6": "unspecified_failure",
            "7": "cold",
        }
        return health.get(code, "unknown")
