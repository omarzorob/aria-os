"""
Aria Accessibility Service Bridge

Python client that communicates with the Aria Accessibility Service APK running on an
Android device. The APK implements a JSON-RPC socket server on port 7765.

Protocol: Line-delimited JSON-RPC over TCP
APK package: ai.aria.accessibility
Socket port: 7765 (on-device, forwarded via ADB)

ADB port forwarding setup:
    adb forward tcp:7765 tcp:7765

Build the APK:
    cd apps/accessibility-service && ./gradlew assembleDebug

Install the APK:
    adb install apps/accessibility-service/app/build/outputs/apk/debug/app-debug.apk

Enable the service:
    Android Settings → Accessibility → Aria Accessibility Service → Enable
"""

from __future__ import annotations

import json
import socket
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Port must match SocketServer.PORT in Kotlin
BRIDGE_PORT = 7765
BRIDGE_HOST = "127.0.0.1"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0
APK_PACKAGE = "ai.aria.accessibility"


@dataclass
class UIElement:
    """Represents a UI element from the Android accessibility tree."""

    id: str
    text: str
    content_description: str
    class_name: str
    bounds: dict[str, int]          # left, top, right, bottom
    is_clickable: bool
    is_editable: bool
    is_scrollable: bool
    is_enabled: bool
    child_count: int
    node_hash_code: int             # used as temp id for tapping

    @classmethod
    def from_dict(cls, data: dict) -> "UIElement":
        return cls(
            id=data.get("id", ""),
            text=data.get("text", ""),
            content_description=data.get("contentDescription", ""),
            class_name=data.get("className", ""),
            bounds=data.get("bounds", {"left": 0, "top": 0, "right": 0, "bottom": 0}),
            is_clickable=data.get("isClickable", False),
            is_editable=data.get("isEditable", False),
            is_scrollable=data.get("isScrollable", False),
            is_enabled=data.get("isEnabled", True),
            child_count=data.get("childCount", 0),
            node_hash_code=data.get("nodeHashCode", 0),
        )

    def center(self) -> tuple[int, int]:
        """Return the center coordinates of this element."""
        b = self.bounds
        x = (b.get("left", 0) + b.get("right", 0)) // 2
        y = (b.get("top", 0) + b.get("bottom", 0)) // 2
        return x, y


