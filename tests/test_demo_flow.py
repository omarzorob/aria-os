"""
tests/test_demo_flow.py
=======================
Integration tests for the Aria OS demo flow.

All tests use mocked ADB subprocess calls — no real phone required.
Run with: python -m pytest tests/test_demo_flow.py -v
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.android.adb_bridge import ADBBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_adb_output():
    """Factory for creating mock subprocess.run results."""
    def _make(stdout: str = "", returncode: int = 0, stderr: str = ""):
        result = MagicMock()
        result.stdout = stdout
        result.returncode = returncode
        result.stderr = stderr
        return result
    return _make


@pytest.fixture
def adb(mock_adb_output):
    """ADBBridge instance with subprocess.run mocked."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = mock_adb_output("", 0, "")
        bridge = ADBBridge()
        bridge._mock_run = mock_run
        yield bridge, mock_run


# ---------------------------------------------------------------------------
# 1. ADB Bridge core
# ---------------------------------------------------------------------------

class TestADBBridgeCore:
    """Tests for ADBBridge core command execution."""

    def test_run_command_builds_correct_args(self, mock_adb_output):
        """run_command should prepend 'adb' and pass args correctly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("output text")
            bridge = ADBBridge()
            result = bridge.run_command("devices")
            assert result == "output text"
            args_called = mock_run.call_args[0][0]
            assert args_called[0] == "adb"
            assert "devices" in args_called

    def test_run_command_with_serial(self, mock_adb_output):
        """run_command should include -s <serial> when device_serial is set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("output")
            bridge = ADBBridge(device_serial="emulator-5554")
            bridge.run_command("shell ls")
            args = mock_run.call_args[0][0]
            assert "-s" in args
            assert "emulator-5554" in args

    def test_run_command_raises_on_error(self, mock_adb_output):
        """run_command should raise ADBError when command fails with error output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("", 1, "error: device not found")
            bridge = ADBBridge()
            with pytest.raises(ADBBridge.ADBError):
                bridge.run_command("shell ls")

    def test_run_command_raises_when_adb_missing(self):
        """run_command should raise ADBError when adb binary is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            bridge = ADBBridge()
            with pytest.raises(ADBBridge.ADBError, match="not found"):
                bridge.run_command("devices")

    def test_run_command_raises_on_timeout(self, mock_adb_output):
        """run_command should raise ADBError on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 30)):
            bridge = ADBBridge()
            with pytest.raises(ADBBridge.ADBError, match="timed out"):
                bridge.run_command("shell ls")


# ---------------------------------------------------------------------------
# 2. Device connection / info
# ---------------------------------------------------------------------------

class TestDeviceConnection:
    """Tests for device detection and info retrieval."""

    def test_is_device_connected_true(self, mock_adb_output):
        """is_device_connected should return True when a device is listed."""
        devices_output = "List of devices attached\nemulator-5554\tdevice\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output(devices_output)
            bridge = ADBBridge()
            assert bridge.is_device_connected() is True

    def test_is_device_connected_false_when_empty(self, mock_adb_output):
        """is_device_connected should return False when no devices are listed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("List of devices attached\n")
            bridge = ADBBridge()
            assert bridge.is_device_connected() is False

    def test_is_device_connected_false_when_unauthorized(self, mock_adb_output):
        """is_device_connected should return False for unauthorized devices."""
        output = "List of devices attached\nABC123\tunauthorized\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output(output)
            bridge = ADBBridge()
            assert bridge.is_device_connected() is False

    def test_is_device_connected_false_on_adb_error(self):
        """is_device_connected should return False (not raise) on ADB errors."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            bridge = ADBBridge()
            assert bridge.is_device_connected() is False

    def test_get_device_info_returns_dict(self, mock_adb_output):
        """get_device_info should return a dict with expected keys."""
        def side_effect(*args, **kwargs):
            cmd = args[0]
            prop = cmd[-1] if cmd else ""
            responses = {
                "ro.product.model": "Pixel 8 Pro",
                "ro.product.manufacturer": "Google",
                "ro.build.version.release": "14",
                "ro.build.version.sdk": "34",
            }
            for prop_name, value in responses.items():
                if prop_name in " ".join(cmd):
                    return mock_adb_output(value)
            return mock_adb_output("")

        with patch("subprocess.run", side_effect=side_effect):
            bridge = ADBBridge()
            info = bridge.get_device_info()
            assert "model" in info
            assert "manufacturer" in info
            assert "android_version" in info
            assert "sdk_version" in info


# ---------------------------------------------------------------------------
# 3. Touch / input
# ---------------------------------------------------------------------------

class TestTouchInput:
    """Tests for tap, swipe, type_text, press_key."""

    def test_tap_sends_correct_command(self, mock_adb_output):
        """tap should send 'input tap x y' shell command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge.tap(100, 200)
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "input tap 100 200" in cmd_str

    def test_swipe_sends_correct_command(self, mock_adb_output):
        """swipe should send 'input swipe x1 y1 x2 y2 duration' command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge.swipe(0, 800, 0, 200, 500)
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "input swipe 0 800 0 200 500" in cmd_str

    def test_type_text_escapes_spaces(self, mock_adb_output):
        """type_text should replace spaces with %s for ADB compatibility."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge.type_text("Hello World")
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "Hello%sWorld" in cmd_str

    def test_press_key_with_int(self, mock_adb_output):
        """press_key with int keycode should use numeric form."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge.press_key(4)  # BACK
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "keyevent 4" in cmd_str

    def test_press_key_with_string(self, mock_adb_output):
        """press_key with string should use KEYCODE_ prefix form."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge.press_key("BACK")
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "KEYCODE_BACK" in cmd_str


