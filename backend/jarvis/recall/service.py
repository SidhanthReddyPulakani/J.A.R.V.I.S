"""
Jarvis Recall service.

Recall is the persistent historical interaction layer.
It provides access to conversation and message history.

Recall is distinct from semantic Memory and Diary.
"""

from typing import Any

from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)


class RecallService:
    """
    Provides the Agent with access to persistent recall.

    The service owns the application-level interface while
    the repository owns database interaction.
    """

    def __init__(
        self,
        repository: ConversationRepository,
    ) -> None:
        self.repository = repository

    def create_conversation(self) -> int:
        return self.repository.create()

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
    ) -> int:
        return self.repository.add_message(
            conversation_id,
            role,
            content,
        )

    def get_messages(
        self,
        conversation_id: int,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self.repository.get_messages(
            conversation_id,
            limit=limit,
        )

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self.repository.search(
            query,
            conversation_id=conversation_id,
            limit=limit,
        )