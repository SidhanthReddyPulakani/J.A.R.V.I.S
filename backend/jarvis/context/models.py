"""
Context data models.

Context objects are temporary representations of the
information required for one reasoning step.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContextRequest:
    """
    Inputs available to the Context Compiler.

    Not every field has to be populated for every request.
    """

    user_input: str

    state: Any

    conversation: list[Any] = field(
        default_factory=list
    )

    working_memory: list[Any] = field(
        default_factory=list
    )

    memories: list[Any] = field(
        default_factory=list
    )

    diary: list[Any] = field(
        default_factory=list
    )

    knowledge: list[Any] = field(
        default_factory=list
    )

    relationships: list[Any] = field(
        default_factory=list
    )

    capability_information: list[Any] = field(
        default_factory=list
    )

    operation_results: list[Any] = field(
        default_factory=list
    )


@dataclass
class AgentContext:
    """
    Compiled context for one LLM reasoning step.

    This object is temporary and can be rebuilt at any time.
    """

    messages: list[dict[str, Any]] = field(
        default_factory=list
    )

    def as_messages(self) -> list[dict[str, Any]]:
        """
        Return a copy of the compiled messages.
        """

        return list(self.messages)