"""
Memory formation models.

These models represent the information moving through
the memory formation pipeline.

Pipeline:

    experience
        ↓
    candidate extraction
        ↓
    evaluation
        ↓
    create / update / discard
        ↓
    consolidation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jarvis.memory.models import LongTermMemory


class MemorySource(str, Enum):
    """Origin of a memory candidate."""

    USER = "user"
    CONVERSATION = "conversation"
    DIARY = "diary"
    AGENT = "agent"
    SYSTEM = "system"


class RetentionReason(str, Enum):
    """Reason information may deserve retention."""

    EXPLICIT_REQUEST = "explicit_request"
    PERSONAL_FACT = "personal_fact"
    PREFERENCE = "preference"
    PROJECT_CONTEXT = "project_context"
    REPEATED_INFORMATION = "repeated_information"
    IMPORTANT_EVENT = "important_event"
    CORRECTION = "correction"
    OTHER = "other"


class FormationAction(str, Enum):
    """Action selected by memory formation."""

    DISCARD = "discard"
    CREATE = "create"
    UPDATE = "update"


class ConsolidationAction(str, Enum):
    """Action selected by memory consolidation."""

    NONE = "none"
    MERGE = "merge"
    SUPERSEDE = "supersede"


@dataclass(frozen=True)
class MemoryCandidate:
    """
    A proposed Long-Term Memory.

    A candidate is not persistent by itself.
    """

    content: str

    source: MemorySource

    reason: RetentionReason

    confidence: float = 1.0

    importance: float = 0.5

    category: str | None = None

    subject: str | None = None

    project: str | None = None

    source_id: int | str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:

        if not self.content.strip():
            raise ValueError(
                "Memory candidate content "
                "cannot be empty."
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Memory candidate confidence "
                "must be between 0.0 and 1.0."
            )

        if not 0.0 <= self.importance <= 1.0:
            raise ValueError(
                "Memory candidate importance "
                "must be between 0.0 and 1.0."
            )

    def to_dict(self) -> dict[str, Any]:

        return {
            "content": self.content,
            "source": self.source.value,
            "reason": self.reason.value,
            "confidence": self.confidence,
            "importance": self.importance,
            "category": self.category,
            "subject": self.subject,
            "project": self.project,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class FormationDecision:
    """
    Result of evaluating a memory candidate.
    """

    action: FormationAction

    candidate: MemoryCandidate

    reason: str

    existing_memory: LongTermMemory | None = None

    def __post_init__(self) -> None:

        if (
            self.action
            == FormationAction.UPDATE
            and self.existing_memory is None
        ):
            raise ValueError(
                "UPDATE decisions require "
                "an existing memory."
            )

        if (
            self.action
            != FormationAction.UPDATE
            and self.existing_memory is not None
        ):
            raise ValueError(
                "Only UPDATE decisions may "
                "reference an existing memory."
            )


@dataclass(frozen=True)
class ConsolidationDecision:
    """
    Result of examining a group of existing memories.

    The decision does not itself modify persistence.

    MERGE / SUPERSEDE decisions identify the memories
    that should be consolidated and provide the content
    of the resulting active memory.
    """

    action: ConsolidationAction

    memories: tuple[LongTermMemory, ...]

    reason: str

    replacement_content: str | None = None

    category: str | None = None

    subject: str | None = None

    project: str | None = None

    importance: float = 0.5

    confidence: float = 1.0

    def __post_init__(self) -> None:

        if (
            self.action
            in (
                ConsolidationAction.MERGE,
                ConsolidationAction.SUPERSEDE,
            )
            and len(self.memories) < 2
        ):
            raise ValueError(
                "Consolidation requires at least "
                "two memories."
            )

        if (
            self.action
            in (
                ConsolidationAction.MERGE,
                ConsolidationAction.SUPERSEDE,
            )
            and not self.replacement_content
        ):
            raise ValueError(
                "Consolidation requires "
                "replacement content."
            )

        if not 0.0 <= self.importance <= 1.0:
            raise ValueError(
                "Consolidation importance must "
                "be between 0 and 1."
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Consolidation confidence must "
                "be between 0 and 1."
            )