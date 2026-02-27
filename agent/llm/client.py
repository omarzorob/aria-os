"""
P2-3: Aria LLM Client

Unified LLM client that supports both OpenAI and Anthropic APIs with
structured tool calling. Auto-selects provider based on available API keys.

Environment variables:
    ANTHROPIC_API_KEY: Use Anthropic Claude (preferred)
    OPENAI_API_KEY: Use OpenAI GPT (fallback)
    ARIA_LLM_MODEL: Override the default model name

Usage:
    client = LLMClient()
    response = await client.complete(messages, tools=tools)
    tool_calls = client.parse_tool_calls(response)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# Default models per provider
ANTHROPIC_DEFAULT_MODEL = "claude-opus-4-6"
OPENAI_DEFAULT_MODEL = "gpt-4o"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """Represents a single tool call requested by the LLM."""

    name: str
    arguments: dict[str, Any]
    call_id: str = ""


@dataclass
class LLMResponse:
    """Structured response from an LLM completion."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_used: int = 0
    model: str = ""
    stop_reason: str = ""

    @property
    def has_tool_calls(self) -> bool:
        """True if the response contains at least one tool call."""
        return len(self.tool_calls) > 0


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------


class LLMClient:
    """
    Unified LLM client for Anthropic Claude and OpenAI GPT.

    Automatically selects the provider based on available API keys.
    Supports both synchronous-style complete() and async streaming.
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """
        Initialize the LLM client.

        Args:
            anthropic_api_key: Override ANTHROPIC_API_KEY env var.
            openai_api_key: Override OPENAI_API_KEY env var.
            model: Override the default model for the selected provider.
        """
        self._anthropic_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model_override = model or os.environ.get("ARIA_LLM_MODEL", "")

        # Determine provider
        if self._anthropic_key:
            self._provider = "anthropic"
            self._model = self._model_override or ANTHROPIC_DEFAULT_MODEL
        elif self._openai_key:
            self._provider = "openai"
            self._model = self._model_override or OPENAI_DEFAULT_MODEL
        else:
            logger.warning("No API key found — LLM calls will fail at runtime")
            self._provider = "anthropic"  # Default; will error on use
            self._model = self._model_override or ANTHROPIC_DEFAULT_MODEL

        logger.info("LLMClient using provider=%s model=%s", self._provider, self._model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            messages: Conversation history in OpenAI format
                      [{"role": "user"|"assistant", "content": "..."}].
            tools: Optional list of tool schemas in Anthropic or OpenAI format.
            system: Optional system prompt override.
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with content, tool_calls, and usage stats.
        """
        if self._provider == "anthropic":
            return await self._complete_anthropic(messages, tools, system, max_tokens)
        else:
            return await self._complete_openai(messages, tools, system, max_tokens)

    async def stream_complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Stream a completion response token by token.

        Args:
            messages: Conversation history.
            tools: Optional tool schemas.
            system: Optional system prompt.
            max_tokens: Maximum tokens.

        Yields:
            Text chunks as they arrive from the LLM.
        """
        if self._provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, tools, system, max_tokens):
                yield chunk
        else:
            async for chunk in self._stream_openai(messages, tools, system, max_tokens):
                yield chunk

    def parse_tool_calls(self, response: LLMResponse) -> list[ToolCall]:
        """
        Extract tool calls from an LLMResponse.

        Args:
            response: LLMResponse object.

        Returns:
            List of ToolCall objects (may be empty).
        """
        return list(response.tool_calls)

    # ------------------------------------------------------------------
    # Anthropic implementation
    # ------------------------------------------------------------------

    async def _complete_anthropic(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str | None,
        max_tokens: int,
    ) -> LLMResponse:
        """Call Anthropic Claude API."""
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError("anthropic package not installed: pip install anthropic") from exc

        client = anthropic.Anthropic(api_key=self._anthropic_key)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        def _sync_call() -> anthropic.types.Message:
            return client.messages.create(**kwargs)

        loop = asyncio.get_event_loop()
        raw: anthropic.types.Message = await loop.run_in_executor(None, _sync_call)

        content_text = ""
        tool_calls: list[ToolCall] = []

        for block in raw.content:
            if hasattr(block, "text"):
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block.name,
                        arguments=dict(block.input),
                        call_id=block.id,
                    )
                )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            tokens_used=(raw.usage.input_tokens + raw.usage.output_tokens),
            model=raw.model,
            stop_reason=raw.stop_reason or "",
        )

    async def _stream_anthropic(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str | None,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Stream from Anthropic Claude API."""
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError("anthropic package not installed") from exc

        client = anthropic.Anthropic(api_key=self._anthropic_key)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        # Anthropic streaming is synchronous; run in executor and yield chunks
        collected: list[str] = []

        def _stream_sync() -> None:
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    collected.append(text)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stream_sync)

        for chunk in collected:
            yield chunk

    # ------------------------------------------------------------------
    # OpenAI implementation
    # ------------------------------------------------------------------

    async def _complete_openai(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str | None,
        max_tokens: int,
    ) -> LLMResponse:
        """Call OpenAI API."""
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package not installed: pip install openai") from exc

        client = openai.OpenAI(api_key=self._openai_key)

        # Prepend system message if provided
        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": msgs,
        }
        if tools:
            # Convert Anthropic-style tool schemas to OpenAI format if needed
            kwargs["tools"] = [_anthropic_to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        def _sync_call():
            return client.chat.completions.create(**kwargs)

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, _sync_call)

        choice = raw.choices[0]
        content_text = choice.message.content or ""
        tool_calls: list[ToolCall] = []

        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append(
                    ToolCall(
                        name=tc.function.name,
                        arguments=args,
                        call_id=tc.id,
                    )
                )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            tokens_used=raw.usage.total_tokens if raw.usage else 0,
            model=raw.model,
            stop_reason=choice.finish_reason or "",
        )

    async def _stream_openai(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        system: str | None,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Stream from OpenAI API."""
        try:
            import openai  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc

        client = openai.OpenAI(api_key=self._openai_key)

        msgs = list(messages)
        if system:
            msgs = [{"role": "system", "content": system}] + msgs

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": msgs,
            "stream": True,
        }

        collected: list[str] = []

        def _stream_sync() -> None:
            with client.chat.completions.create(**kwargs) as stream:
                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        collected.append(delta)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stream_sync)

        for chunk in collected:
            yield chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _anthropic_to_openai_tool(tool: dict) -> dict:
    """
    Convert an Anthropic-format tool schema to OpenAI format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    if "input_schema" in tool:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"],
            },
        }
    # Already in OpenAI format
    return tool
