"""
Repository for persistent Long-Term Memory.
"""

from jarvis.memory.models import (
    LongTermMemory,
)

from jarvis.storage.repositories.base import (
    BaseRepository,
)


class LongTermMemoryRepository(
    BaseRepository
):
    """
    Handles database persistence for
    Long-Term Memory.
    """

    def create(
        self,
        memory: LongTermMemory,
    ) -> int:
        """Persist a new active memory."""

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO memories (
                    agent_id,
                    content,
                    category,
                    subject,
                    project,
                    importance,
                    confidence,
                    status,
                    superseded_by_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    memory.agent_id,
                    memory.content,
                    memory.category,
                    memory.subject,
                    memory.project,
                    memory.importance,
                    memory.confidence,
                    memory.status,
                    memory.superseded_by_id,
                    memory.created_at,
                    memory.updated_at,
                ),
            )

            return int(
                cursor.lastrowid
            )

    def get(
        self,
        memory_id: int,
    ) -> LongTermMemory | None:
        """Retrieve one memory by ID."""

        row = self.database.fetch_one(
            """
            SELECT
                id,
                agent_id,
                content,
                category,
                subject,
                project,
                importance,
                confidence,
                status,
                superseded_by_id,
                created_at,
                updated_at
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        )

        if row is None:
            return None

        return self._from_row(
            row
        )

    def list(
        self,
        agent_id: str,
        include_superseded: bool = False,
    ) -> list[LongTermMemory]:
        """
        List memories belonging to an agent.

        By default only active memories are returned.
        """

        if include_superseded:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    agent_id,
                    content,
                    category,
                    subject,
                    project,
                    importance,
                    confidence,
                    status,
                    superseded_by_id,
                    created_at,
                    updated_at
                FROM memories
                WHERE agent_id = ?
                ORDER BY
                    importance DESC,
                    updated_at DESC,
                    id DESC
                """,
                (agent_id,),
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    agent_id,
                    content,
                    category,
                    subject,
                    project,
                    importance,
                    confidence,
                    status,
                    superseded_by_id,
                    created_at,
                    updated_at
                FROM memories
                WHERE agent_id = ?
                  AND status = 'active'
                ORDER BY
                    importance DESC,
                    updated_at DESC,
                    id DESC
                """,
                (agent_id,),
            )

        return [
            self._from_row(row)
            for row in rows
        ]

    def update(
        self,
        memory: LongTermMemory,
    ) -> None:
        """Update an active memory."""

        if memory.id is None:

            raise ValueError(
                "Cannot update a memory "
                "without an ID."
            )

        self.database.execute(
            """
            UPDATE memories
            SET
                content = ?,
                category = ?,
                subject = ?,
                project = ?,
                importance = ?,
                confidence = ?,
                updated_at = ?
            WHERE id = ?
              AND agent_id = ?
              AND status = 'active'
            """,
            (
                memory.content,
                memory.category,
                memory.subject,
                memory.project,
                memory.importance,
                memory.confidence,
                memory.updated_at,
                memory.id,
                memory.agent_id,
            ),
        )

    def supersede(
        self,
        existing: LongTermMemory,
        replacement: LongTermMemory,
    ) -> int:
        """
        Atomically create a replacement memory
        and mark the existing memory as superseded.
        """

        if existing.id is None:

            raise ValueError(
                "Cannot supersede a memory "
                "without an ID."
            )

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO memories (
                    agent_id,
                    content,
                    category,
                    subject,
                    project,
                    importance,
                    confidence,
                    status,
                    superseded_by_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, 'active', NULL, ?, ?
                )
                """,
                (
                    replacement.agent_id,
                    replacement.content,
                    replacement.category,
                    replacement.subject,
                    replacement.project,
                    replacement.importance,
                    replacement.confidence,
                    replacement.created_at,
                    replacement.updated_at,
                ),
            )

            replacement_id = int(
                cursor.lastrowid
            )

            connection.execute(
                """
                UPDATE memories
                SET
                    status = 'superseded',
                    superseded_by_id = ?,
                    updated_at = ?
                WHERE id = ?
                  AND agent_id = ?
                  AND status = 'active'
                """,
                (
                    replacement_id,
                    replacement.updated_at,
                    existing.id,
                    existing.agent_id,
                ),
            )

            return replacement_id

    def delete(
        self,
        memory_id: int,
        agent_id: str,
    ) -> None:
        """Delete an active memory."""

        self.database.execute(
            """
            DELETE FROM memories
            WHERE id = ?
              AND agent_id = ?
              AND status = 'active'
            """,
            (
                memory_id,
                agent_id,
            ),
        )

    @staticmethod
    def _from_row(
        row,
    ) -> LongTermMemory:

        return LongTermMemory(
            id=row[0],
            agent_id=row[1],
            content=row[2],
            category=row[3],
            subject=row[4],
            project=row[5],
            importance=float(row[6]),
            confidence=float(row[7]),
            status=row[8],
            superseded_by_id=row[9],
            created_at=row[10],
            updated_at=row[11],
        )