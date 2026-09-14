from __future__ import annotations

from enum import Enum


class ReasoningState(str, Enum):
    GENERATING = "generating"
    COMMIT = "commit"
    COMPLETE = "complete"
    CONTINUE = "continue"
    INTERVENE = "intervene"
    ABORT = "abort"


class ReasoningController:
    """
    Deterministic reasoning-control state machine.

    Phase 7 adds one bounded stagnation intervention.
    The controller does not decide whether a trajectory is
    stagnant; StagnationDetector owns that observation.
    """

    def __init__(self) -> None:
        self.state: ReasoningState | None = None
        self.intervention_count = 0
        self.max_interventions = 1

    def start_generation(self) -> ReasoningState:
        if self.state not in (
            None,
            ReasoningState.COMMIT,
            ReasoningState.CONTINUE,
            ReasoningState.INTERVENE,
        ):
            raise RuntimeError(
                "Cannot start generation from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.GENERATING
        return self.state

    def continue_after_evidence(
        self,
        *,
        task_unresolved: bool,
    ) -> ReasoningState:
        if self.state != ReasoningState.COMMIT:
            raise RuntimeError(
                "Can only evaluate continuation after "
                f"COMMIT, currently "
                f"{self.state.value if self.state else 'START'}."
            )

        if task_unresolved:
            self.state = ReasoningState.CONTINUE
        else:
            self.state = ReasoningState.COMPLETE

        return self.state

    def observe(
        self,
        *,
        actionable_tool_call: bool = False,
        final_answer: bool = False,
        ceiling_reached: bool = False,
    ) -> ReasoningState:
        if self.state != ReasoningState.GENERATING:
            current_state = (
                self.state.value
                if self.state is not None
                else "START"
            )

            raise RuntimeError(
                "Can only observe generation while in "
                f"GENERATING, currently {current_state}."
            )

        if actionable_tool_call:
            self.state = ReasoningState.COMMIT
            return self.state

        if final_answer:
            self.state = ReasoningState.COMPLETE
            return self.state

        if ceiling_reached:
            self.state = ReasoningState.ABORT
            return self.state

        raise RuntimeError(
            "Generation produced no recognized terminal transition."
        )

    def intervene(self) -> ReasoningState:
        """
        Request one bounded recovery cycle after stagnation.

        A second intervention is not permitted. The caller should
        abort rather than allowing an unbounded reasoning loop.
        """

        if self.state != ReasoningState.GENERATING:
            raise RuntimeError(
                "Can only intervene from GENERATING, currently "
                f"{self.state.value if self.state else 'START'}."
            )

        if self.intervention_count >= self.max_interventions:
            self.state = ReasoningState.ABORT
            return self.state

        self.intervention_count += 1
        self.state = ReasoningState.INTERVENE

        return self.state

    def commit(self) -> ReasoningState:
        if self.state != ReasoningState.GENERATING:
            raise RuntimeError(
                "Cannot commit from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.COMMIT
        return self.state

    def complete(self) -> ReasoningState:
        if self.state != ReasoningState.GENERATING:
            raise RuntimeError(
                "Cannot complete from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.COMPLETE
        return self.state

    def abort(self) -> ReasoningState:
        if self.state not in (
            ReasoningState.GENERATING,
            ReasoningState.COMMIT,
            ReasoningState.INTERVENE,
        ):
            raise RuntimeError(
                "Cannot abort from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.ABORT
        return self.state


__all__ = [
    "ReasoningState",
    "ReasoningController",
]