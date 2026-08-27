"""
Context source abstractions.

Sources provide information to the Context Compiler.

They do not own persistence.
"""

from typing import Any, Protocol


class ContextSource(Protocol):
    """
    Interface for a source of context information.
    """

    name: str

    def get(
        self,
        request: Any,
    ) -> list[Any]:
        ...