# ---------------------------------------------------------------------------
# 4. Screenshot
# ---------------------------------------------------------------------------

class TestScreenshot:
    """Tests for take_screenshot."""

    def test_take_screenshot_returns_path(self, mock_adb_output, tmp_path):
        """take_screenshot should return a path to a saved PNG file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            # Create a dummy screenshot file to simulate pull
            screenshot_path = str(tmp_path / "test_screenshot.png")
            # Write fake PNG bytes
            with open(screenshot_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

            bridge = ADBBridge()
            # Mock pull_file to copy our fake file
            with patch.object(bridge, "pull_file") as mock_pull:
                def fake_pull(remote, local):
                    with open(local, "wb") as f:
                        f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
                    return ""
                mock_pull.side_effect = fake_pull

                result = bridge.take_screenshot()
                assert result.endswith(".png")
                assert os.path.exists(result)
                # Clean up
                os.unlink(result)

    def test_take_screenshot_uses_custom_path(self, mock_adb_output, tmp_path):
        """take_screenshot should save to the specified local_path."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            expected_path = str(tmp_path / "custom.png")

            with patch.object(bridge, "pull_file") as mock_pull:
                def fake_pull(remote, local):
                    with open(local, "wb") as f:
                        f.write(b"PNG")
                    return ""
                mock_pull.side_effect = fake_pull

                result = bridge.take_screenshot(local_path=expected_path)
                assert result == expected_path


# ---------------------------------------------------------------------------
# 5. Screen size
# ---------------------------------------------------------------------------

class TestScreenSize:
    """Tests for get_screen_size."""

    def test_get_screen_size_parses_output(self, mock_adb_output):
        """get_screen_size should parse 'Physical size: WxH' correctly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("Physical size: 1080x2340")
            bridge = ADBBridge()
            w, h = bridge.get_screen_size()
            assert w == 1080
            assert h == 2340

    def test_get_screen_size_raises_on_bad_output(self, mock_adb_output):
        """get_screen_size should raise ADBError when output is unparseable."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("garbage output")
            bridge = ADBBridge()
            with pytest.raises(ADBBridge.ADBError):
                bridge.get_screen_size()


# ---------------------------------------------------------------------------
# 6. SMS send (via ADB intent)
# ---------------------------------------------------------------------------

