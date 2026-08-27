"""
Long-Term Memory service.

Long-Term Memory is persistent semantic information
retained outside the active context and later retrieved
by the Retrieval layer.
"""

from __future__ import annotations

from jarvis.memory.models import (
    LongTermMemory,
)

from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)


class LongTermMemoryService:
    """
    Agent-facing service for Long-Term Memory.
    """

    def __init__(
        self,
        repository: LongTermMemoryRepository,
        agent_id: str = "jarvis",
    ) -> None:

        self.repository = repository
        self.agent_id = agent_id

    def create(
        self,
        content: str,
        category: str | None = None,
        subject: str | None = None,
        project: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
    ) -> LongTermMemory:

        memory = LongTermMemory(
            agent_id=self.agent_id,
            content=content,
            category=category,
            subject=subject,
            project=project,
            importance=importance,
            confidence=confidence,
        )

        memory.id = (
            self.repository.create(
                memory
            )
        )

        return memory

    def get(
        self,
        memory_id: int,
    ) -> LongTermMemory | None:

        memory = self.repository.get(
            memory_id
        )

        if memory is None:
            return None

        if memory.agent_id != self.agent_id:
            return None

        return memory

    def list(
        self,
        include_superseded: bool = False,
    ) -> list[LongTermMemory]:

        return self.repository.list(
            agent_id=self.agent_id,
            include_superseded=(
                include_superseded
            ),
        )

    def update(
        self,
        memory: LongTermMemory,
    ) -> LongTermMemory:

        if memory.agent_id != self.agent_id:
            raise PermissionError(
                "Memory belongs to a "
                "different agent."
            )

        if memory.id is None:
            raise ValueError(
                "Cannot update a memory "
                "without an ID."
            )

        if memory.status != "active":
            raise ValueError(
                "Only active memories "
                "can be edited."
            )

        memory.touch()

        self.repository.update(
            memory
        )

        return memory

    def supersede(
        self,
        memory_id: int,
        content: str,
        category: str | None = None,
        subject: str | None = None,
        project: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
    ) -> LongTermMemory:

        existing = self.get(
            memory_id
        )

        if existing is None:
            raise KeyError(
                f"Long-Term Memory "
                f"'{memory_id}' does not exist."
            )

        if existing.status != "active":
            raise ValueError(
                "Only an active memory "
                "can be superseded."
            )

        replacement = LongTermMemory(
            agent_id=self.agent_id,
            content=content,
            category=category,
            subject=subject,
            project=project,
            importance=importance,
            confidence=confidence,
        )

        replacement.id = (
            self.repository.supersede(
                existing,
                replacement,
            )
        )

        return replacement

    def consolidate(
        self,
        memory_ids: list[int],
        content: str,
        category: str | None = None,
        subject: str | None = None,
        project: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
    ) -> LongTermMemory:
        """
        Replace multiple active memories with one active
        consolidated memory.

        The operation is atomic.

        All original memories remain persisted as
        superseded historical records.
        """

        if len(memory_ids) < 2:
            raise ValueError(
                "Consolidation requires at least "
                "two memory IDs."
            )

        existing_memories: list[
            LongTermMemory
        ] = []

        for memory_id in memory_ids:

            memory = self.get(
                memory_id
            )

            if memory is None:
                raise KeyError(
                    f"Long-Term Memory "
                    f"'{memory_id}' does not exist."
                )

            if memory.status != "active":
                raise ValueError(
                    "Only active memories can "
                    "be consolidated."
                )

            existing_memories.append(
                memory
            )

        replacement = LongTermMemory(
            agent_id=self.agent_id,
            content=content,
            category=category,
            subject=subject,
            project=project,
            importance=importance,
            confidence=confidence,
        )

        replacement.id = (
            self.repository.consolidate(
                existing_memories,
                replacement,
            )
        )

        return replacement

    def delete(
        self,
        memory_id: int,
    ) -> None:

        memory = self.get(
            memory_id
        )

        if memory is None:
            raise KeyError(
                f"Long-Term Memory "
                f"'{memory_id}' does not exist."
            )

        if memory.status != "active":
            raise ValueError(
                "Superseded memories cannot "
                "be deleted through the normal "
                "memory service."
            )

        self.repository.delete(
            memory_id,
            self.agent_id,
        )