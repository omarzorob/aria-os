"""
Context window management — keeps conversation history within token limits
while preserving the most relevant turns.
"""

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["user", "assistant"]
MAX_TOKENS = 180_000   # Claude's context window (leave headroom for tools/system)
AVG_CHARS_PER_TOKEN = 4


@dataclass
class Turn:
    role: Role
    content: str | list  # str for text, list for tool use blocks

    def token_estimate(self) -> int:
        text = self.content if isinstance(self.content, str) else str(self.content)
        return len(text) // AVG_CHARS_PER_TOKEN


@dataclass
class ConversationContext:
    turns: list[Turn] = field(default_factory=list)
    max_tokens: int = MAX_TOKENS

    def add(self, role: Role, content: str | list):
        self.turns.append(Turn(role=role, content=content))
        self._trim()

    def _trim(self):
        """Drop oldest turns when over token budget. Always keep last 4 turns."""
        while self._total_tokens() > self.max_tokens and len(self.turns) > 4:
            self.turns.pop(0)

    def _total_tokens(self) -> int:
        return sum(t.token_estimate() for t in self.turns)

    def to_messages(self) -> list[dict]:
        """Format for Anthropic API."""
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def clear(self):
        self.turns.clear()

    def summary(self) -> str:
        return f"{len(self.turns)} turns, ~{self._total_tokens():,} tokens"
