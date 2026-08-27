"""
Repository for persistent Diary events.
"""

import json
from typing import Any

from jarvis.diary.models import DiaryEvent
from jarvis.storage.repositories.base import BaseRepository


class DiaryRepository(BaseRepository):
    """
    Handles persistence and retrieval of Diary events.

    Diary is append-oriented:
    events are created and retrieved, but not rewritten.
    """

    def create(
        self,
        event: DiaryEvent,
    ) -> int:
        """
        Persist one Diary event.

        Returns:
            The database ID assigned to the event.
        """

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO diary_events (
                    agent_id,
                    conversation_id,
                    event_type,
                    description,
                    source,
                    metadata,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.agent_id,
                    event.conversation_id,
                    event.event_type,
                    event.description,
                    event.source,
                    json.dumps(
                        event.metadata,
                        ensure_ascii=False,
                    ),
                    event.created_at,
                ),
            )

            return int(
                cursor.lastrowid
            )

    def get(
        self,
        event_id: int,
    ) -> DiaryEvent | None:
        """
        Retrieve one Diary event by ID.
        """

        row = self.database.fetch_one(
            """
            SELECT
                id,
                agent_id,
                conversation_id,
                event_type,
                description,
                source,
                metadata,
                created_at
            FROM diary_events
            WHERE id = ?
            """,
            (event_id,),
        )

        if row is None:
            return None

        return self._from_row(row)

    def get_recent(
        self,
        agent_id: str,
        *,
        conversation_id: int | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[DiaryEvent]:
        """
        Retrieve Diary events in reverse chronological order.

        The newest event is returned first.

        Optional filters:
            conversation_id:
                Restrict events to one conversation.

            event_type:
                Restrict events to one event type.

            limit:
                Maximum number of events to return.
        """

        if limit <= 0:
            raise ValueError(
                "Diary event limit must be positive."
            )

        conditions = [
            "agent_id = ?"
        ]

        parameters: list[Any] = [
            agent_id
        ]

        if conversation_id is not None:

            conditions.append(
                "conversation_id = ?"
            )

            parameters.append(
                conversation_id
            )

        if event_type is not None:

            conditions.append(
                "event_type = ?"
            )

            parameters.append(
                event_type
            )

        parameters.append(
            limit
        )

        query = f"""
            SELECT
                id,
                agent_id,
                conversation_id,
                event_type,
                description,
                source,
                metadata,
                created_at
            FROM diary_events
            WHERE {" AND ".join(conditions)}
            ORDER BY id DESC
            LIMIT ?
        """

        rows = self.database.fetch_all(
            query,
            tuple(parameters),
        )

        return [
            self._from_row(row)
            for row in rows
        ]

    def search(
        self,
        agent_id: str,
        query: str,
        *,
        conversation_id: int | None = None,
        event_type: str | None = None,
        limit: int = 20,
    ) -> list[DiaryEvent]:
        """
        Search Diary event descriptions.

        This is intentionally lexical/simple for R2.3.

        Semantic retrieval belongs to the later Retrieval layer.
        """

        if not query.strip():
            return []

        if limit <= 0:
            raise ValueError(
                "Diary search limit must be positive."
            )

        conditions = [
            "agent_id = ?",
            """
            (
                description LIKE ?
                OR event_type LIKE ?
                OR COALESCE(source, '') LIKE ?
            )
            """,
        ]

        search_term = f"%{query}%"

        parameters: list[Any] = [
            agent_id,
            search_term,
            search_term,
            search_term,
        ]

        if conversation_id is not None:

            conditions.append(
                "conversation_id = ?"
            )

            parameters.append(
                conversation_id
            )

        if event_type is not None:

            conditions.append(
                "event_type = ?"
            )

            parameters.append(
                event_type
            )

        parameters.append(
            limit
        )

        sql = f"""
            SELECT
                id,
                agent_id,
                conversation_id,
                event_type,
                description,
                source,
                metadata,
                created_at
            FROM diary_events
            WHERE {" AND ".join(conditions)}
            ORDER BY id DESC
            LIMIT ?
        """

        rows = self.database.fetch_all(
            sql,
            tuple(parameters),
        )

        return [
            self._from_row(row)
            for row in rows
        ]

    @staticmethod
    def _from_row(
        row,
    ) -> DiaryEvent:
        """
        Convert a database row into a DiaryEvent.
        """

        metadata = {}

        if row[6]:

            try:
                loaded = json.loads(
                    row[6]
                )

                if isinstance(
                    loaded,
                    dict,
                ):
                    metadata = loaded

            except (
                TypeError,
                ValueError,
            ):
                metadata = {}

        return DiaryEvent(
            id=row[0],
            agent_id=row[1],
            conversation_id=row[2],
            event_type=row[3],
            description=row[4],
            source=row[5],
            metadata=metadata,
            created_at=row[7],
        )