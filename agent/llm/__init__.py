"""
agent/llm — LLM client package for Aria OS.

Exports:
    LLMClient    — unified Anthropic / OpenAI client
    LLMResponse  — structured response dataclass
    ToolCall     — tool call dataclass
    SYSTEM_PROMPT — Aria's personality and instructions
"""

from agent.llm.client import LLMClient, LLMResponse, ToolCall
from agent.llm.prompts import SYSTEM_PROMPT

__all__ = ["LLMClient", "LLMResponse", "ToolCall", "SYSTEM_PROMPT"]