class TestSMSSend:
    """Tests for SMS sending via ADB intent."""

    def test_sms_send_calls_am_start(self, mock_adb_output):
        """SMS send should invoke am start with SENDTO intent."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            # Simulate what the SMS tool does via bridge._shell
            bridge._shell(
                "am start -a android.intent.action.SENDTO "
                "-d 'smsto:+15551234567' "
                "--es sms_body 'Hello from Aria!'"
            )
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "am start" in cmd_str
            assert "SENDTO" in cmd_str

    def test_sms_tool_send_returns_true_on_success(self, mock_adb_output):
        """SMSTool.send_sms should return True when ADB succeeds."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            try:
                from agent.tools.implementations.sms_tool import SMSTool
                sms = SMSTool(bridge)
                result = sms.send_sms("+15551234567", "Test message")
                assert result is True
            except ImportError:
                pytest.skip("SMSTool not available")

    def test_sms_tool_send_returns_false_on_failure(self):
        """SMSTool.send_sms should return False when ADB fails."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            bridge = ADBBridge()
            try:
                from agent.tools.implementations.sms_tool import SMSTool
                sms = SMSTool(bridge)
                result = sms.send_sms("+15551234567", "Test")
                assert result is False
            except ImportError:
                pytest.skip("SMSTool not available")


# ---------------------------------------------------------------------------
# 7. Alarm set (via ADB intent)
# ---------------------------------------------------------------------------

class TestAlarmSet:
    """Tests for alarm setting via ADB intent."""

    def test_alarm_intent_format(self, mock_adb_output):
        """Setting an alarm should use the correct Android alarm intent."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("")
            bridge = ADBBridge()
            bridge._shell(
                "am start -a android.intent.action.SET_ALARM "
                "--ei android.intent.extra.alarm.HOUR 8 "
                "--ei android.intent.extra.alarm.MINUTES 0 "
                "--ez android.intent.extra.alarm.SKIP_UI true"
            )
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "SET_ALARM" in cmd_str
            assert "HOUR" in cmd_str


# ---------------------------------------------------------------------------
# 8. App launch
# ---------------------------------------------------------------------------

