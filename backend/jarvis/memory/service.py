"""
Core Memory service.

Provides the Agent-facing interface for persistent
memory blocks.
"""

from jarvis.memory.models import MemoryBlock
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)


class CoreMemoryService:
    """
    Manages Core Memory for an agent.
    """

    def __init__(
        self,
        repository: CoreMemoryRepository,
        agent_id: str = "jarvis",
    ) -> None:

        self.repository = repository
        self.agent_id = agent_id

    def create_block(
        self,
        label: str,
        content: str = "",
        capacity: int = 2000,
        priority: int = 100,
        writable: bool = True,
    ) -> MemoryBlock:

        existing = self.repository.get_by_label(
            self.agent_id,
            label,
        )

        if existing is not None:
            raise ValueError(
                f"Core Memory block '{label}' "
                f"already exists."
            )

        block = MemoryBlock(
            agent_id=self.agent_id,
            label=label,
            content=content,
            capacity=capacity,
            priority=priority,
            writable=writable,
        )

        block.id = (
            self.repository.create(
                block
            )
        )

        return block

    def get(
        self,
        label: str,
    ) -> MemoryBlock | None:

        return self.repository.get_by_label(
            self.agent_id,
            label,
        )

    def list_blocks(
        self,
    ) -> list[MemoryBlock]:

        return self.repository.list(
            self.agent_id
        )

    def replace(
        self,
        label: str,
        content: str,
    ) -> MemoryBlock:

        block = self.get(label)

        if block is None:
            raise KeyError(
                f"Core Memory block '{label}' "
                f"does not exist."
            )

        block.replace(content)

        self.repository.update(
            block
        )

        return block

    def append(
        self,
        label: str,
        content: str,
    ) -> MemoryBlock:

        block = self.get(label)

        if block is None:
            raise KeyError(
                f"Core Memory block '{label}' "
                f"does not exist."
            )

        block.append(content)

        self.repository.update(
            block
        )

        return block

    def delete(
        self,
        label: str,
    ) -> None:

        block = self.get(label)

        if block is None:
            raise KeyError(
                f"Core Memory block '{label}' "
                f"does not exist."
            )

        self.repository.delete(
            block.id
        )

    def ensure_default_blocks(
            self,
        ) -> None:
            """
            Ensure Jarvis has its standard Core Memory blocks.
            """

            defaults = [
                {
                    "label": "human",
                    "content": "",
                    "capacity": 2000,
                    "priority": 10,
                    "writable": True,
                },
                {
                    "label": "persona",
                    "content": (
                        "You are Jarvis, a local personal "
                        "AI assistant."
                    ),
                    "capacity": 2000,
                    "priority": 20,
                    "writable": True,
                },
            ]

            for default in defaults:

                existing = self.get(
                    default["label"]
                )

                if existing is not None:
                    continue

                self.create_block(
                    label=default["label"],
                    content=default["content"],
                    capacity=default["capacity"],
                    priority=default["priority"],
                    writable=default["writable"],
                )