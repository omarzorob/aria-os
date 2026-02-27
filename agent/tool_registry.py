"""
Aria Tool Registry — discovers and manages all available tools.
Tools are auto-registered on import.
"""

import importlib
import pkgutil
from typing import Dict
from agent.tools.base import AriaTool

_registry: Dict[str, AriaTool] = {}


def register(tool: AriaTool):
    _registry[tool.name] = tool


def get(name: str) -> AriaTool | None:
    return _registry.get(name)


def all_tools() -> list[AriaTool]:
    return list(_registry.values())


def anthropic_tools() -> list[dict]:
    """Return all tools formatted for Claude's tool-use API."""
    return [t.to_anthropic_tool() for t in _registry.values()]


def execute(tool_name: str, inputs: dict) -> str:
    tool = get(tool_name)
    if not tool:
        return f"Unknown tool: {tool_name}"
    try:
        return tool.execute(**inputs)
    except Exception as e:
        return f"Tool error ({tool_name}): {e}"


def load_all():
    """Auto-import all tool modules from agent/tools/."""
    import agent.tools as tools_pkg
    for _, module_name, _ in pkgutil.iter_modules(tools_pkg.__path__):
        if module_name != "base":
            importlib.import_module(f"agent.tools.{module_name}")
