"""
Diary service.

Provides the Agent-facing interface for persistent
event and experience history.
"""

from typing import Any

from jarvis.diary.models import DiaryEvent
from jarvis.storage.repositories.diary import DiaryRepository


class DiaryService:
    """
    Manages persistent Diary events for one Agent.
    """

    def __init__(
        self,
        repository: DiaryRepository,
        agent_id: str = "jarvis",
    ) -> None:

        self.repository = repository
        self.agent_id = agent_id

    def record(
        self,
        event_type: str,
        description: str,
        *,
        conversation_id: int | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DiaryEvent:
        """
        Record a new Diary event.

        Diary events are append-only.
        Every call creates a new event.
        """

        event = DiaryEvent(
            agent_id=self.agent_id,
            conversation_id=conversation_id,
            event_type=event_type,
            description=description,
            source=source,
            metadata=metadata or {},
        )

        event.id = (
            self.repository.create(
                event
            )
        )

        return event

    def get(
        self,
        event_id: int,
    ) -> DiaryEvent | None:
        """
        Retrieve one event belonging to this Agent.
        """

        event = self.repository.get(
            event_id
        )

        if event is None:
            return None

        if event.agent_id != self.agent_id:
            return None

        return event

    def recent(
        self,
        *,
        conversation_id: int | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[DiaryEvent]:
        """
        Retrieve recent events belonging to this Agent.
        """

        return self.repository.get_recent(
            self.agent_id,
            conversation_id=conversation_id,
            event_type=event_type,
            limit=limit,
        )

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        event_type: str | None = None,
        limit: int = 20,
    ) -> list[DiaryEvent]:
        """
        Search this Agent's Diary.

        Search is intentionally lexical at this stage.
        """

        return self.repository.search(
            self.agent_id,
            query,
            conversation_id=conversation_id,
            event_type=event_type,
            limit=limit,
        )