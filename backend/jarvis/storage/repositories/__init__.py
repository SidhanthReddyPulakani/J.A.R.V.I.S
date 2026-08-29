"""Repository package public API.

Concrete repositories are exposed lazily so importing one repository module
cannot trigger a package-wide import cycle.
"""

from typing import Any

__all__ = [
    "AgentStateRepository",
    "ConversationRepository",
    "CoreMemoryRepository",
    "DiaryRepository",
    "KnowledgeRepository",
    "LongTermMemoryRepository",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve concrete repository classes on demand."""

    if name == "AgentStateRepository":
        from jarvis.storage.repositories.agent_state import AgentStateRepository

        return AgentStateRepository

    if name == "ConversationRepository":
        from jarvis.storage.repositories.conversations import ConversationRepository

        return ConversationRepository

    if name == "CoreMemoryRepository":
        from jarvis.storage.repositories.core_memory import CoreMemoryRepository

        return CoreMemoryRepository

    if name == "DiaryRepository":
        from jarvis.storage.repositories.diary import DiaryRepository

        return DiaryRepository

    if name == "KnowledgeRepository":
        from jarvis.storage.repositories.knowledge import KnowledgeRepository

        return KnowledgeRepository

    if name == "LongTermMemoryRepository":
        from jarvis.storage.repositories.long_term_memory import (
            LongTermMemoryRepository,
        )

        return LongTermMemoryRepository

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
