"""
Jarvis Knowledge / Archive data models.

Knowledge represents persistent information that can be retrieved
when relevant.

Hierarchy:

    KnowledgeSource
        |
        +-- KnowledgeDocument
                |
                +-- KnowledgePassage

Knowledge is intentionally separate from Long-Term Memory.

Long-Term Memory:
    Semantic information Jarvis deliberately retains.

Knowledge / Archive:
    External, reference, project, or imported information that
    Jarvis can retrieve when needed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""

    return datetime.now(
        timezone.utc
    ).isoformat()


# ==================================================
# Knowledge Source
# ==================================================


@dataclass
class KnowledgeSource:
    """
    Represents the origin of a body of knowledge.

    Examples:

        file
        directory
        url
        database
        manual
        capability

    The source identifies where information came from.

    It does not contain the actual document contents.
    """

    id: int | None = None

    name: str = ""

    source_type: str = ""

    origin: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    ingestion_status: str = "pending"

    created_at: str | None = None

    updated_at: str | None = None

    def __post_init__(self) -> None:

        if not self.name.strip():
            raise ValueError(
                "Knowledge source name cannot be empty."
            )

        if not self.source_type.strip():
            raise ValueError(
                "Knowledge source type cannot be empty."
            )

        if not self.origin.strip():
            raise ValueError(
                "Knowledge source origin cannot be empty."
            )

        if not self.ingestion_status.strip():
            raise ValueError(
                "Knowledge source ingestion status "
                "cannot be empty."
            )

        now = _utc_now()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = _utc_now()


# ==================================================
# Knowledge Document
# ==================================================


@dataclass
class KnowledgeDocument:
    """
    Represents a concrete document belonging to a KnowledgeSource.

    A document is the canonical artifact from which passages are
    later produced.

    Examples:

        architecture.md
        python_reference.pdf
        handbook.pdf
        project_notes.txt
    """

    id: int | None = None

    source_id: int | None = None

    title: str = ""

    content_type: str = "text/plain"

    external_id: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    content_hash: str | None = None

    created_at: str | None = None

    updated_at: str | None = None

    def __post_init__(self) -> None:

        if self.source_id is None:
            raise ValueError(
                "Knowledge document source_id cannot be None."
            )

        if not self.title.strip():
            raise ValueError(
                "Knowledge document title cannot be empty."
            )

        if not self.content_type.strip():
            raise ValueError(
                "Knowledge document content_type "
                "cannot be empty."
            )

        if (
            self.external_id is not None
            and not self.external_id.strip()
        ):
            raise ValueError(
                "Knowledge document external_id "
                "cannot be empty when provided."
            )

        if (
            self.content_hash is not None
            and not self.content_hash.strip()
        ):
            raise ValueError(
                "Knowledge document content_hash "
                "cannot be empty when provided."
            )

        now = _utc_now()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = _utc_now()


# ==================================================
# Knowledge Passage
# ==================================================


@dataclass
class KnowledgePassage:
    """
    Represents one retrievable unit of a KnowledgeDocument.

    Passages are the canonical retrieval units.

    sequence:
        Zero-based or one-based ordering assigned by the ingestion
        pipeline. The model only guarantees that the value is
        non-negative.

    metadata:
        Source-specific provenance such as:

            page
            section
            heading
            line range
            URL fragment
            parser information
    """

    id: int | None = None

    document_id: int | None = None

    sequence: int = 0

    content: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    content_hash: str | None = None

    created_at: str | None = None

    updated_at: str | None = None

    def __post_init__(self) -> None:

        if self.document_id is None:
            raise ValueError(
                "Knowledge passage document_id "
                "cannot be None."
            )

        if self.sequence < 0:
            raise ValueError(
                "Knowledge passage sequence "
                "cannot be negative."
            )

        if not self.content.strip():
            raise ValueError(
                "Knowledge passage content cannot be empty."
            )

        if (
            self.content_hash is not None
            and not self.content_hash.strip()
        ):
            raise ValueError(
                "Knowledge passage content_hash "
                "cannot be empty when provided."
            )

        now = _utc_now()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = _utc_now()