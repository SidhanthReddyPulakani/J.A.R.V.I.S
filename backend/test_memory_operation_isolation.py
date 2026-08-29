"""
R2.9E persistence and isolation tests.

These tests verify that Agent-facing memory operations:

- persist through the existing services,
- survive service reconstruction,
- remain agent-scoped,
- do not leak across agents,
- respect the existing persistence boundary.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from jarvis.memory import (
    AgentMemoryOperations,
    CoreMemoryService,
)
from jarvis.memory.long_term import (
    LongTermMemoryService,
)
from jarvis.knowledge import KnowledgeService
from jarvis.recall.service import RecallService
from jarvis.retrieval import (
    KnowledgeProvider,
    MemoryProvider,
    RecallProvider,
    RetrievalService,
)
from jarvis.state.models import AgentState
from jarvis.storage.database import Database
from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)
from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)


def create_agent(
    database: Database,
    agent_id: str,
) -> AgentState:
    """
    Create the minimum persistent Agent State required by
    agent-scoped information tables.

    Core Memory and Long-Term Memory both depend on a valid
    Agent identity being present before their records can be
    inserted.
    """

    repository = AgentStateRepository(
        database
    )

    state = repository.get(
        agent_id
    )

    if state is None:
        state = AgentState(
            agent_id=agent_id,
        )

        repository.save(
            state
        )

    return state


def build_operations(
    database: Database,
    *,
    agent_id: str,
    conversation_id: int | None = None,
) -> AgentMemoryOperations:
    """
    Build an isolated AgentMemoryOperations surface.
    """

    create_agent(
        database,
        agent_id,
    )

    recall = RecallService(
        ConversationRepository(database)
    )

    core_memory = CoreMemoryService(
        CoreMemoryRepository(database),
        agent_id=agent_id,
    )

    long_term_memory = LongTermMemoryService(
        LongTermMemoryRepository(database),
        agent_id=agent_id,
    )

    knowledge = KnowledgeService(
        KnowledgeRepository(database)
    )

    retrieval = RetrievalService(
        providers=[
            RecallProvider(
                recall_service=recall,
                conversation_id=conversation_id,
            ),
            MemoryProvider(
                memory_service=long_term_memory,
            ),
            KnowledgeProvider(
                knowledge_service=knowledge,
            ),
        ]
    )

    return AgentMemoryOperations(
        core_memory=core_memory,
        long_term_memory=long_term_memory,
        recall=recall,
        knowledge=knowledge,
        retrieval=retrieval,
        conversation_id=conversation_id,
    )


def test_long_term_memory_persists_and_is_agent_scoped() -> None:
    """
    Memory created by one agent must survive reconstruction
    and remain invisible to another agent.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "jarvis.db"

        database = Database(
            path=db_path
        )

        database.initialize()

        agent_a = build_operations(
            database,
            agent_id="agent-a",
        )

        created = agent_a.create_memory(
            "Agent A persistent information.",
            category="test",
            subject="isolation",
            project="R2.9",
            importance=0.9,
            confidence=1.0,
        )

        assert created.id is not None

        # Reconstruct the service boundary.
        agent_a_reloaded = build_operations(
            database,
            agent_id="agent-a",
        )

        memories = agent_a_reloaded.list_memories()

        assert any(
            memory.content
            == "Agent A persistent information."
            for memory in memories
        )

        agent_b = build_operations(
            database,
            agent_id="agent-b",
        )

        agent_b_memories = agent_b.list_memories()

        assert not any(
            memory.content
            == "Agent A persistent information."
            for memory in agent_b_memories
        )


def test_core_memory_persists_through_operation_surface() -> None:
    """
    Core Memory edits must persist through the normal service
    boundary and survive service reconstruction.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "jarvis.db"

        database = Database(
            path=db_path
        )

        database.initialize()

        operations = build_operations(
            database,
            agent_id="agent-core",
        )

        # Core Memory blocks are intentionally explicit.
        # Create the standard blocks through the existing
        # Core Memory service lifecycle.
        operations.core_memory.ensure_default_blocks()

        blocks = operations.list_core_memory()

        assert blocks

        label = blocks[0].label

        operations.replace_core_memory(
            label,
            "Persistent Core Memory test.",
        )

        reloaded = build_operations(
            database,
            agent_id="agent-core",
        )

        block = reloaded.read_core_memory(
            label
        )

        assert block is not None

        assert (
            block.content
            == "Persistent Core Memory test."
        )

        # Restore the test database state before leaving the
        # test. This keeps the fixture semantically clean if


def test_operation_surface_does_not_cross_agent_memory_boundary() -> None:
    """
    Search through one Agent's memory provider must not expose
    another Agent's Long-Term Memory.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "jarvis.db"

        database = Database(
            path=db_path
        )

        database.initialize()

        agent_a = build_operations(
            database,
            agent_id="agent-a",
        )

        agent_b = build_operations(
            database,
            agent_id="agent-b",
        )

        agent_a.create_memory(
            "Only agent A should retrieve this.",
            category="test",
            subject="scope",
            project="R2.9",
            importance=0.9,
            confidence=1.0,
        )

        a_results = agent_a.search_memory(
            "agent A retrieve",
        )

        b_results = agent_b.search_memory(
            "agent A retrieve",
        )

        assert any(
            "agent A" in str(result.content)
            for result in a_results
        )

        assert not any(
            "agent A" in str(result.content)
            for result in b_results
        )


def main() -> None:
    test_long_term_memory_persists_and_is_agent_scoped()
    test_core_memory_persists_through_operation_surface()
    test_operation_surface_does_not_cross_agent_memory_boundary()

    print(
        "R2.9E persistence/isolation tests passed."
    )


if __name__ == "__main__":
    main()