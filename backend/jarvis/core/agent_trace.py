from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from jarvis.core.agent_observation import (
    AgentOperationObservation,
)


class AgentTerminationReason(str, Enum):
    MODEL_COMPLETED = "model_completed"
    MAX_STEPS_REACHED = "max_steps_reached"


@dataclass
class AgentTraceStep:
    step: int
    observations: list[
        AgentOperationObservation
    ] = field(default_factory=list)


@dataclass
class AgentExecutionTrace:
    steps: list[AgentTraceStep] = field(
        default_factory=list
    )
    termination_reason: (
        AgentTerminationReason | None
    ) = None

    def add_step(
        self,
        step: AgentTraceStep,
    ) -> None:
        self.steps.append(step)

    def terminate(
        self,
        reason: AgentTerminationReason,
    ) -> None:
        self.termination_reason = reason