class AccessibilityServiceBridge:
    """
    Python bridge to the Aria Accessibility Service running on an Android device.

    The Aria Accessibility Service APK must be installed and enabled on the device.
    ADB port forwarding must be active: `adb forward tcp:7765 tcp:7765`

    Usage:
        bridge = AccessibilityServiceBridge()
        bridge.connect()
        # check it's alive
        print(bridge.ping())
        # get all on-screen elements
        elements = bridge.get_screen_elements()
        # tap an element
        bridge.tap_element(elements[0].node_hash_code)
        bridge.disconnect()

    Or as a context manager:
        with AccessibilityServiceBridge() as bridge:
            bridge.tap_coords(540, 960)
    """

    def __init__(
        self,
        host: str = BRIDGE_HOST,
        port: int = BRIDGE_PORT,
        adb_path: str = "adb",
    ) -> None:
        self.host = host
        self.port = port
        self.adb_path = adb_path
        self._sock: Optional[socket.socket] = None
        self._file = None           # buffered file reader over the socket
        self._connected = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, setup_forward: bool = True) -> bool:
        """
        Connect to the Aria Accessibility Service on the device.

        Args:
            setup_forward: If True, runs `adb forward tcp:7765 tcp:7765` first.

        Returns:
            True if connected successfully.
        """
        if setup_forward:
            self._setup_adb_forward()

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(CONNECT_TIMEOUT)
            self._sock.connect((self.host, self.port))
            self._sock.settimeout(READ_TIMEOUT)
            # Wrap in a file for easy line-by-line reading
            self._file = self._sock.makefile("r", encoding="utf-8")
            self._connected = True
            logger.info("Connected to Aria Accessibility Service on %s:%d", self.host, self.port)
            return True
        except (socket.error, ConnectionRefusedError) as e:
            logger.error("Failed to connect: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the Accessibility Service."""
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None
        if self._sock:
            try:
                self._sock.close()
            except socket.error:
                pass
            self._sock = None
        self._connected = False
        logger.info("Disconnected from Aria Accessibility Service")

    def is_connected(self) -> bool:
        """Return True if currently connected."""
        return self._connected

    def _setup_adb_forward(self) -> None:
        """Set up ADB port forwarding tcp:7765 → tcp:7765."""
        cmd = [self.adb_path, "forward", f"tcp:{self.port}", f"tcp:{self.port}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning("ADB forward warning: %s", result.stderr.strip())
            else:
                logger.debug("ADB forward active: port %d", self.port)
        except subprocess.TimeoutExpired:
            logger.error("ADB forward timed out")
        except FileNotFoundError:
            logger.error("adb not found: %s", self.adb_path)

    # ------------------------------------------------------------------
    # Core JSON-RPC transport
    # ------------------------------------------------------------------

    def _send_command(self, method: str, params: dict | None = None) -> Any:
        """
        Send a JSON-RPC command to the Kotlin SocketServer and return the result.

        Request format:  {"method": "...", "params": {...}}
        Response format: {"success": true, "result": ...}
                         {"success": false, "error": "..."}

        Args:
            method: The command method name (e.g., "ping", "get_screen_elements").
            params: Optional dict of parameters.

        Returns:
            The "result" value from the response.

        Raises:
            ConnectionError: If not connected.
            RuntimeError: If the service returns success=false.
            TimeoutError: If the request times out.
        """
        if not self._connected or not self._sock or not self._file:
            raise ConnectionError("Not connected to Accessibility Service. Call connect() first.")

        request = {"method": method, "params": params or {}}
        payload = json.dumps(request) + "\n"

        try:
            self._sock.sendall(payload.encode("utf-8"))
            response_line = self._file.readline()
            if not response_line:
                raise ConnectionError("Connection closed by service")

            response = json.loads(response_line.strip())

            if not response.get("success", False):
                raise RuntimeError(f"Service error [{method}]: {response.get('error', 'unknown')}")

            return response.get("result")

        except socket.timeout:
            raise TimeoutError(f"Request '{method}' timed out after {READ_TIMEOUT}s")
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON response: {e}")

    # ------------------------------------------------------------------
    # Service commands
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        """Ping the service. Returns {"status": "ok", "service": "aria-accessibility"}."""
        return self._send_command("ping")

    def get_screen_elements(self) -> list[UIElement]:
        """
        Get all UI elements currently visible on screen.

        Returns:
            List of UIElement objects.
        """
        result = self._send_command("get_screen_elements")
        if isinstance(result, list):
            return [UIElement.from_dict(e) for e in result]
        return []

    def get_screen_text(self) -> str:
        """
        Get all visible text on screen as a single string.

        Returns:
            Concatenated text content.
        """
        result = self._send_command("get_screen_text")
        if isinstance(result, dict):
            return result.get("text", "")
        return str(result) if result else ""

    def get_focused_app(self) -> str:
        """
        Get the package name of the currently active application.

        Returns:
            Package name, e.g. "com.google.android.apps.maps"
        """
        result = self._send_command("get_focused_app")
        if isinstance(result, dict):
            return result.get("package", "")
        return ""

    def find_element_by_text(self, text: str) -> list[UIElement]:
        """
        Find elements whose text or content description contains [text].

        Args:
            text: Text to search for (case-insensitive, substring match).

        Returns:
            List of matching UIElement objects.
        """
        result = self._send_command("find_element_by_text", {"text": text})
        if isinstance(result, list):
            return [UIElement.from_dict(e) for e in result]
        return []

    def find_element_by_id(self, view_id: str) -> list[UIElement]:
        """
        Find elements whose viewIdResourceName matches [view_id].

        Args:
            view_id: Resource ID to search (exact or contains match).

        Returns:
            List of matching UIElement objects.
        """
        result = self._send_command("find_element_by_id", {"id": view_id})
        if isinstance(result, list):
            return [UIElement.from_dict(e) for e in result]
        return []

    def tap_element(self, node_hash_code: int) -> bool:
        """
        Click an element identified by its nodeHashCode.

        Args:
            node_hash_code: The nodeHashCode from UIElement (temporary ID valid for current screen state).

        Returns:
            True if the click action was performed.
        """
        result = self._send_command("tap_element", {"nodeId": node_hash_code})
        if isinstance(result, dict):
            return result.get("clicked", False)
        return False

    def tap_coords(self, x: float, y: float) -> bool:
        """
        Perform a tap gesture at screen coordinates (x, y).

        Args:
            x: Horizontal coordinate in pixels.
            y: Vertical coordinate in pixels.

        Returns:
            True if gesture was dispatched.
        """
        result = self._send_command("tap_coords", {"x": x, "y": y})
        if isinstance(result, dict):
            return result.get("tapped", False)
        return False

    def swipe(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int = 300,
    ) -> bool:
        """
        Perform a swipe gesture from (x1, y1) to (x2, y2).

        Args:
            x1, y1: Start coordinates.
            x2, y2: End coordinates.
            duration_ms: Duration of the swipe in milliseconds.

        Returns:
            True if gesture was dispatched.
        """
        result = self._send_command(
            "swipe",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration_ms},
        )
        if isinstance(result, dict):
            return result.get("swiped", False)
        return False

    def type_text(self, text: str) -> bool:
        """
        Type text into the currently focused input field.

        Args:
            text: Text string to type.

        Returns:
            True if text was set successfully.
        """
        result = self._send_command("type_text", {"text": text})
        if isinstance(result, dict):
            return result.get("typed", False)
        return False

    def press_back(self) -> None:
        """Press the Back button."""
        self._send_command("press_back")

    def press_home(self) -> None:
        """Press the Home button."""
        self._send_command("press_home")

    def press_recents(self) -> None:
        """Press the Recents (overview) button."""
        self._send_command("press_recents")

    def press_notifications(self) -> None:
        """Open the notification shade."""
        self._send_command("press_notifications")

    def scroll_forward(self, node_hash_code: Optional[int] = None) -> bool:
        """
        Scroll forward (down) in a scrollable view.

        Args:
            node_hash_code: Hash of the scrollable node to scroll in, or None for root.

        Returns:
            True if scroll was performed.
        """
        params = {}
        if node_hash_code is not None:
            params["nodeId"] = node_hash_code
        result = self._send_command("scroll_forward", params)
        if isinstance(result, dict):
            return result.get("scrolled", False)
        return False

    def scroll_backward(self, node_hash_code: Optional[int] = None) -> bool:
        """
        Scroll backward (up) in a scrollable view.

        Args:
            node_hash_code: Hash of the scrollable node to scroll in, or None for root.

        Returns:
            True if scroll was performed.
        """
        params = {}
        if node_hash_code is not None:
            params["nodeId"] = node_hash_code
        result = self._send_command("scroll_backward", params)
        if isinstance(result, dict):
            return result.get("scrolled", False)
        return False

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "AccessibilityServiceBridge":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
