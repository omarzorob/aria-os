"""Base class for all Aria tools."""

from abc import ABC, abstractmethod
from typing import Any


class AriaTool(ABC):
    """Every Aria tool inherits from this."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (used by LLM to call it)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """What this tool does — shown to LLM."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON schema for tool inputs."""
        ...

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool. Returns result as string."""
        ...

    def to_anthropic_tool(self) -> dict:
        """Format for Claude's tool-use API."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
