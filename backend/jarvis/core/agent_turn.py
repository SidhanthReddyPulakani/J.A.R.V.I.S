"""
Provider-independent contract for one Agent model turn.

This module defines the boundary between the LLM provider response
and the Agent execution runtime.

It intentionally contains no LLM calls, tool execution, persistence,
context assembly, or reasoning-loop logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentToolCall:
    """
    A normalized tool invocation requested by the model.
    """

    id: str | None
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentTurnResult:
    """
    Provider-independent result of one model turn.

    `assistant_message` contains the normalized assistant message
    that should become part of the Agent runtime conversation.

    `tool_calls` contains the executable operations requested by
    the model.

    A turn is considered complete when the model requested no
    further tool calls.
    """

    assistant_message: dict[str, Any]
    tool_calls: tuple[AgentToolCall, ...]

    @property
    def completed(self) -> bool:
        """
        Whether this turn represents model completion.

        Completion is determined by the absence of further tool
        calls rather than by a provider-specific finish reason.
        """
        return not self.tool_calls


__all__ = [
    "AgentToolCall",
    "AgentTurnResult",
]