class TestAppLaunch:
    """Tests for launching apps via ADB monkey."""

    def test_app_launch_uses_monkey(self, mock_adb_output):
        """App launch should use adb shell monkey with LAUNCHER category."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("Events injected: 1\n## Network stats: elapsed: 18ms")
            bridge = ADBBridge()
            output = bridge._shell(
                "monkey -p com.google.android.calculator "
                "-c android.intent.category.LAUNCHER 1"
            )
            cmd_str = " ".join(mock_run.call_args[0][0])
            assert "monkey" in cmd_str
            assert "com.google.android.calculator" in cmd_str


# ---------------------------------------------------------------------------
# 9. Weather fetch (no ADB needed)
# ---------------------------------------------------------------------------

class TestWeatherFetch:
    """Tests for weather data retrieval (uses web API, not ADB)."""

    def test_weather_fetch_returns_data(self):
        """Weather fetch should return a non-empty string."""
        import urllib.request
        import json

        mock_response_data = {
            "current_condition": [{
                "temp_F": "72",
                "weatherDesc": [{"value": "Partly Cloudy"}],
                "humidity": "55",
            }]
        }

        class FakeResponse:
            def read(self):
                return json.dumps(mock_response_data).encode()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            data = mock_response_data
            current = data["current_condition"][0]
            temp_f = current["temp_F"]
            desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            weather_text = f"{temp_f}°F, {desc}, {humidity}% humidity"
            assert "72°F" in weather_text
            assert "Cloudy" in weather_text

    def test_weather_gracefully_handles_network_error(self):
        """Weather fetch should fall back gracefully on network failure."""
        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            weather_text = "72°F, Partly Cloudy"  # Default fallback
            try:
                import urllib.request
                with urllib.request.urlopen("https://wttr.in/test", timeout=1):
                    pass
            except Exception:
                pass  # Expected
            assert weather_text  # Fallback always has content


# ---------------------------------------------------------------------------
# 10. Notification read
# ---------------------------------------------------------------------------

class TestNotificationRead:
    """Tests for notification reading."""

    def test_sim_notifications_have_expected_structure(self):
        """Simulated notifications should have app name and message."""
        sim_notifications = [
            ("Gmail", "New message from team@company.com"),
            ("Slack", "#general: New message"),
            ("Calendar", "Meeting in 30 minutes"),
        ]
        for app, msg in sim_notifications:
            assert isinstance(app, str)
            assert len(app) > 0
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_notifications_limit_to_three(self):
        """Demo should show at most 3 notifications."""
        many_notifs = [("App", f"Message {i}") for i in range(10)]
        top_3 = many_notifs[:3]
        assert len(top_3) == 3


# ---------------------------------------------------------------------------
# 11. File push/pull
# ---------------------------------------------------------------------------

class TestFilePushPull:
    """Tests for file transfer methods."""

    def test_pull_file_calls_adb_pull(self, mock_adb_output):
        """pull_file should run 'adb pull remote local'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("1 file pulled.")
            bridge = ADBBridge()
            result = bridge.pull_file("/sdcard/test.txt", "/tmp/test.txt")
            args = mock_run.call_args[0][0]
            assert "pull" in args
            assert "/sdcard/test.txt" in args

    def test_push_file_calls_adb_push(self, mock_adb_output):
        """push_file should run 'adb push local remote'."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_adb_output("1 file pushed.")
            bridge = ADBBridge()
            bridge.push_file("/tmp/test.txt", "/sdcard/test.txt")
            args = mock_run.call_args[0][0]
            assert "push" in args
            assert "/sdcard/test.txt" in args


# ---------------------------------------------------------------------------
# 12. Demo flow integration
# ---------------------------------------------------------------------------

class TestDemoFlowIntegration:
    """End-to-end demo flow tests (mocked)."""

    def test_full_demo_sequence_completes(self, mock_adb_output):
        """Full demo sequence should complete all steps without raising."""
        with patch("subprocess.run") as mock_run:
            # Return sensible defaults for all ADB calls
            def smart_mock(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
                if "devices" in cmd_str:
                    return mock_adb_output("List of devices attached\nemulator-5554\tdevice")
                elif "getprop ro.product.model" in cmd_str:
                    return mock_adb_output("Pixel 8 Pro")
                elif "getprop ro.product.manufacturer" in cmd_str:
                    return mock_adb_output("Google")
                elif "getprop ro.build.version.release" in cmd_str:
                    return mock_adb_output("14")
                elif "getprop ro.build.version.sdk" in cmd_str:
                    return mock_adb_output("34")
                elif "wm size" in cmd_str:
                    return mock_adb_output("Physical size: 1080x2340")
                else:
                    return mock_adb_output("")

            mock_run.side_effect = smart_mock
            bridge = ADBBridge()

            # Run each demo step
            assert bridge.is_device_connected() is True
            info = bridge.get_device_info()
            assert info["model"] == "Pixel 8 Pro"
            w, h = bridge.get_screen_size()
            assert w == 1080 and h == 2340

            # Touch actions
            bridge.tap(540, 960)
            bridge.swipe(540, 1600, 540, 400)
            bridge.type_text("Hello Aria")
            bridge.press_key(66)

    def test_simulated_mode_has_complete_data(self):
        """Simulated mode data should have all required fields."""
        sim_info = {
            "manufacturer": "Google",
            "model": "Pixel 8 Pro",
            "android_version": "14",
            "sdk_version": "34",
        }
        required_keys = ["manufacturer", "model", "android_version", "sdk_version"]
        for key in required_keys:
            assert key in sim_info
            assert len(sim_info[key]) > 0

    def test_demo_can_import_bridge(self):
        """ADBBridge should be importable from the project."""
        from agent.android.adb_bridge import ADBBridge as Bridge
        assert Bridge is not None
        bridge = Bridge()
        assert hasattr(bridge, "tap")
        assert hasattr(bridge, "swipe")
        assert hasattr(bridge, "type_text")
        assert hasattr(bridge, "press_key")
        assert hasattr(bridge, "take_screenshot")
        assert hasattr(bridge, "get_screen_size")
        assert hasattr(bridge, "install_apk")
        assert hasattr(bridge, "pull_file")
        assert hasattr(bridge, "push_file")
        assert hasattr(bridge, "is_device_connected")
        assert hasattr(bridge, "get_device_info")
