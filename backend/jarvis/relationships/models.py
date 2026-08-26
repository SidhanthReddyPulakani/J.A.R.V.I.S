"""
Generic relationship models.

A relationship connects a human-facing key/phrase to a target.

The relationship system intentionally knows nothing about
applications, files, folders, templates, etc.
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Relationship:
    """
    A persistent association between a source phrase and a target.

    Example:

        source = "browser"
        target_type = "application"
        target = "Brave"
    """

    id: int | None
    source: str
    target_type: str
    target: str

    confidence: float = 0.5
    confirmations: int = 0
    uses: int = 0

    created_at: str | None = None
    updated_at: str | None = None
    last_used_at: str | None = None

    def __post_init__(self) -> None:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        if self.created_at is None:
            self.created_at = now

        if self.updated_at is None:
            self.updated_at = now

    def mark_confirmed(self) -> None:
        """
        Record an explicit user confirmation.
        """

        self.confirmations += 1

        # Confirmation increases confidence,
        # but confidence is capped at 1.0.
        self.confidence = min(
            1.0,
            self.confidence + 0.15,
        )

        self.updated_at = datetime.now(
            timezone.utc
        ).isoformat()

    def mark_used(self) -> None:
        """
        Record successful use of the relationship.
        """

        self.uses += 1

        self.last_used_at = datetime.now(
            timezone.utc
        ).isoformat()

        self.updated_at = datetime.now(
            timezone.utc
        ).isoformat()