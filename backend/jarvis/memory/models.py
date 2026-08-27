"""
Core Memory data models.

Core Memory consists of persistent, bounded memory blocks
that can be rendered directly into the Agent's context.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MemoryBlock:
    """
    A persistent Core Memory block.

    A block is:
    - identified by an ID,
    - scoped to an agent,
    - addressed by a unique label,
    - bounded by a character capacity,
    - optionally writable.
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
                "Memory block capacity must be positive."
            )

        if self.priority < 0:
            raise ValueError(
                "Memory block priority cannot be negative."
            )

        if len(self.content) > self.capacity:
            raise ValueError(
                "Memory block content exceeds capacity."
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def replace(
        self,
        content: str,
    ) -> None:
        """
        Replace the entire contents of the block.
        """

        if not self.writable:
            raise PermissionError(
                f"Memory block '{self.label}' is read-only."
            )

        if len(content) > self.capacity:
            raise ValueError(
                f"Content exceeds the capacity of "
                f"memory block '{self.label}'. "
                f"Maximum: {self.capacity} characters."
            )

        self.content = content
        self.touch()

    def append(
        self,
        content: str,
    ) -> None:
        """
        Append content to the existing block.
        """

        if not self.writable:
            raise PermissionError(
                f"Memory block '{self.label}' is read-only."
            )

        new_content = self.content + content

        if len(new_content) > self.capacity:
            raise ValueError(
                f"Content exceeds the capacity of "
                f"memory block '{self.label}'. "
                f"Maximum: {self.capacity} characters."
            )

        self.content = new_content
        self.touch()

    def touch(self) -> None:
        """Update the modification timestamp."""

        self.updated_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )