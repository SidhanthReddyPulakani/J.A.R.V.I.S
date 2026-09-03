from __future__ import annotations

from enum import Enum


class ReasoningState(str, Enum):
    GENERATING = "generating"
    COMMIT = "commit"
    COMPLETE = "complete"
    CONTINUE = "continue"
    ABORT = "abort"


class ReasoningController:
    """
    Deterministic reasoning-control state machine.

    Phase 5 deliberately contains no intelligence:
    - no confidence score
    - no stagnation detection
    - no evidence scoring
    - no continuation policy

    It only makes the existing Agent transitions explicit.
    """

    def __init__(self) -> None:
        self.state: ReasoningState | None = None

    def start_generation(self) -> ReasoningState:
        """
        Enter a model-generation cycle.
        """

        if self.state not in (
            None,
            ReasoningState.COMMIT,
            ReasoningState.CONTINUE,
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
        """
        Decide whether another reasoning cycle is justified
        by newly produced capability evidence.

        COMMIT -> CONTINUE when the task remains unresolved.
        COMMIT -> COMPLETE when the task is resolved.
        """

        if self.state != ReasoningState.COMMIT:
            raise RuntimeError(
                "Can only evaluate continuation after "
                f"COMMIT, currently {self.state.value if self.state else 'START'}."
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
        """
        Apply deterministic observations to the current
        generation cycle.
        """

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
    def commit(self) -> ReasoningState:
        """
        Explicitly transition to COMMIT.

        Convenience method for tests and callers that already
        determined the structured action is actionable.
        """

        if self.state != ReasoningState.GENERATING:
            raise RuntimeError(
                "Cannot commit from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.COMMIT
        return self.state

    def complete(self) -> ReasoningState:
        """
        Explicitly transition to COMPLETE.
        """

        if self.state != ReasoningState.GENERATING:
            raise RuntimeError(
                "Cannot complete from "
                f"{self.state.value}."
            )

        self.state = ReasoningState.COMPLETE
        return self.state

    def abort(self) -> ReasoningState:
        """
        Explicitly transition to ABORT.
        """

        if self.state not in (
            ReasoningState.GENERATING,
            ReasoningState.COMMIT,
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