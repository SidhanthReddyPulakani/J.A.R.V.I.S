from dataclasses import dataclass, field
from enum import Enum

from jarvis.computation.profile import ComputationMode


class ComputationAction(str, Enum):
    CONTINUE = "continue"
    ESCALATE = "escalate"
    DEESCALATE = "deescalate"
    FINISH = "finish"
    ABORT = "abort"


@dataclass(frozen=True)
class ComputationDecision:
    """
    Result produced by the computation policy.

    current_mode describes the mode before this decision.
    next_mode describes the mode to use after this decision.
    """

    action: ComputationAction
    current_mode: ComputationMode
    next_mode: ComputationMode | None = None

    reason: str = ""

    signals_used: tuple[str, ...] = field(
        default_factory=tuple
    )

    @property
    def terminal(self) -> bool:
        return self.action in {
            ComputationAction.FINISH,
            ComputationAction.ABORT,
        }