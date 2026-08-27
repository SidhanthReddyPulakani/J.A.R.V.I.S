"""
Repository for persistent Core Memory blocks.
"""

from jarvis.memory.models import MemoryBlock
from jarvis.storage.repositories.base import BaseRepository


class CoreMemoryRepository(BaseRepository):
    """
    Handles database persistence for Core Memory blocks.
    """

    def create(
        self,
        block: MemoryBlock,
    ) -> int:

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO core_memory_blocks (
                    agent_id,
                    label,
                    content,
                    capacity,
                    priority,
                    writable,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    block.agent_id,
                    block.label,
                    block.content,
                    block.capacity,
                    block.priority,
                    int(block.writable),
                    block.created_at,
                    block.updated_at,
                ),
            )

            return int(
                cursor.lastrowid
            )

    def get(
        self,
        block_id: int,
    ) -> MemoryBlock | None:

        row = self.database.fetch_one(
            """
            SELECT
                id,
                agent_id,
                label,
                content,
                capacity,
                priority,
                writable,
                created_at,
                updated_at
            FROM core_memory_blocks
            WHERE id = ?
            """,
            (block_id,),
        )

        if row is None:
            return None

        return self._from_row(row)

    def get_by_label(
        self,
        agent_id: str,
        label: str,
    ) -> MemoryBlock | None:

        row = self.database.fetch_one(
            """
            SELECT
                id,
                agent_id,
                label,
                content,
                capacity,
                priority,
                writable,
                created_at,
                updated_at
            FROM core_memory_blocks
            WHERE agent_id = ?
              AND label = ?
            """,
            (
                agent_id,
                label,
            ),
        )

        if row is None:
            return None

        return self._from_row(row)

    def list(
        self,
        agent_id: str,
    ) -> list[MemoryBlock]:

        rows = self.database.fetch_all(
            """
            SELECT
                id,
                agent_id,
                label,
                content,
                capacity,
                priority,
                writable,
                created_at,
                updated_at
            FROM core_memory_blocks
            WHERE agent_id = ?
            ORDER BY priority ASC, id ASC
            """,
            (agent_id,),
        )

        return [
            self._from_row(row)
            for row in rows
        ]

    def update(
        self,
        block: MemoryBlock,
    ) -> None:

        if block.id is None:
            raise ValueError(
                "Cannot update a block without an ID."
            )

        block.touch()

        self.database.execute(
            """
            UPDATE core_memory_blocks
            SET
                content = ?,
                capacity = ?,
                priority = ?,
                writable = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                block.content,
                block.capacity,
                block.priority,
                int(block.writable),
                block.updated_at,
                block.id,
            ),
        )

    def delete(
        self,
        block_id: int,
    ) -> None:

        self.database.execute(
            """
            DELETE FROM core_memory_blocks
            WHERE id = ?
            """,
            (block_id,),
        )

    @staticmethod
    def _from_row(
        row,
    ) -> MemoryBlock:

        return MemoryBlock(
            id=row[0],
            agent_id=row[1],
            label=row[2],
            content=row[3],
            capacity=row[4],
            priority=row[5],
            writable=bool(row[6]),
            created_at=row[7],
            updated_at=row[8],
        )