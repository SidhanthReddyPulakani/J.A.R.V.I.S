"""
Diary data models.

Diary is Jarvis's persistent record of events and experiences.

Unlike Memory, Diary is append-oriented history. An event records
what happened; it does not decide whether the information should
be retained as semantic memory.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""

    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass
class DiaryEvent:
    """
    A persistent Diary event.

    Diary events are append-oriented records of experiences.

    Fields:
        id:
            Database identifier. None before persistence.

        agent_id:
            Agent to which this event belongs.

        conversation_id:
            Optional conversation associated with the event.

        event_type:
            Category/type of event, for example:
            "interaction", "action", "result", "system", etc.

        description:
            Human-readable description of what happened.

        source:
            Component that produced the event.

        metadata:
            Optional structured information associated with the event.

        created_at:
            UTC timestamp at which the event was recorded.
    """

    id: int | None = None

    agent_id: str = "jarvis"

    conversation_id: int | None = None

    event_type: str = ""

    description: str = ""

    source: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str | None = None

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError(
                "Diary event agent_id cannot be empty."
            )

        if not self.event_type:
            raise ValueError(
                "Diary event type cannot be empty."
            )

        if not self.description:
            raise ValueError(
                "Diary event description cannot be empty."
            )

        if self.created_at is None:
            self.created_at = _utc_now()