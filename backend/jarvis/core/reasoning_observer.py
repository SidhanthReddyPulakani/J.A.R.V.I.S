from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReasoningObservation:
    """
    Observable properties of the current reasoning trajectory.

    This is deliberately not a confidence score.

    The observer measures evidence/progress/commit-readiness
    signals that can be used by the Agent runtime.
    """

    elapsed_ms: float
    total_chars: int
    new_chars: int

    action_signal: float
    uncertainty_signal: float
    repetition_signal: float

    commit_readiness: bool


class ReasoningObserver:
    """
    External observer for incremental model reasoning.

    The observer does not:
        - modify the LLM prompt
        - generate additional LLM calls
        - decide whether an action is correct
        - execute tools
        - replace ReasoningController
        - claim calibrated confidence

    It only evaluates observable properties of the streamed
    reasoning trajectory.
    """

    ACTION_TERMS = (
        "open",
        "launch",
        "start",
        "run",
        "application",
        "app",
        "tool",
        "function",
        "query",
        "argument",
        "arguments",
    )

    UNCERTAINTY_TERMS = (
        "maybe",
        "perhaps",
        "might",
        "could",
        "not sure",
        "unclear",
        "i need to check",
        "let me verify",
        "i should verify",
        "i need to make sure",
    )

    def __init__(
        self,
        *,
        min_reasoning_chars: int = 200,
        min_action_signal: float = 0.01,
        max_uncertainty_signal: float = 0.20,
    ) -> None:
        if min_reasoning_chars < 0:
            raise ValueError(
                "min_reasoning_chars must be non-negative"
            )

        if not 0.0 <= min_action_signal <= 1.0:
            raise ValueError(
                "min_action_signal must be between 0 and 1"
            )

        if not 0.0 <= max_uncertainty_signal <= 1.0:
            raise ValueError(
                "max_uncertainty_signal must be between 0 and 1"
            )

        self.min_reasoning_chars = min_reasoning_chars
        self.min_action_signal = min_action_signal
        self.max_uncertainty_signal = max_uncertainty_signal

        self._previous_text = ""

    def reset(self) -> None:
        self._previous_text = ""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(
            text.lower().split()
        )

    @staticmethod
    def _term_density(
        text: str,
        terms: tuple[str, ...],
    ) -> float:
        if not text:
            return 0.0

        matches = sum(
            1
            for term in terms
            if term in text
        )

        return min(
            1.0,
            matches / max(len(terms), 1),
        )

    @staticmethod
    def _repetition_signal(
        text: str,
    ) -> float:
        if len(text) < 100:
            return 0.0

        words = text.split()

        if len(words) < 20:
            return 0.0

        unique_words = len(set(words))

        diversity = (
            unique_words / len(words)
        )

        return max(
            0.0,
            min(
                1.0,
                1.0 - diversity,
            ),
        )

    def observe(
        self,
        *,
        thinking: str,
        elapsed_ms: float,
    ) -> ReasoningObservation:
        normalized = self._normalize(
            thinking
        )

        previous = self._previous_text

        if previous and normalized.startswith(previous):
            new_text = normalized[
                len(previous):
            ]
        else:
            new_text = normalized

        self._previous_text = normalized

        action_signal = self._term_density(
            normalized,
            self.ACTION_TERMS,
        )

        uncertainty_signal = self._term_density(
            normalized,
            self.UNCERTAINTY_TERMS,
        )

        repetition_signal = (
            self._repetition_signal(
                normalized
            )
        )

        commit_readiness = (
            len(normalized)
            >= self.min_reasoning_chars
            and action_signal
            >= self.min_action_signal
            and uncertainty_signal
            < self.max_uncertainty_signal
        )

        return ReasoningObservation(
            elapsed_ms=elapsed_ms,
            total_chars=len(normalized),
            new_chars=len(new_text),
            action_signal=action_signal,
            uncertainty_signal=uncertainty_signal,
            repetition_signal=repetition_signal,
            commit_readiness=commit_readiness,
        )


__all__ = [
    "ReasoningObservation",
    "ReasoningObserver",
]