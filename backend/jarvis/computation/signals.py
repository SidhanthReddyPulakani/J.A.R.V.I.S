from dataclasses import dataclass
from enum import Enum


class DemandSignalStatus(str, Enum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DemandSignal:
    """
    One observation about the computational demand of the
    current reasoning cycle.

    Signals describe observations only. They do not prescribe
    computation actions.
    """

    name: str
    value: object | None = None

    status: DemandSignalStatus = (
        DemandSignalStatus.UNKNOWN
    )


@dataclass
class DemandSignals:
    """
    Collection of demand observations for one controller
    evaluation boundary.
    """

    # Goal
    goal_resolution: DemandSignal = DemandSignal(
        name="goal_resolution"
    )
    goal_progress: DemandSignal = DemandSignal(
        name="goal_progress"
    )
    unresolved_requirements: DemandSignal = DemandSignal(
        name="unresolved_requirements"
    )

    # Uncertainty
    intent_ambiguity: DemandSignal = DemandSignal(
        name="intent_ambiguity"
    )
    action_ambiguity: DemandSignal = DemandSignal(
        name="action_ambiguity"
    )
    target_ambiguity: DemandSignal = DemandSignal(
        name="target_ambiguity"
    )
    decision_confidence: DemandSignal = DemandSignal(
        name="decision_confidence"
    )

    # Information
    information_sufficiency: DemandSignal = DemandSignal(
        name="information_sufficiency"
    )
    missing_information: DemandSignal = DemandSignal(
        name="missing_information"
    )
    evidence_sufficiency: DemandSignal = DemandSignal(
        name="evidence_sufficiency"
    )
    evidence_conflict: DemandSignal = DemandSignal(
        name="evidence_conflict"
    )

    # Execution
    tool_execution_status: DemandSignal = DemandSignal(
        name="tool_execution_status"
    )
    tool_failure_count: DemandSignal = DemandSignal(
        name="tool_failure_count"
    )
    operation_repetition: DemandSignal = DemandSignal(
        name="operation_repetition"
    )
    tool_dependency_depth: DemandSignal = DemandSignal(
        name="tool_dependency_depth"
    )

    # Reasoning
    reasoning_step: DemandSignal = DemandSignal(
        name="reasoning_step"
    )
    reasoning_progress: DemandSignal = DemandSignal(
        name="reasoning_progress"
    )
    reasoning_repetition: DemandSignal = DemandSignal(
        name="reasoning_repetition"
    )
    decision_instability: DemandSignal = DemandSignal(
        name="decision_instability"
    )

    # Resources
    context_pressure: DemandSignal = DemandSignal(
        name="context_pressure"
    )
    elapsed_computation: DemandSignal = DemandSignal(
        name="elapsed_computation"
    )
    budget_remaining: DemandSignal = DemandSignal(
        name="budget_remaining"
    )

    def get(self, name: str) -> DemandSignal | None:
        """
        Retrieve a signal by its canonical name.
        """

        signal = getattr(
            self,
            name,
            None,
        )

        if isinstance(signal, DemandSignal):
            return signal

        return None

    def available(self) -> dict[str, DemandSignal]:
        """
        Return signals that currently contain usable observations.
        """

        result: dict[str, DemandSignal] = {}

        for name, signal in self.__dict__.items():

            if (
                isinstance(signal, DemandSignal)
                and signal.status
                == DemandSignalStatus.AVAILABLE
            ):
                result[name] = signal

        return result