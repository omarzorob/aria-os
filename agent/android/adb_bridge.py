"""
P1-11: ADB Bridge

Full Android Debug Bridge (ADB) wrapper providing high-level methods for
device interaction. Requires `adb` in PATH and a connected Android device
with USB debugging enabled (or ADB over WiFi).
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_ADB = "adb"
DEFAULT_TIMEOUT = 30


class ADBBridge:
    """
    High-level ADB bridge for Aria OS Android control.

    All methods raise ADBError on failure unless otherwise noted.

    Usage:
        adb = ADBBridge()
        if adb.is_device_connected():
            adb.tap(500, 500)
            adb.type_text("Hello from Aria!")
    """

    class ADBError(Exception):
        """Raised when an ADB command fails."""
        pass

    def __init__(
        self,
        adb_path: str = DEFAULT_ADB,
        device_serial: Optional[str] = None,
        default_timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the ADB bridge.

        Args:
            adb_path: Path to the adb binary (default: "adb" from PATH).
            device_serial: Target device serial (for multi-device setups).
            default_timeout: Default command timeout in seconds.
        """
        self.adb_path = adb_path
        self.device_serial = device_serial
        self.default_timeout = default_timeout

    # ------------------------------------------------------------------
    # Core command execution
    # ------------------------------------------------------------------

    def run_command(
        self,
        cmd: str | list[str],
        timeout: Optional[int] = None,
        shell_mode: bool = False,
    ) -> str:
        """
        Run an ADB command and return stdout.

        Args:
            cmd: Command string (e.g., "shell ls") or list of args.
            timeout: Override default timeout.
            shell_mode: If True, run via shell (allows pipes/redirects).

        Returns:
            stdout as string (stripped).

        Raises:
            ADBError: If the command fails or times out.
        """
        timeout = timeout or self.default_timeout

        if isinstance(cmd, str):
            args = cmd.split()
        else:
            args = list(cmd)

        # Build full adb command
        full_cmd = [self.adb_path]
        if self.device_serial:
            full_cmd += ["-s", self.device_serial]
        full_cmd += args

        logger.debug("ADB: %s", " ".join(full_cmd))

        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and result.stderr.strip():
                # Some adb commands return non-zero but still work
                stderr = result.stderr.strip()
                if "error:" in stderr.lower() or "failed" in stderr.lower():
                    raise self.ADBError(
                        f"ADB command failed: {' '.join(args)}\n{stderr}"
                    )
            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise self.ADBError(f"ADB command timed out after {timeout}s: {args}")
        except FileNotFoundError:
            raise self.ADBError(
                f"ADB binary not found at '{self.adb_path}'. "
                "Install Android SDK Platform Tools."
            )

    def _shell(self, shell_cmd: str, timeout: Optional[int] = None) -> str:
        """Run `adb shell <cmd>` and return output."""
        return self.run_command(["shell", shell_cmd], timeout=timeout)

    # ------------------------------------------------------------------
    # Touch / input
    # ------------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        """
        Simulate a tap at the given screen coordinates.

        Args:
            x: X coordinate in pixels.
            y: Y coordinate in pixels.
        """
        self._shell(f"input tap {x} {y}")
        logger.debug("Tapped (%d, %d)", x, y)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int = 300,
    ) -> None:
        """
        Simulate a swipe gesture.

        Args:
            x1: Start X coordinate.
            y1: Start Y coordinate.
            x2: End X coordinate.
            y2: End Y coordinate.
            duration: Duration in milliseconds.
        """
        self._shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
        logger.debug("Swipe (%d,%d) → (%d,%d) [%dms]", x1, y1, x2, y2, duration)

    def type_text(self, text: str) -> None:
        """
        Type text via ADB input (handles spaces via escape).

        Args:
            text: Text to type. Spaces are converted to %s.
        """
        # Escape special characters for adb input text
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        self._shell(f'input text "{escaped}"')
        logger.debug("Typed text (len=%d)", len(text))

    def press_key(self, keycode: int | str) -> None:
        """
        Press an Android keycode.

        Args:
            keycode: Integer keycode or named keycode string
                     (e.g., 4 or "KEYCODE_BACK").

        Common keycodes:
            3  = HOME
            4  = BACK
            24 = VOLUME_UP
            25 = VOLUME_DOWN
            26 = POWER
            66 = ENTER
            82 = MENU
        """
        if isinstance(keycode, int):
            self._shell(f"input keyevent {keycode}")
        else:
            key_str = keycode if keycode.startswith("KEYCODE_") else f"KEYCODE_{keycode}"
            self._shell(f"input keyevent {key_str}")
        logger.debug("Pressed key: %s", keycode)

    # ------------------------------------------------------------------
    # Screen
    # ------------------------------------------------------------------

    def take_screenshot(self, local_path: Optional[str] = None) -> str:
        """
        Capture a screenshot from the device.

        Args:
            local_path: Where to save the screenshot locally.
                        If None, saves to a temp file.

        Returns:
            Local path to the saved screenshot PNG.
        """
        remote_path = "/sdcard/aria_screenshot.png"
        self._shell(f"screencap -p {remote_path}")

        if local_path is None:
            fd, local_path = tempfile.mkstemp(suffix=".png", prefix="aria_screenshot_")
            os.close(fd)

        self.pull_file(remote_path, local_path)
        self._shell(f"rm -f {remote_path}")
        logger.debug("Screenshot saved to: %s", local_path)
        return local_path

    def get_screen_size(self) -> tuple[int, int]:
        """
        Get the screen resolution.

        Returns:
            Tuple of (width, height) in pixels.
        """
        output = self._shell("wm size")
        # Output: "Physical size: 1080x2340" or "Override size: ..."
        for line in output.splitlines():
            if "size:" in line.lower():
                parts = line.split(":")[-1].strip().split("x")
                if len(parts) == 2:
                    return int(parts[0]), int(parts[1])
        raise self.ADBError(f"Could not parse screen size from: {output}")

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    def install_apk(self, path: str, replace: bool = True) -> str:
        """
        Install an APK on the device.

        Args:
            path: Local path to the APK file.
            replace: If True, use -r flag to replace existing install.

        Returns:
            ADB output string.
        """
        flags = ["-r"] if replace else []
        args = ["install"] + flags + [path]
        output = self.run_command(args)
        logger.info("Installed APK: %s → %s", path, output)
        return output

    def pull_file(self, remote: str, local: str) -> str:
        """
        Pull a file from the device to the local machine.

        Args:
            remote: Remote path on device.
            local: Local destination path.

        Returns:
            ADB output string.
        """
        output = self.run_command(["pull", remote, local])
        logger.debug("Pulled %s → %s", remote, local)
        return output

    def push_file(self, local: str, remote: str) -> str:
        """
        Push a file from the local machine to the device.

        Args:
            local: Local source path.
            remote: Remote destination path on device.

        Returns:
            ADB output string.
        """
        output = self.run_command(["push", local, remote])
        logger.debug("Pushed %s → %s", local, remote)
        return output

    # ------------------------------------------------------------------
    # Device status
    # ------------------------------------------------------------------

    def is_device_connected(self) -> bool:
        """
        Check whether a device is connected and authorized.

        Returns:
            True if at least one device is connected and authorized.
        """
        try:
            output = self.run_command(["devices"])
            lines = output.splitlines()
            for line in lines[1:]:  # Skip header
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    serial, status = parts[0], parts[1]
                    if self.device_serial:
                        if serial == self.device_serial and status == "device":
                            return True
                    else:
                        if status == "device":
                            return True
            return False
        except self.ADBError:
            return False

    def get_device_info(self) -> dict[str, str]:
        """
        Retrieve basic device information.

        Returns:
            Dict with keys: model, manufacturer, android_version, sdk_version.
        """
        props = {
            "model": "ro.product.model",
            "manufacturer": "ro.product.manufacturer",
            "android_version": "ro.build.version.release",
            "sdk_version": "ro.build.version.sdk",
        }
        info: dict[str, str] = {}
        for key, prop in props.items():
            try:
                info[key] = self._shell(f"getprop {prop}")
            except self.ADBError:
                info[key] = "unknown"
        return info

    def wait_for_device(self, timeout: int = 30) -> bool:
        """
        Wait for a device to become available.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if device connected within timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_device_connected():
                return True
            time.sleep(1)
        return False
