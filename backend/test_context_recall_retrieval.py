"""
R2.10B.3 + R2.10B.4

Recall and Retrieval -> Context integration tests.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.memory.long_term import (
    LongTermMemoryService,
)
from jarvis.recall.service import (
    RecallService,
)
from jarvis.retrieval import (
    KnowledgeProvider,
    MemoryProvider,
    RecallProvider,
    RetrievalService,
)
from jarvis.storage.database import Database
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)
from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)
from jarvis.knowledge import KnowledgeService
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)


SYSTEM_PROMPT = "You are Jarvis."


def test_recall_retrieval_is_available() -> None:
    """
    RecallProvider must retrieve historical conversation
    through the unified RetrievalService.
    """

    with TemporaryDirectory() as temp_dir:

        database = Database(
            Path(temp_dir) / "recall.db"
        )

        database.initialize()

        recall = RecallService(
            ConversationRepository(
                database
            )
        )

        conversation_id = (
            recall.create_conversation()
        )

        recall.add_message(
            conversation_id,
            "user",
            "Jarvis uses a modular architecture.",
        )

        retrieval = RetrievalService(
            providers=[
                RecallProvider(
                    recall_service=recall,
                    conversation_id=conversation_id,
                )
            ]
        )

        results = retrieval.search(
            "modular architecture",
            sources=["recall"],
            limit=10,
        )

        assert results

        assert any(
            "modular architecture"
            in result.content.lower()
            for result in results
        )

        assert all(
            result.source == "recall"
            for result in results
        )


def test_retrieval_results_reach_context() -> None:
    """
    Retrieval results must be transferable into Context
    and become visible in the compiled system context.
    """

    with TemporaryDirectory() as temp_dir:

        database = Database(
            Path(temp_dir) / "retrieval_context.db"
        )

        database.initialize()

        recall = RecallService(
            ConversationRepository(
                database
            )
        )

        conversation_id = (
            recall.create_conversation()
        )

        memory = LongTermMemoryService(
            LongTermMemoryRepository(
                database
            ),
            agent_id="agent-test",
        )

        created = memory.create(
            content=(
                "Jarvis uses a modular "
                "State and Knowledge architecture."
            ),
            category="project",
            subject="architecture",
            project="Jarvis",
            importance=0.9,
            confidence=1.0,
        )

        assert created.id is not None

        knowledge = KnowledgeService(
            KnowledgeRepository(
                database
            )
        )

        retrieval = RetrievalService(
            providers=[
                RecallProvider(
                    recall_service=recall,
                    conversation_id=conversation_id,
                ),
                MemoryProvider(
                    memory_service=memory,
                ),
                KnowledgeProvider(
                    knowledge_service=knowledge,
                ),
            ]
        )

        results = retrieval.search(
            "modular architecture",
            sources=["memory"],
            limit=10,
        )

        assert results

        compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        request = ContextRequest(
            user_input="Tell me about the architecture.",
            state=_build_state(
                "agent-test"
            ),
            memories=results,
        )

        context = compiler.compile(
            request
        )

        messages = context.as_messages()

        assert messages

        content = messages[0]["content"]

        assert (
            "RETRIEVED INFORMATION"
            in content
        )

        assert (
            "modular State and Knowledge architecture"
            in content
        )


def test_retrieval_source_filtering_is_preserved() -> None:
    """
    Context integration must not bypass RetrievalService
    source filtering.
    """

    with TemporaryDirectory() as temp_dir:

        database = Database(
            Path(temp_dir) / "filtering.db"
        )

        database.initialize()

        recall = RecallService(
            ConversationRepository(
                database
            )
        )

        conversation_id = (
            recall.create_conversation()
        )

        recall.add_message(
            conversation_id,
            "user",
            "Recall contains this architecture discussion.",
        )

        memory = LongTermMemoryService(
            LongTermMemoryRepository(
                database
            ),
            agent_id="agent-filter",
        )

        memory.create(
            content=(
                "Memory contains persistent architecture."
            ),
            category="project",
            subject="architecture",
            project="Jarvis",
            importance=0.9,
            confidence=1.0,
        )

        retrieval = RetrievalService(
            providers=[
                RecallProvider(
                    recall_service=recall,
                    conversation_id=conversation_id,
                ),
                MemoryProvider(
                    memory_service=memory,
                ),
            ]
        )

        recall_results = retrieval.search(
            "architecture",
            sources=["recall"],
            limit=10,
        )

        assert recall_results

        assert all(
            result.source == "recall"
            for result in recall_results
        )

        memory_results = retrieval.search(
            "architecture",
            sources=["memory"],
            limit=10,
        )

        assert memory_results

        assert all(
            result.source == "memory"
            for result in memory_results
        )


def _build_state(agent_id: str):
    """
    Build the smallest valid AgentState for the test.
    """

    from jarvis.state.models import AgentState

    return AgentState(
        agent_id=agent_id,
        conversation_id=None,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project=None,
        active_operation=None,
        operation_status="idle",
    )


def main() -> None:
    test_recall_retrieval_is_available()
    test_retrieval_results_reach_context()
    test_retrieval_source_filtering_is_preserved()

    print(
        "R2.10B.3 + R2.10B.4 "
        "Recall/Retrieval context tests passed."
    )


if __name__ == "__main__":
    main()