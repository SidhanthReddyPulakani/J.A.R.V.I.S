"""
Repository for conversation and message history.

Conversation history is Jarvis's persistent recall layer.
It is distinct from semantic Memory and Diary.
"""

from datetime import datetime, timezone
from typing import Any

from jarvis.storage.repositories.base import BaseRepository


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationRepository(BaseRepository):
    """Persistence operations for conversations and messages."""

    def create(self) -> int:
        """Create a new conversation and return its ID."""

        now = _utc_now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversations (
                    created_at,
                    updated_at
                )
                VALUES (?, ?)
                """,
                (now, now),
            )

            return cursor.lastrowid

    def get(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        """Retrieve conversation metadata."""

        return self.database.fetch_one(
            """
            SELECT
                id,
                created_at,
                updated_at
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,),
        )

    def touch(
        self,
        conversation_id: int,
    ) -> None:
        """Update the conversation's modification timestamp."""

        self.database.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
            """,
            (_utc_now(), conversation_id),
        )

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
    ) -> int:
        """Persist one conversation message."""

        now = _utc_now()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    content,
                    now,
                ),
            )

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, conversation_id),
            )

            return cursor.lastrowid

    def get_messages(
        self,
        conversation_id: int,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve conversation messages in chronological order.

        If limit is supplied, the most recent messages are returned.
        """

        if limit is None:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    conversation_id,
                    limit,
                ),
            )

            rows.reverse()

        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "role": row[2],
                "content": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search persisted conversation history.

        This is intentionally simple for 1.1C.
        Semantic retrieval comes later.
        """

        if conversation_id is None:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    created_at
                FROM messages
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    f"%{query}%",
                    limit,
                ),
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    conversation_id,
                    role,
                    content,
                    created_at
                FROM messages
                WHERE conversation_id = ?
                  AND content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    conversation_id,
                    f"%{query}%",
                    limit,
                ),
            )

        return [
            {
                "id": row[0],
                "conversation_id": row[1],
                "role": row[2],
                "content": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]