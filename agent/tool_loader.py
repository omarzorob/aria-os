"""
P2-2: Aria Tool Loader

Auto-discovers and registers all tools from agent/tools/implementations/.
Tools are found by scanning for *_tool.py files, imported dynamically,
and instantiated with the shared ADBBridge.

Usage:
    from agent.tool_loader import scan_tools, register_all, get_tool_manifest

    tool_classes = scan_tools()
    register_all(tool_registry, adb_bridge)
    manifest = get_tool_manifest()
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any, Type

logger = logging.getLogger(__name__)

# Cache for discovered tool classes
_discovered_classes: list[Type] = []
_manifest_cache: list[dict] | None = None


def scan_tools() -> list[Type]:
    """
    Scan agent/tools/implementations/ for all *_tool.py files
    and return a list of tool classes found within them.

    Only classes that have both `name` and `execute` attributes are included
    (duck-typing check to avoid importing non-tool classes).

    Returns:
        List of tool class objects.

    Raises:
        No exceptions — import errors are logged and skipped gracefully.
    """
    global _discovered_classes
    _discovered_classes = []

    impl_package = "agent.tools.implementations"

    try:
        impl_module = importlib.import_module(impl_package)
    except ImportError as exc:
        logger.error("Cannot import tool implementations package: %s", exc)
        return []

    impl_path = Path(inspect.getfile(impl_module)).parent

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(impl_path)]):
        if not module_name.endswith("_tool"):
            continue  # Only *_tool.py files

        full_name = f"{impl_package}.{module_name}"
        try:
            module = importlib.import_module(full_name)
        except ImportError as exc:
            logger.warning("Skipping %s — import error: %s", full_name, exc)
            continue
        except Exception as exc:
            logger.warning("Skipping %s — unexpected error: %s", full_name, exc)
            continue

        # Find tool classes in the module
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if not inspect.isclass(obj):
                continue
            if obj.__module__ != full_name:
                continue  # Skip re-exported classes from other modules
            if not (hasattr(obj, "name") and hasattr(obj, "execute")):
                continue  # Not a tool class

            logger.debug("Discovered tool class: %s.%s", full_name, attr_name)
            _discovered_classes.append(obj)

    logger.info("Discovered %d tool class(es)", len(_discovered_classes))
    return list(_discovered_classes)


def register_all(tool_registry: Any, adb_bridge: Any) -> int:
    """
    Instantiate every discovered tool class and register it in the registry.

    Tools are instantiated with the shared ADBBridge if their __init__
    accepts an `adb` parameter. Otherwise they're constructed with no args.

    Args:
        tool_registry: Object with a `register(tool)` method (or callable).
        adb_bridge: ADBBridge instance to pass to tools that need it.

    Returns:
        Number of tools successfully registered.
    """
    if not _discovered_classes:
        scan_tools()

    registered = 0
    for tool_class in _discovered_classes:
        try:
            # Inspect __init__ to determine how to instantiate
            sig = inspect.signature(tool_class.__init__)
            params = list(sig.parameters.keys())  # ['self', ...]

            # Does this class accept an adb parameter?
            if "adb" in params:
                instance = tool_class(adb=adb_bridge)
            elif len(params) > 1:  # Has params beyond self
                instance = tool_class(adb_bridge)
            else:
                instance = tool_class()

            # Register using the registry's register method or call the registry
            if hasattr(tool_registry, "register"):
                tool_registry.register(instance)
            elif callable(tool_registry):
                tool_registry(instance)
            else:
                raise TypeError(f"tool_registry has no register() method: {tool_registry!r}")

            logger.info("Registered tool: %s", getattr(instance, "name", tool_class.__name__))
            registered += 1

        except Exception as exc:
            logger.warning("Failed to register %s: %s", tool_class.__name__, exc)

    logger.info("Registered %d/%d tools", registered, len(_discovered_classes))
    return registered


def get_tool_manifest() -> list[dict]:
    """
    Return a JSON-serialisable manifest of all available tools.

    Each entry contains:
        - name: tool name
        - description: what the tool does
        - parameters: JSON schema dict of input parameters (if available)
        - class_name: Python class name

    Returns:
        List of tool descriptor dicts.
    """
    global _manifest_cache

    if _manifest_cache is not None:
        return _manifest_cache

    if not _discovered_classes:
        scan_tools()

    manifest: list[dict] = []
    for tool_class in _discovered_classes:
        entry: dict = {
            "class_name": tool_class.__name__,
            "name": None,
            "description": None,
            "parameters": {},
        }

        # Try to get name / description from class attributes or instance
        if hasattr(tool_class, "name"):
            raw = tool_class.name
            entry["name"] = raw if isinstance(raw, str) else raw.fget(None) if hasattr(raw, "fget") else str(raw)  # type: ignore
        if hasattr(tool_class, "description"):
            raw = tool_class.description
            entry["description"] = (
                raw if isinstance(raw, str) else raw.fget(None) if hasattr(raw, "fget") else str(raw)  # type: ignore
            )

        # Try to get input_schema from class
        if hasattr(tool_class, "input_schema"):
            try:
                raw = tool_class.input_schema
                entry["parameters"] = (
                    raw if isinstance(raw, dict) else raw.fget(None) if hasattr(raw, "fget") else {}  # type: ignore
                )
            except Exception:
                pass

        # Fall back: try instantiating with no args
        if entry["name"] is None or entry["description"] is None:
            try:
                instance = tool_class()
                entry["name"] = entry["name"] or getattr(instance, "name", tool_class.__name__)
                entry["description"] = entry["description"] or getattr(instance, "description", "")
                entry["parameters"] = entry["parameters"] or getattr(instance, "input_schema", {})
            except Exception:
                entry["name"] = entry["name"] or tool_class.__name__
                entry["description"] = entry["description"] or ""

        manifest.append(entry)

    _manifest_cache = manifest
    return manifest


def clear_cache() -> None:
    """Reset the discovery and manifest caches (useful for testing)."""
    global _discovered_classes, _manifest_cache
    _discovered_classes = []
    _manifest_cache = None
