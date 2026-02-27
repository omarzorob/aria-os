"""
P2-5: Aria Session Memory

Manages conversation history for ongoing sessions with token budgeting,
summarization for long conversations, and JSON persistence.

Uses tiktoken for accurate token counting when available; falls back to a
character-based estimate (1 token ≈ 4 characters).

Usage:
    mem = SessionMemory()
    mem.add_message("user", "Hey Aria, what's the weather?")
    mem.add_message("assistant", "72°F and sunny.")
    window = mem.get_context_window(max_tokens=4000)
    mem.save("/tmp/session.json")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Attempt to load tiktoken for accurate token counting
try:
    import tiktoken  # type: ignore

    _TIKTOKEN_AVAILABLE = True
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")  # Works for GPT-4 and Claude
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _TOKENIZER = None  # type: ignore

CHARS_PER_TOKEN = 4  # Rough estimate when tiktoken is unavailable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single conversation message."""

    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: float = 0.0
    tokens: int = 0  # Populated on add

    def to_dict(self) -> dict:
        """Convert to LLM-compatible dict (without internal fields)."""
        return {"role": self.role, "content": self.content}

    def to_full_dict(self) -> dict:
        """Convert to full dict including metadata (for persistence)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Session Memory
# ---------------------------------------------------------------------------


class SessionMemory:
    """
    Session-scoped conversation memory with token budgeting.

    Attributes:
        max_history: Hard limit on stored messages before old ones are dropped.
        _messages: Internal list of Message objects.
    """

    def __init__(self, max_history: int = 100) -> None:
        """
        Initialize an empty session memory.

        Args:
            max_history: Maximum number of messages to keep in memory.
                         Oldest messages are dropped when the limit is exceeded.
        """
        self.max_history = max_history
        self._messages: list[Message] = []

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: "user", "assistant", or "system".
            content: Message text.
        """
        tokens = self._count_tokens(content)
        msg = Message(role=role, content=content, timestamp=time.time(), tokens=tokens)
        self._messages.append(msg)

        # Trim history if over the hard limit
        if len(self._messages) > self.max_history:
            overflow = len(self._messages) - self.max_history
            self._messages = self._messages[overflow:]
            logger.debug("Trimmed %d old message(s) from session memory", overflow)

    def get_history(self, max_turns: int = 20) -> list[dict]:
        """
        Return the most recent messages in LLM-compatible format.

        Args:
            max_turns: Maximum number of messages to return (pairs = 2x exchanges).

        Returns:
            List of {"role": ..., "content": ...} dicts, newest last.
        """
        recent = self._messages[-max_turns:] if max_turns else self._messages
        return [m.to_dict() for m in recent]

    def get_context_window(self, max_tokens: int = 4000) -> list[dict]:
        """
        Return messages that fit within a token budget, newest-first priority.

        Iterates from most-recent backwards, collecting messages until the
        token budget is exhausted. Always includes at least the last message.

        Args:
            max_tokens: Maximum token budget for the context window.

        Returns:
            List of {"role": ..., "content": ...} dicts in chronological order.
        """
        if not self._messages:
            return []

        selected: list[Message] = []
        used_tokens = 0

        for msg in reversed(self._messages):
            msg_tokens = msg.tokens or self._count_tokens(msg.content)
            if used_tokens + msg_tokens > max_tokens and selected:
                break  # Budget exceeded — but keep at least one message
            selected.append(msg)
            used_tokens += msg_tokens

        # Reverse back to chronological order
        selected.reverse()
        logger.debug(
            "Context window: %d/%d messages, ~%d tokens",
            len(selected),
            len(self._messages),
            used_tokens,
        )
        return [m.to_dict() for m in selected]

    def clear(self) -> None:
        """Reset the session — removes all conversation history."""
        self._messages.clear()
        logger.info("Session memory cleared")

    def summarize(self) -> str:
        """
        Condense older messages to save tokens.

        Keeps the most recent 10 messages verbatim and replaces older
        messages with a single summary placeholder. Returns the summary text.

        In production, this should call the LLM to generate a real summary.
        For now it creates a structured text summary of the dropped messages.

        Returns:
            Summary text of condensed messages.
        """
        keep_recent = 10

        if len(self._messages) <= keep_recent:
            return ""  # Nothing to summarize

        older = self._messages[:-keep_recent]
        recent = self._messages[-keep_recent:]

        # Build a simple summary
        lines = [f"[Conversation summary — {len(older)} earlier messages]"]
        for msg in older:
            role_label = "User" if msg.role == "user" else "Aria"
            snippet = msg.content[:100] + ("…" if len(msg.content) > 100 else "")
            lines.append(f"  {role_label}: {snippet}")

        summary_text = "\n".join(lines)

        # Replace older messages with a single system summary message
        summary_msg = Message(
            role="system",
            content=summary_text,
            timestamp=time.time(),
            tokens=self._count_tokens(summary_text),
        )
        self._messages = [summary_msg] + recent

        logger.info("Summarized %d messages → 1 summary + %d recent", len(older), len(recent))
        return summary_text

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """
        Persist the session to a JSON file.

        Args:
            path: File path to write to (created if absent).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "saved_at": time.time(),
            "max_history": self.max_history,
            "messages": [m.to_full_dict() for m in self._messages],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Session saved to %s (%d messages)", path, len(self._messages))

    def load(self, path: str | Path) -> None:
        """
        Load a session from a JSON file.

        Args:
            path: File path to read from.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Session file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "messages" not in data:
            raise ValueError(f"Invalid session file format: {path}")

        self._messages = []
        for m in data["messages"]:
            self._messages.append(
                Message(
                    role=m["role"],
                    content=m["content"],
                    timestamp=m.get("timestamp", 0.0),
                    tokens=m.get("tokens", 0),
                )
            )

        self.max_history = data.get("max_history", self.max_history)
        logger.info("Session loaded from %s (%d messages)", path, len(self._messages))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def message_count(self) -> int:
        """Number of messages in the current session."""
        return len(self._messages)

    @property
    def total_tokens(self) -> int:
        """Estimated total tokens across all stored messages."""
        return sum(m.tokens for m in self._messages)

    def stats(self) -> dict:
        """Return a summary stats dict for the status endpoint."""
        return {
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "max_history": self.max_history,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Uses tiktoken if available, otherwise estimates at 4 chars/token.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        if _TIKTOKEN_AVAILABLE and _TOKENIZER is not None:
            try:
                return len(_TOKENIZER.encode(text))
            except Exception:
                pass
        return max(1, len(text) // CHARS_PER_TOKEN)
