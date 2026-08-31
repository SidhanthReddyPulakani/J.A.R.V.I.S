"""
Provider-independent observation contract for Agent operations.

An observation associates a model-requested operation with the
OperationResult produced by executing it.

This module does not execute operations and does not decide
whether the Agent should continue reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.memory.operation_results import OperationResult


@dataclass(frozen=True)
class AgentOperationObservation:
    """
    The observable outcome of one Agent-requested operation.
    """

    tool_call_id: str | None
    operation: str
    result: OperationResult


__all__ = [
    "AgentOperationObservation",
]