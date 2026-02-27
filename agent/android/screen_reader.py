"""
P1-13: Screen Reader

Extracts UI content from the Android screen using `adb shell uiautomator dump`.
Provides text extraction, UI tree parsing, element search, and layout analysis.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

from .adb_bridge import ADBBridge

logger = logging.getLogger(__name__)

DUMP_REMOTE_PATH = "/sdcard/aria_ui_dump.xml"


@dataclass
class LayoutNode:
    """Represents a single node in the Android UI hierarchy."""

    index: int
    text: str
    resource_id: str
    class_name: str
    package: str
    content_desc: str
    checkable: bool
    checked: bool
    clickable: bool
    enabled: bool
    focusable: bool
    focused: bool
    scrollable: bool
    long_clickable: bool
    password: bool
    selected: bool
    bounds: tuple[int, int, int, int]  # left, top, right, bottom
    children: list["LayoutNode"] = field(default_factory=list)

    def is_edit_field(self) -> bool:
        """Return True if this node is a text input field."""
        edit_classes = (
            "EditText",
            "AutoCompleteTextView",
            "MultiAutoCompleteTextView",
        )
        return any(ec in self.class_name for ec in edit_classes) or self.password

    def center(self) -> tuple[int, int]:
        """Return the center coordinates of this node."""
        left, top, right, bottom = self.bounds
        return (left + right) // 2, (top + bottom) // 2

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return {
            "text": self.text,
            "resourceId": self.resource_id,
            "className": self.class_name,
            "contentDesc": self.content_desc,
            "clickable": self.clickable,
            "enabled": self.enabled,
            "bounds": {
                "left": self.bounds[0],
                "top": self.bounds[1],
                "right": self.bounds[2],
                "bottom": self.bounds[3],
            },
            "children": [c.to_dict() for c in self.children],
        }


class ScreenReader:
    """
    Reads and parses the Android UI tree using uiautomator dump.

    Usage:
        reader = ScreenReader(adb_bridge)
        text = reader.get_screen_text()
        elements = reader.get_clickable_elements()
    """

    def __init__(self, adb: ADBBridge) -> None:
        """
        Initialize the ScreenReader.

        Args:
            adb: ADBBridge instance for device communication.
        """
        self.adb = adb

    # ------------------------------------------------------------------
    # Layout dump
    # ------------------------------------------------------------------

    def dump_layout(self) -> dict[str, Any]:
        """
        Dump the current UI layout and return it as a parsed dict.

        Returns:
            Dict representation of the full UI hierarchy.

        Raises:
            RuntimeError: If the dump fails or cannot be parsed.
        """
        root = self._get_layout_root()
        return root.to_dict()

    def get_ui_tree(self) -> LayoutNode:
        """
        Get the full UI tree as a LayoutNode hierarchy.

        Returns:
            Root LayoutNode of the current screen.
        """
        return self._get_layout_root()

    def _dump_to_xml(self) -> str:
        """
        Run uiautomator dump and return the XML content.

        Returns:
            XML string of the UI hierarchy.
        """
        # Trigger the dump on device
        self.adb._shell(f"uiautomator dump {DUMP_REMOTE_PATH}")

        # Pull to a temp file
        fd, local_path = tempfile.mkstemp(suffix=".xml", prefix="aria_uidump_")
        os.close(fd)

        try:
            self.adb.pull_file(DUMP_REMOTE_PATH, local_path)
            with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return content
        finally:
            try:
                os.unlink(local_path)
            except OSError:
                pass
            # Clean up remote file
            try:
                self.adb._shell(f"rm -f {DUMP_REMOTE_PATH}")
            except Exception:
                pass

    def _get_layout_root(self) -> LayoutNode:
        """Parse UI dump XML and return root LayoutNode."""
        xml_content = self._dump_to_xml()

        try:
            root_elem = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise RuntimeError(f"Failed to parse UI XML: {e}")

        def parse_node(elem: ET.Element) -> LayoutNode:
            bounds_str = elem.get("bounds", "[0,0][0,0]")
            bounds = _parse_bounds(bounds_str)
            node = LayoutNode(
                index=int(elem.get("index", 0)),
                text=elem.get("text", ""),
                resource_id=elem.get("resource-id", ""),
                class_name=elem.get("class", ""),
                package=elem.get("package", ""),
                content_desc=elem.get("content-desc", ""),
                checkable=elem.get("checkable", "false") == "true",
                checked=elem.get("checked", "false") == "true",
                clickable=elem.get("clickable", "false") == "true",
                enabled=elem.get("enabled", "true") == "true",
                focusable=elem.get("focusable", "false") == "true",
                focused=elem.get("focused", "false") == "true",
                scrollable=elem.get("scrollable", "false") == "true",
                long_clickable=elem.get("long-clickable", "false") == "true",
                password=elem.get("password", "false") == "true",
                selected=elem.get("selected", "false") == "true",
                bounds=bounds,
            )
            for child_elem in elem:
                node.children.append(parse_node(child_elem))
            return node

        # The XML root is <hierarchy>, find first <node>
        first_node = root_elem.find(".//node")
        if first_node is None:
            # Return empty root
            return LayoutNode(
                index=0, text="", resource_id="", class_name="hierarchy",
                package="", content_desc="", checkable=False, checked=False,
                clickable=False, enabled=True, focusable=False, focused=False,
                scrollable=False, long_clickable=False, password=False,
                selected=False, bounds=(0, 0, 0, 0),
            )

        return parse_node(first_node)

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def get_screen_text(self) -> str:
        """
        Get all visible text on the current screen.

        Returns:
            Concatenated text from all text-bearing UI elements.
        """
        root = self._get_layout_root()
        texts: list[str] = []
        self._collect_text(root, texts)
        return "\n".join(t for t in texts if t.strip())

    def _collect_text(self, node: LayoutNode, acc: list[str]) -> None:
        if node.text:
            acc.append(node.text)
        if node.content_desc and node.content_desc != node.text:
            acc.append(node.content_desc)
        for child in node.children:
            self._collect_text(child, acc)

    def find_text_on_screen(self, query: str, case_sensitive: bool = False) -> list[LayoutNode]:
        """
        Find all nodes containing the given query text.

        Args:
            query: Text to search for.
            case_sensitive: If False (default), case-insensitive match.

        Returns:
            List of matching LayoutNodes.
        """
        root = self._get_layout_root()
        results: list[LayoutNode] = []
        q = query if case_sensitive else query.lower()
        self._search_text(root, q, case_sensitive, results)
        return results

    def _search_text(
        self,
        node: LayoutNode,
        query: str,
        case_sensitive: bool,
        results: list[LayoutNode],
    ) -> None:
        text = node.text if case_sensitive else node.text.lower()
        desc = node.content_desc if case_sensitive else node.content_desc.lower()
        if query in text or query in desc:
            results.append(node)
        for child in node.children:
            self._search_text(child, query, case_sensitive, results)

    # ------------------------------------------------------------------
    # Element queries
    # ------------------------------------------------------------------

    def get_clickable_elements(self) -> list[LayoutNode]:
        """
        Get all clickable elements on the current screen.

        Returns:
            List of LayoutNodes that are clickable and enabled.
        """
        root = self._get_layout_root()
        results: list[LayoutNode] = []
        self._collect_matching(root, lambda n: n.clickable and n.enabled, results)
        return results

    def get_edit_fields(self) -> list[LayoutNode]:
        """
        Get all text input (EditText) fields on the current screen.

        Returns:
            List of LayoutNodes that are editable text fields.
        """
        root = self._get_layout_root()
        results: list[LayoutNode] = []
        self._collect_matching(root, lambda n: n.is_edit_field(), results)
        return results

    def get_scrollable_elements(self) -> list[LayoutNode]:
        """
        Get all scrollable elements on the current screen.

        Returns:
            List of LayoutNodes that support scrolling.
        """
        root = self._get_layout_root()
        results: list[LayoutNode] = []
        self._collect_matching(root, lambda n: n.scrollable, results)
        return results

    def _collect_matching(
        self,
        node: LayoutNode,
        predicate,
        results: list[LayoutNode],
    ) -> None:
        if predicate(node):
            results.append(node)
        for child in node.children:
            self._collect_matching(child, predicate, results)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """
    Parse Android bounds string format "[left,top][right,bottom]".

    Args:
        bounds_str: Bounds string like "[0,0][1080,2340]".

    Returns:
        Tuple of (left, top, right, bottom).
    """
    numbers = re.findall(r"\d+", bounds_str)
    if len(numbers) == 4:
        return tuple(int(n) for n in numbers)  # type: ignore
    return (0, 0, 0, 0)
