from dataclasses import dataclass, field
from enum import Enum
from time import monotonic

from jarvis.computation.decision import (
    ComputationAction,
    ComputationDecision,
)
from jarvis.computation.profile import ComputationMode
from jarvis.computation.signals import DemandSignals


class ComputationPhase(str, Enum):
    INITIAL = "initial"
    PRE_LLM = "pre_llm"
    POST_LLM = "post_llm"
    POST_EXECUTION = "post_execution"
    COMPLETION = "completion"


@dataclass
class ComputationState:
    """
    Transient computational state for one Agent request.

    This state describes the computation trajectory only.
    It does not replace or own Agent State, Memory,
    Knowledge, Context, or Operation Results.
    """

    mode: ComputationMode = ComputationMode.NORMAL

    phase: ComputationPhase = (
        ComputationPhase.INITIAL
    )

    reasoning_step: int = 0

    started_at: float = field(
        default_factory=monotonic
    )

    previous_mode: ComputationMode | None = None

    previous_action: ComputationAction | None = None

    last_decision: ComputationDecision | None = None

    last_signals: DemandSignals | None = None

    transition_count: int = 0

    escalation_count: int = 0

    deescalation_count: int = 0

    tool_failure_count: int = 0

    operation_repetition_count: int = 0

    reasoning_repetition_count: int = 0

    decision_instability_count: int = 0

    progress_delta: float | None = None

    terminal: bool = False

    aborted: bool = False

    def elapsed_seconds(self) -> float:
        return max(
            0.0,
            monotonic() - self.started_at,
        )

    def transition_to(
        self,
        mode: ComputationMode,
        action: ComputationAction | None = None,
    ) -> None:
        """
        Record a computation-mode transition.
        """

        if mode != self.mode:

            self.previous_mode = self.mode

            self.mode = mode

            self.transition_count += 1

        if action is not None:

            self.previous_action = action

            if action == ComputationAction.ESCALATE:
                self.escalation_count += 1

            elif action == ComputationAction.DEESCALATE:
                self.deescalation_count += 1

    def apply_decision(
        self,
        decision: ComputationDecision,
    ) -> None:
        """
        Apply a controller decision to this transient state.
        """

        self.last_decision = decision

        self.previous_action = decision.action

        if decision.next_mode is not None:

            self.transition_to(
                mode=decision.next_mode,
                action=decision.action,
            )

        if decision.terminal:

            self.terminal = True

            self.aborted = (
                decision.action
                == ComputationAction.ABORT
            )

    def advance_reasoning_step(self) -> None:
        self.reasoning_step += 1