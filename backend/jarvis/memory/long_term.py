"""
Long-Term Memory service.

Long-Term Memory is persistent semantic information
that is retained outside the active context and can
later be retrieved by the Retrieval layer.
"""

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
        """
        Create and persist an active memory.
        """

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
        """
        Retrieve a memory belonging to this agent.
        """

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
        """
        List this agent's memories.

        Superseded memories are excluded by default.
        """

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
        """
        Persist edits to an active memory.
        """

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
        """
        Replace an active memory with a new memory.

        The replacement and superseding operation are
        committed atomically.
        """

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

    def delete(
        self,
        memory_id: int,
    ) -> None:
        """
        Delete an active memory.

        Superseded memories are retained as history.
        """

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