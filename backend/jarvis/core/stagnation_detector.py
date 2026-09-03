from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StagnationObservation:
    repeated_content: bool
    repeated_tool_intent: bool
    no_new_action_information: bool
    repeated_self_correction: bool

    @property
    def stagnant(self) -> bool:
        signals = (
            self.repeated_content,
            self.repeated_tool_intent,
            self.no_new_action_information,
            self.repeated_self_correction,
        )

        return sum(signals) >= 2


class StagnationDetector:
    """
    Phase 7 v1.

    Detects observable repetition/stagnation.
    No embeddings or semantic similarity yet.
    """

    def __init__(self, window_size: int = 3) -> None:
        if window_size < 2:
            raise ValueError(
                "window_size must be at least 2"
            )

        self.window_size = window_size
        self._content_window: list[str] = []
        self._tool_intent_window: list[str] = []

    def observe(
        self,
        *,
        content: str = "",
        tool_intents: tuple[str, ...] = (),
        new_action_information: bool = True,
        self_correction: bool = False,
    ) -> StagnationObservation:

        normalized_content = " ".join(
            content.lower().split()
        )

        self._content_window.append(
            normalized_content
        )

        if len(self._content_window) > self.window_size:
            self._content_window.pop(0)

        for intent in tool_intents:
            self._tool_intent_window.append(
                intent
            )

        if len(self._tool_intent_window) > self.window_size:
            self._tool_intent_window = (
                self._tool_intent_window[
                    -self.window_size:
                ]
            )

        repeated_content = (
            len(self._content_window) >= 2
            and len(
                set(self._content_window[-2:])
            ) == 1
            and bool(normalized_content)
        )

        repeated_tool_intent = (
            len(self._tool_intent_window) >= 2
            and self._tool_intent_window[-1]
            == self._tool_intent_window[-2]
        )

        return StagnationObservation(
            repeated_content=repeated_content,
            repeated_tool_intent=repeated_tool_intent,
            no_new_action_information=(
                not new_action_information
            ),
            repeated_self_correction=(
                self_correction
            ),
        )

    def reset(self) -> None:
        self._content_window.clear()
        self._tool_intent_window.clear()