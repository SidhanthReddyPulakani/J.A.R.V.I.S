"""
P8 — Formal contract for one Agent-requested operation.

This module defines the normalized request shape used for every
operation the Agent asks something to perform during the reasoning
loop (P7) — regardless of whether that operation is ultimately
handled by the Agent Memory Operation surface (P1) or an existing
application tool (jarvis.core.tools), and regardless of which real
Capability eventually owns it once the Capability Controller (P12)
exists.

Today there are two separate hand-rolled registries an operation
name can resolve against. P8 does not remove that split — that is
P12's job. P8 only guarantees that whichever registry ends up
handling a request, the Agent Execution Loop hands it a single,
normalized object instead of a raw (name, args) pair, and gets back
the one true result shape (`OperationResult`, defined in
`jarvis.memory.operation_results`) no matter which registry ran it.

This module intentionally contains no dispatch, execution,
persistence, or LLM logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis.core.agent_turn import AgentToolCall


@dataclass(frozen=True)
class CapabilityRequest:
    """
    Normalized request for one Agent-requested operation.

    `operation` is the operation name exactly as requested by the
    model (e.g. "open_application", "memory_replace_core"). This is
    the same string used today for the `if name in {...}` dispatch
    in `agent.run()` — P8 formalizes it, P12 will use it as the
    real `capability.operation` addressing key.

    `arguments` are the raw arguments requested by the model,
    already normalized into a plain dict by `AgentToolCall`.

    `invocation_id` ties this request back to the originating
    `AgentToolCall.id`, when the provider supplied one. This is the
    "invocation metadata" P8 is responsible for introducing — it
    lets a future Controller (or the execution trace) correlate a
    request with its originating model tool call even after the
    result has been converted into an `OperationResult`, which has
    no such identifier of its own.

    `step` is the reasoning-loop step (1-indexed) this request was
    made during, matching `AgentTraceStep.step`. This is the second
    piece of invocation metadata: it lets a later consumer of the
    execution trace (P7.10 — the visual execution trace) reconstruct
    which step produced which request without re-deriving it from
    trace ordering.
    """

    operation: str
    arguments: dict[str, Any]
    invocation_id: str | None = None
    step: int | None = None

    @classmethod
    def from_tool_call(
        cls,
        call: AgentToolCall,
        step: int,
    ) -> "CapabilityRequest":
        """
        Build a CapabilityRequest from a provider-normalized
        AgentToolCall produced during a given reasoning-loop step.

        This is the one place an AgentToolCall becomes a
        CapabilityRequest, so every operation entering execution —
        memory operation or application tool alike — passes through
        the same construction path.
        """

        return cls(
            operation=call.name,
            arguments=dict(
                call.arguments
            ),
            invocation_id=call.id,
            step=step,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the request into a transport-safe dictionary.

        Mirrors `OperationResult.to_dict()` so a request and its
        eventual result can travel together through a future
        Agent/Controller protocol without depending on internal
        service objects.
        """

        return {
            "operation": self.operation,
            "arguments": self.arguments,
            "invocation_id": self.invocation_id,
            "step": self.step,
        }


__all__ = [
    "CapabilityRequest",
]