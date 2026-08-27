"""
Jarvis memory data models.

This module contains models for both:

- Core Memory
- Long-Term Memory
"""

from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(
        timezone.utc
    ).isoformat()


# ==================================================
# Core Memory
# ==================================================


@dataclass
class MemoryBlock:
    """
    A persistent Core Memory block.

    Core Memory is:
    - bounded,
    - persistent,
    - editable,
    - directly rendered into context.
    """

    id: int | None = None

    agent_id: str = "jarvis"

    label: str = ""

    content: str = ""

    capacity: int = 2000

    priority: int = 100

    writable: bool = True

    created_at: str | None = None

    updated_at: str | None = None

    def __post_init__(self) -> None:

        if not self.label:

            raise ValueError(
                "Memory block label cannot be empty."
            )

        if self.capacity <= 0:

            raise ValueError(
                "Memory block capacity "
                "must be positive."
            )

        if self.priority < 0:

            raise ValueError(
                "Memory block priority "
                "cannot be negative."
            )

        if len(self.content) > self.capacity:

            raise ValueError(
                "Memory block content "
                "exceeds capacity."
            )

        now = _utc_now()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def replace(
        self,
        content: str,
    ) -> None:
        """Replace the entire contents."""

        if not self.writable:

            raise PermissionError(
                f"Memory block '{self.label}' "
                "is read-only."
            )

        if len(content) > self.capacity:

            raise ValueError(
                f"Content exceeds the capacity "
                f"of memory block '{self.label}'. "
                f"Maximum: {self.capacity} characters."
            )

        self.content = content

        self.touch()

    def append(
        self,
        content: str,
    ) -> None:
        """Append content to the block."""

        if not self.writable:

            raise PermissionError(
                f"Memory block '{self.label}' "
                "is read-only."
            )

        new_content = (
            self.content + content
        )

        if len(new_content) > self.capacity:

            raise ValueError(
                f"Content exceeds the capacity "
                f"of memory block '{self.label}'. "
                f"Maximum: {self.capacity} characters."
            )

        self.content = new_content

        self.touch()

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = _utc_now()


# ==================================================
# Long-Term Memory
# ==================================================


_ALLOWED_LONG_TERM_STATUSES = {
    "active",
    "superseded",
}


@dataclass
class LongTermMemory:
    """
    Persistent semantic information retained outside
    the active context.

    Lifecycle:

        active
           │
           ▼
        superseded

    Superseded memories remain persisted so that
    historical state and replacement relationships
    remain available.
    """

    id: int | None = None

    agent_id: str = "jarvis"

    content: str = ""

    category: str | None = None

    subject: str | None = None

    project: str | None = None

    importance: float = 0.5

    confidence: float = 1.0

    status: str = "active"

    superseded_by_id: int | None = None

    created_at: str | None = None

    updated_at: str | None = None

    def __post_init__(self) -> None:

        if not self.agent_id:

            raise ValueError(
                "Memory agent_id cannot be empty."
            )

        if not self.content.strip():

            raise ValueError(
                "Long-Term Memory content "
                "cannot be empty."
            )

        if not 0.0 <= self.importance <= 1.0:

            raise ValueError(
                "Memory importance must be "
                "between 0 and 1."
            )

        if not 0.0 <= self.confidence <= 1.0:

            raise ValueError(
                "Memory confidence must be "
                "between 0 and 1."
            )

        if self.status not in (
            _ALLOWED_LONG_TERM_STATUSES
        ):

            raise ValueError(
                "Invalid memory status. "
                "Expected one of: "
                f"{sorted(_ALLOWED_LONG_TERM_STATUSES)}."
            )

        if (
            self.status == "active"
            and self.superseded_by_id is not None
        ):

            raise ValueError(
                "An active memory cannot "
                "have a replacement."
            )

        if (
            self.id is not None
            and self.superseded_by_id == self.id
        ):

            raise ValueError(
                "A memory cannot "
                "supersede itself."
            )

        now = _utc_now()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = _utc_now()