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
    The ComputationController decides which profile should
    be used. Runtime-specific adapters interpret it later.
    """

    mode: ComputationMode

    prompt_profile: str
    thinking_policy: str

    context_budget: int | None = None
    output_budget: int | None = None

    model_options: dict[str, Any] = field(
        default_factory=dict
    )