"""
Retrieval composition.

Builds the application's unified RetrievalService from
the information providers that already exist.

This module owns composition only.
It does not implement retrieval logic.
"""

from jarvis.retrieval.providers import (
    KnowledgeProvider,
    MemoryProvider,
    RecallProvider,
    RelationshipProvider,
)
from jarvis.retrieval.service import RetrievalService


def build_retrieval_service(
    *,
    recall_service,
    memory_service,
    relationship_store,
    knowledge_service,
    conversation_id: int | None = None,
) -> RetrievalService:
    """
    Construct the unified RetrievalService.

    Provider responsibilities remain unchanged:

        RecallProvider
        MemoryProvider
        RelationshipProvider
        KnowledgeProvider

    The composition layer simply supplies their dependencies.
    """

    return RetrievalService(
        providers=[
            RecallProvider(
                recall_service=recall_service,
                conversation_id=conversation_id,
            ),
            MemoryProvider(
                memory_service=memory_service,
            ),
            RelationshipProvider(
                relationship_store=relationship_store,
            ),
            KnowledgeProvider(
                knowledge_service=knowledge_service,
            ),
        ]
    )