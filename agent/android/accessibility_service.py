"""
P1-10: Accessibility Service Bridge

Defines the AccessibilityService integration spec and provides a Python bridge
that communicates with an Android Accessibility Service APK via ADB socket.

The companion APK (aria-accessibility-service) runs on the Android device and
exposes a local TCP socket that this bridge connects to via ADB port forwarding.

Protocol: JSON-RPC over TCP.
APK package: com.aria.accessibilityservice
Socket port: 9876 (on-device)
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

# ADB port-forward: adb forward tcp:9876 tcp:9876
BRIDGE_PORT = 9876
BRIDGE_HOST = "127.0.0.1"
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0
APK_PACKAGE = "com.aria.accessibilityservice"


@dataclass
class UIElement:
    """Represents a UI element from the Android accessibility tree."""

    element_id: str
    text: str
    content_description: str
    class_name: str
    resource_id: str
    bounds: dict[str, int]  # left, top, right, bottom
    clickable: bool
    focusable: bool
    scrollable: bool
    enabled: bool
    children: list["UIElement"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "UIElement":
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            element_id=data.get("id", ""),
            text=data.get("text", ""),
            content_description=data.get("contentDescription", ""),
            class_name=data.get("className", ""),
            resource_id=data.get("resourceId", ""),
            bounds=data.get("bounds", {"left": 0, "top": 0, "right": 0, "bottom": 0}),
            clickable=data.get("clickable", False),
            focusable=data.get("focusable", False),
            scrollable=data.get("scrollable", False),
            enabled=data.get("enabled", True),
            children=children,
        )

    def center(self) -> tuple[int, int]:
        """Return the center coordinates of this element."""
        b = self.bounds
        x = (b["left"] + b["right"]) // 2
        y = (b["top"] + b["bottom"]) // 2
        return x, y


class AccessibilityServiceBridge:
    """
    Python bridge to the Aria Accessibility Service running on an Android device.

    Usage:
        bridge = AccessibilityServiceBridge()
        bridge.connect()
        elements = bridge.get_screen_elements()
        bridge.tap_element(elements[0])
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
        self._connected = False
        self._request_id = 0

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, setup_forward: bool = True) -> bool:
        """
        Connect to the Accessibility Service bridge.

        Args:
            setup_forward: If True, runs `adb forward` before connecting.

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
            self._connected = True
            logger.info("Connected to Accessibility Service on %s:%d", self.host, self.port)
            return True
        except (socket.error, ConnectionRefusedError) as e:
            logger.error("Failed to connect to Accessibility Service: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the bridge."""
        if self._sock:
            try:
                self._sock.close()
            except socket.error:
                pass
            self._sock = None
        self._connected = False
        logger.info("Disconnected from Accessibility Service")

    def is_connected(self) -> bool:
        """Return True if the bridge is currently connected."""
        return self._connected

    def _setup_adb_forward(self) -> None:
        """Set up ADB port forwarding for the bridge socket."""
        cmd = [self.adb_path, "forward", f"tcp:{self.port}", f"tcp:{self.port}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning("ADB forward warning: %s", result.stderr.strip())
            else:
                logger.debug("ADB forward set up: %s", result.stdout.strip())
        except subprocess.TimeoutExpired:
            logger.error("ADB forward timed out")
        except FileNotFoundError:
            logger.error("ADB not found at: %s", self.adb_path)

    # ------------------------------------------------------------------
    # RPC communication
    # ------------------------------------------------------------------

    def _send_request(self, method: str, params: dict | None = None) -> dict:
        """
        Send a JSON-RPC request to the bridge and return the response.

        Args:
            method: RPC method name.
            params: Optional parameters dict.

        Returns:
            Response dict from the bridge.

        Raises:
            ConnectionError: If not connected or send fails.
            TimeoutError: If response times out.
            ValueError: If response is malformed.
        """
        if not self._connected or not self._sock:
            raise ConnectionError("Not connected to Accessibility Service")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }

        try:
            payload = json.dumps(request) + "\n"
            self._sock.sendall(payload.encode("utf-8"))

            # Read response (newline-delimited JSON)
            data = b""
            while not data.endswith(b"\n"):
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("Connection closed by bridge")
                data += chunk

            response = json.loads(data.decode("utf-8").strip())
            if "error" in response:
                raise RuntimeError(f"Bridge error: {response['error']}")
            return response.get("result", {})

        except socket.timeout:
            raise TimeoutError(f"Request '{method}' timed out after {READ_TIMEOUT}s")
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON response: {e}")

    # ------------------------------------------------------------------
    # Screen element access
    # ------------------------------------------------------------------

    def get_screen_elements(self) -> list[UIElement]:
        """
        Get all UI elements currently visible on screen.

        Returns:
            List of UIElement objects representing the accessibility tree.
        """
        result = self._send_request("getScreenElements")
        elements_data = result.get("elements", [])
        return [UIElement.from_dict(e) for e in elements_data]

    def find_element_by_text(self, text: str, exact: bool = False) -> Optional[UIElement]:
        """
        Find a UI element by its visible text.

        Args:
            text: Text to search for.
            exact: If True, match exactly; otherwise case-insensitive substring.

        Returns:
            First matching UIElement, or None.
        """
        result = self._send_request("findElementByText", {"text": text, "exact": exact})
        element_data = result.get("element")
        if element_data:
            return UIElement.from_dict(element_data)
        return None

    def find_element_by_id(self, resource_id: str) -> Optional[UIElement]:
        """
        Find a UI element by its Android resource ID.

        Args:
            resource_id: Resource ID string (e.g., "com.example:id/button").

        Returns:
            Matching UIElement, or None.
        """
        result = self._send_request("findElementById", {"resourceId": resource_id})
        element_data = result.get("element")
        if element_data:
            return UIElement.from_dict(element_data)
        return None

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def tap_element(self, element: UIElement) -> bool:
        """
        Perform a tap/click action on the given element.

        Args:
            element: The UIElement to tap.

        Returns:
            True if the action was performed successfully.
        """
        result = self._send_request(
            "tapElement",
            {"elementId": element.element_id, "bounds": element.bounds},
        )
        return result.get("success", False)

    def type_text(self, text: str) -> bool:
        """
        Type text into the currently focused input field.

        Args:
            text: Text to type.

        Returns:
            True if text was entered successfully.
        """
        result = self._send_request("typeText", {"text": text})
        return result.get("success", False)

    def scroll(
        self,
        direction: str,
        element_id: Optional[str] = None,
        amount: int = 1,
    ) -> bool:
        """
        Scroll in the specified direction.

        Args:
            direction: "up", "down", "left", or "right".
            element_id: Optional element ID to scroll within.
            amount: Number of scroll steps.

        Returns:
            True if scroll was performed.
        """
        if direction not in ("up", "down", "left", "right"):
            raise ValueError(f"Invalid scroll direction: {direction}")

        result = self._send_request(
            "scroll",
            {"direction": direction, "elementId": element_id, "amount": amount},
        )
        return result.get("success", False)

    def get_focused_app(self) -> str:
        """
        Get the package name of the currently focused application.

        Returns:
            Package name string (e.g., "com.google.android.dialer").
        """
        result = self._send_request("getFocusedApp")
        return result.get("packageName", "")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "AccessibilityServiceBridge":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
