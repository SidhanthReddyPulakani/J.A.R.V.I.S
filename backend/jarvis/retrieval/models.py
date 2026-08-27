"""
Retrieval data models.

Retrieval is the information-discovery layer between
persistent information stores and Context.

A RetrievalResult is intentionally storage-agnostic.
The rest of Jarvis should not need to know whether a result
came from Recall, Memory, Knowledge, or Relationships.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    """
    One normalized retrieval result.

    Attributes:
        source:
            Logical retrieval source.

            Examples:
                recall
                memory
                knowledge
                relationship

        identifier:
            Identifier of the originating record when available.

        content:
            Human-readable information returned to the caller.

        score:
            Normalized relevance score.

        metadata:
            Additional source-specific information.
    """

    source: str

    identifier: Any

    content: str

    score: float

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError(
                "Retrieval result source cannot be empty."
            )

        if not self.content.strip():
            raise ValueError(
                "Retrieval result content cannot be empty."
            )

        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                "Retrieval result score must be "
                "between 0 and 1."
            )


@dataclass
class RetrievalRequest:
    """
    Request passed to the Retrieval service.

    sources:
        Optional list restricting which retrieval providers
        are queried.

        If None, all available providers are queried.

    limit:
        Maximum number of results returned globally.
    """

    query: str

    sources: list[str] | None = None

    limit: int = 10

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        if self.limit <= 0:
            raise ValueError(
                "Retrieval limit must be positive."
            )