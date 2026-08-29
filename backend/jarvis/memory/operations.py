"""
Agent-facing information operations.

This module defines the stable operation surface that a future Agent
reasoning protocol can call for self-managed information access.

It deliberately does not:

- parse LLM tool calls,
- own persistence,
- compile context,
- execute capabilities, or
- implement the Agent reasoning loop.

Those responsibilities belong to higher layers.
"""

from __future__ import annotations

from typing import Any

from jarvis.knowledge.service import KnowledgeService
from jarvis.recall.service import RecallService
from jarvis.retrieval.models import RetrievalResult
from jarvis.retrieval.service import RetrievalService
from jarvis.memory.long_term import LongTermMemoryService
from jarvis.memory.models import LongTermMemory, MemoryBlock
from jarvis.memory.operation_validation import (
    DEFAULT_LIMIT,
    validate_boolean,
    validate_content,
    validate_id,
    validate_label,
    validate_limit,
    validate_memory_creation,
    validate_optional_text,
    validate_query,
)
from jarvis.memory.service import CoreMemoryService


class AgentMemoryOperations:
    """
    Stable Agent-facing operation surface for persistent information.

    The operation surface intentionally uses existing services rather than
    reaching into repositories. This preserves the storage boundary and
    gives the future Agent loop one narrow place to call.
    """

    def __init__(
        self,
        *,
        core_memory: CoreMemoryService,
        long_term_memory: LongTermMemoryService,
        recall: RecallService,
        knowledge: KnowledgeService,
        retrieval: RetrievalService,
        conversation_id: int | None = None,
    ) -> None:
        self.core_memory = core_memory
        self.long_term_memory = long_term_memory
        self.recall = recall
        self.knowledge = knowledge
        self.retrieval = retrieval

        if conversation_id is not None:
            validate_id(
                conversation_id,
                field_name="Conversation ID",
            )

        self.conversation_id = conversation_id

    # ==================================================
    # Core Memory
    # ==================================================

    def read_core_memory(
        self,
        label: str,
    ) -> MemoryBlock | None:
        """
        Read one Core Memory block.
        """
        validate_label(label)

        return self.core_memory.get(label)

    def list_core_memory(
        self,
    ) -> list[MemoryBlock]:
        """
        List all Core Memory blocks for the configured agent.
        """
        return self.core_memory.list_blocks()

    def replace_core_memory(
        self,
        label: str,
        content: str,
    ) -> MemoryBlock:
        """
        Replace one writable Core Memory block.
        """
        validate_label(label)
        validate_content(
            content,
            field_name="Core Memory content",
        )

        return self.core_memory.replace(
            label,
            content,
        )

    def append_core_memory(
        self,
        label: str,
        content: str,
    ) -> MemoryBlock:
        """
        Append to one writable Core Memory block.
        """
        validate_label(label)
        validate_content(
            content,
            field_name="Core Memory content",
        )

        return self.core_memory.append(
            label,
            content,
        )

    # ==================================================
    # Long-Term Memory
    # ==================================================

    def create_memory(
        self,
        content: str,
        *,
        category: str | None = None,
        subject: str | None = None,
        project: str | None = None,
        importance: float = 0.5,
        confidence: float = 1.0,
    ) -> LongTermMemory:
        """
        Create a Long-Term Memory owned by the configured agent.
        """
        validated = validate_memory_creation(
            content=content,
            category=category,
            subject=subject,
            project=project,
            importance=importance,
            confidence=confidence,
        )

        return self.long_term_memory.create(
            **validated,
        )

    def get_memory(
        self,
        memory_id: int,
    ) -> LongTermMemory | None:
        """
        Read one Long-Term Memory owned by the configured agent.
        """
        validate_id(
            memory_id,
            field_name="Memory ID",
        )

        return self.long_term_memory.get(
            memory_id
        )

    def list_memories(
        self,
        *,
        include_superseded: bool = False,
    ) -> list[LongTermMemory]:
        """
        List Long-Term Memories owned by the configured agent.
        """
        validate_boolean(
            include_superseded,
            field_name="include_superseded",
        )

        return self.long_term_memory.list(
            include_superseded=include_superseded,
        )

    def delete_memory(
        self,
        memory_id: int,
    ) -> None:
        """
        Delete an active Long-Term Memory owned by the configured agent.
        """
        validate_id(
            memory_id,
            field_name="Memory ID",
        )

        self.long_term_memory.delete(
            memory_id
        )

    # ==================================================
    # Recall
    # ==================================================

    def search_recall(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Search persisted conversation history.
        """
        validate_query(query)
        validate_limit(limit)

        return self.recall.search(
            query,
            conversation_id=self.conversation_id,
            limit=limit,
        )

    # ==================================================
    # Knowledge / Archive
    # ==================================================

    def search_knowledge(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> list[RetrievalResult]:
        """
        Search archived Knowledge through the unified Retrieval layer.
        """
        validate_query(query)
        validate_limit(limit)

        return self.retrieval.search(
            query,
            sources=["knowledge"],
            limit=limit,
        )

    # ==================================================
    # Long-Term Memory retrieval
    # ==================================================

    def search_memory(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> list[RetrievalResult]:
        """
        Search Long-Term Memory through the unified Retrieval layer.
        """
        validate_query(query)
        validate_limit(limit)

        return self.retrieval.search(
            query,
            sources=["memory"],
            limit=limit,
        )


__all__ = [
    "AgentMemoryOperations",
]