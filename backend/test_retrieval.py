from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory.long_term import (
    LongTermMemoryService,
)
from jarvis.recall.service import (
    RecallService,
)
from jarvis.relationships.models import (
    Relationship,
)
from jarvis.relationships.store import (
    RelationshipStore,
)
from jarvis.retrieval import (
    MemoryProvider,
    RecallProvider,
    RelationshipProvider,
    RetrievalService,
)
from jarvis.storage.database import (
    Database,
)
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)
from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "retrieval_test.db"
        )

        db = Database(
            database_path
        )

        db.initialize()

        # ==================================================
        # Recall setup
        # ==================================================

        recall_repository = (
            ConversationRepository(
                db
            )
        )

        recall = RecallService(
            recall_repository
        )

        conversation_id = (
            recall.create_conversation()
        )

        recall.add_message(
            conversation_id,
            "user",
            "I am building Jarvis with Cursor.",
        )

        recall.add_message(
            conversation_id,
            "assistant",
            "That sounds good.",
        )

        # ==================================================
        # Long-Term Memory setup
        # ==================================================

        memory_repository = (
            LongTermMemoryRepository(
                db
            )
        )

        memory = LongTermMemoryService(
            memory_repository,
            agent_id="test-jarvis",
        )

        memory.create(
            content=(
                "Sidhanth uses Cursor as the "
                "primary editor for Jarvis."
            ),
            category="preference",
            subject="editor",
            project="Jarvis",
            importance=0.9,
            confidence=1.0,
        )

        memory.create(
            content=(
                "Jarvis is a modular local "
                "personal assistant."
            ),
            category="project",
            subject="Jarvis",
            project="Jarvis",
            importance=0.95,
            confidence=1.0,
        )

        # ==================================================
        # Relationship setup
        # ==================================================

        relationships = (
            RelationshipStore()
        )

        relationship = Relationship(
            id=None,
            source="browser",
            target_type="application",
            target="Brave",
            confidence=0.9,
        )

        relationships.save(
            relationship
        )

        # ==================================================
        # Build providers
        # ==================================================

        recall_provider = RecallProvider(
            recall_service=recall,
            conversation_id=conversation_id,
        )

        memory_provider = MemoryProvider(
            memory_service=memory,
        )

        relationship_provider = (
            RelationshipProvider(
                relationship_store=relationships
            )
        )

        retrieval = RetrievalService(
            providers=[
                recall_provider,
                memory_provider,
                relationship_provider,
            ]
        )

        # ==================================================
        # Provider registration
        # ==================================================

        assert set(
            retrieval.providers()
        ) == {
            "recall",
            "memory",
            "relationship",
        }

        print(
            "REGISTERED PROVIDERS:"
        )

        for provider in retrieval.providers():
            print(
                f" - {provider}"
            )

        print()

        # ==================================================
        # Memory retrieval
        # ==================================================

        results = retrieval.search(
            "Cursor",
            sources=["memory"],
            limit=10,
        )

        assert len(results) == 1

        assert (
            results[0].source
            == "memory"
        )

        assert (
            "Cursor"
            in results[0].content
        )

        assert (
            results[0].score > 0
        )

        print(
            "MEMORY RESULT:"
        )

        print(
            results[0]
        )

        print()

        # ==================================================
        # Recall retrieval
        # ==================================================

        results = retrieval.search(
            "Cursor",
            sources=["recall"],
            limit=10,
        )

        assert len(results) == 1

        assert (
            results[0].source
            == "recall"
        )

        assert (
            "Cursor"
            in results[0].content
        )

        print(
            "RECALL RESULT:"
        )

        print(
            results[0]
        )

        print()

        # ==================================================
        # Relationship retrieval
        # ==================================================

        results = retrieval.search(
            "browser Brave",
            sources=["relationship"],
            limit=10,
        )

        assert len(results) == 1

        assert (
            results[0].source
            == "relationship"
        )

        assert (
            "Brave"
            in results[0].content
        )

        print(
            "RELATIONSHIP RESULT:"
        )

        print(
            results[0]
        )

        print()

        # ==================================================
        # Unified retrieval
        # ==================================================

        results = retrieval.search(
            "Cursor",
            limit=10,
        )

        assert len(results) == 2

        assert all(
            result.source
            in {
                "memory",
                "recall",
            }
            for result in results
        )

        print(
            "UNIFIED RESULTS:"
        )

        for result in results:
            print(
                f"[{result.source}] "
                f"{result.score:.3f} "
                f"{result.content}"
            )

        print()

        # ==================================================
        # Global limit
        # ==================================================

        results = retrieval.search(
            "Jarvis",
            limit=1,
        )

        assert len(results) == 1

        # ==================================================
        # Source filtering
        # ==================================================

        results = retrieval.search(
            "Jarvis",
            sources=["memory"],
            limit=10,
        )

        assert all(
            result.source == "memory"
            for result in results
        )

        # ==================================================
        # Unknown source protection
        # ==================================================

        try:

            retrieval.search(
                "test",
                sources=["does-not-exist"],
            )

        except KeyError:
            pass

        else:

            raise AssertionError(
                "Unknown retrieval source "
                "was accepted."
            )

        # ==================================================
        # Empty Knowledge provider
        #
        # Knowledge is not yet present in this ZIP.
        # The provider should therefore safely return
        # no results rather than breaking Retrieval.
        # ==================================================

        from jarvis.retrieval.providers import (
            KnowledgeProvider,
        )

        knowledge_provider = (
            KnowledgeProvider()
        )

        assert (
            knowledge_provider.search(
                "anything",
                limit=10,
            )
            == []
        )

        print(
            "PASS: Knowledge provider "
            "is safely extensible."
        )

        print(
            "PASS: Retrieval architecture works."
        )


if __name__ == "__main__":
    main()