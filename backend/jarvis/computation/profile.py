from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ComputationMode(str, Enum):
    FAST = "fast"
    NORMAL = "normal"
    DEEP = "deep"


@dataclass(frozen=True)
class ComputationProfile:
    """
    Describes how the next LLM computation should be performed.

    This is an execution profile, not a policy decision.

    The ComputationController decides the computation mode.
    Runtime-specific adapters interpret this profile.
    """

    mode: ComputationMode

    prompt_profile: str
    thinking_policy: str

    context_budget: int | None = None
    output_budget: int | None = None

    model_options: dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def from_mode(
        cls,
        mode: ComputationMode,
    ) -> "ComputationProfile":
        """
        Translate the controller's computation mode into the
        runtime-independent execution profile.

        No model-specific assumptions are made here.
        """

        if mode == ComputationMode.FAST:
            return cls(
                mode=mode,
                prompt_profile="fast",
                thinking_policy="disabled",
            )

        if mode == ComputationMode.NORMAL:
            return cls(
                mode=mode,
                prompt_profile="normal",
                thinking_policy="default",
            )

        return cls(
            mode=mode,
            prompt_profile="deep",
            thinking_policy="enabled",
        )