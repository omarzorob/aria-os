"""
P2-7: Aria Tool Execution Engine

Safely executes tool calls from the LLM with argument validation,
rate limiting, error isolation, and timing telemetry.

Usage:
    executor = ToolExecutor(tool_registry)
    result = await executor.execute(tool_call)
    results = await executor.execute_batch(tool_calls)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default rate limit: max calls per tool per minute
DEFAULT_RATE_LIMIT = 30  # calls/minute


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolResult:
    """Result of a single tool execution."""

    tool_name: str
    result: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    call_id: str = ""

    @property
    def succeeded(self) -> bool:
        """True if the tool ran without error."""
        return self.error is None

    def to_dict(self) -> dict:
        """Convert to a serialisable dict."""
        return {
            "tool_name": self.tool_name,
            "result": str(self.result) if self.result is not None else None,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "call_id": self.call_id,
        }

    def to_llm_content(self) -> str:
        """Format the result as text for feeding back to the LLM."""
        if self.error:
            return f"[Tool error: {self.error}]"
        if self.result is None:
            return "[Tool returned no result]"
        return str(self.result)


# ---------------------------------------------------------------------------
# Tool Executor
# ---------------------------------------------------------------------------


class ToolExecutor:
    """
    Safe, rate-limited tool execution engine.

    Wraps each tool call in error handling and measures execution time.
    Supports both sequential and batched (concurrent) execution.
    """

    def __init__(
        self,
        tool_registry: Any,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT,
    ) -> None:
        """
        Initialize the executor.

        Args:
            tool_registry: Object with a `get(name)` method returning tool instances,
                           or a dict mapping tool names to instances.
            rate_limit_per_minute: Maximum calls per tool per minute.
        """
        self._registry = tool_registry
        self._rate_limit = rate_limit_per_minute
        # Track call timestamps per tool for rate limiting: {tool_name: deque[timestamp]}
        self._call_log: dict[str, deque] = defaultdict(lambda: deque())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, tool_call: Any) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            tool_call: Object with `.name`, `.arguments` (dict), and
                       optionally `.call_id`.

        Returns:
            ToolResult with the output or error info and timing.
        """
        name = getattr(tool_call, "name", None) or tool_call.get("name", "unknown")
        arguments = getattr(tool_call, "arguments", None) or tool_call.get("arguments", {})
        call_id = getattr(tool_call, "call_id", "") or tool_call.get("call_id", "")

        # Validate arguments
        if not self.validate_args(tool_call):
            return ToolResult(
                tool_name=name,
                result=None,
                error=f"Invalid arguments for tool '{name}'",
                call_id=call_id,
            )

        # Rate limit check
        if not self._rate_limit_ok(name):
            return ToolResult(
                tool_name=name,
                result=None,
                error=f"Rate limit exceeded for tool '{name}' — max {self._rate_limit}/min",
                call_id=call_id,
            )

        # Get the tool instance
        tool = self._get_tool(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                result=None,
                error=f"Unknown tool: '{name}'",
                call_id=call_id,
            )

        # Execute with timing and error isolation
        start = time.perf_counter()
        try:
            self._record_call(name)
            # Support both sync and async execute methods
            if asyncio.iscoroutinefunction(getattr(tool, "execute", None)):
                result = await tool.execute(**arguments)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: tool.execute(**arguments))

            duration_ms = (time.perf_counter() - start) * 1000
            logger.info("Tool %s completed in %.1fms", name, duration_ms)
            return ToolResult(
                tool_name=name,
                result=result,
                duration_ms=duration_ms,
                call_id=call_id,
            )

        except TypeError as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            error_msg = f"Bad arguments for {name}: {exc}"
            logger.warning(error_msg)
            return ToolResult(
                tool_name=name,
                result=None,
                error=error_msg,
                duration_ms=duration_ms,
                call_id=call_id,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception("Tool %s raised an exception: %s", name, exc)
            return ToolResult(
                tool_name=name,
                result=None,
                error=error_msg,
                duration_ms=duration_ms,
                call_id=call_id,
            )

    async def execute_batch(self, tool_calls: list[Any]) -> list[ToolResult]:
        """
        Execute multiple tool calls concurrently.

        Args:
            tool_calls: List of tool call objects.

        Returns:
            List of ToolResult objects in the same order as the input.
        """
        if not tool_calls:
            return []

        logger.info("Executing batch of %d tool calls", len(tool_calls))
        tasks = [self.execute(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    def validate_args(self, tool_call: Any) -> bool:
        """
        Validate tool call arguments against the tool's input schema.

        Checks that all required fields are present and non-None.
        Type checking is not enforced (the LLM is trusted for types).

        Args:
            tool_call: Tool call object with name and arguments.

        Returns:
            True if arguments are valid, False otherwise.
        """
        name = getattr(tool_call, "name", None) or tool_call.get("name", "")
        arguments = getattr(tool_call, "arguments", None) or tool_call.get("arguments", {})

        if not isinstance(arguments, dict):
            logger.warning("Tool %s: arguments must be a dict, got %s", name, type(arguments))
            return False

        tool = self._get_tool(name)
        if tool is None:
            return True  # Can't validate unknown tool — will fail at execution

        # Get schema from tool instance
        schema: dict = {}
        if hasattr(tool, "input_schema"):
            schema = tool.input_schema or {}

        required_fields: list[str] = schema.get("required", [])
        for field_name in required_fields:
            if field_name not in arguments:
                logger.warning("Tool %s: missing required argument '%s'", name, field_name)
                return False
            if arguments[field_name] is None:
                logger.warning("Tool %s: required argument '%s' is None", name, field_name)
                return False

        return True

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limit_ok(self, tool_name: str) -> bool:
        """
        Check whether a tool call is within the rate limit.

        Uses a sliding 60-second window.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if the call is allowed.
        """
        now = time.time()
        window_start = now - 60.0
        calls = self._call_log[tool_name]

        # Remove calls outside the window
        while calls and calls[0] < window_start:
            calls.popleft()

        return len(calls) < self._rate_limit

    def _record_call(self, tool_name: str) -> None:
        """Record a call timestamp for rate limiting."""
        self._call_log[tool_name].append(time.time())

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    def _get_tool(self, name: str) -> Optional[Any]:
        """Retrieve a tool instance from the registry."""
        if isinstance(self._registry, dict):
            return self._registry.get(name)
        if hasattr(self._registry, "get"):
            return self._registry.get(name)
        return None

    def get_call_stats(self) -> dict:
        """Return current call stats per tool for monitoring."""
        now = time.time()
        window_start = now - 60.0
        stats: dict[str, int] = {}
        for name, calls in self._call_log.items():
            recent = sum(1 for t in calls if t >= window_start)
            if recent > 0:
                stats[name] = recent
        return stats
