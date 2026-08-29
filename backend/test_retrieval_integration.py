from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.knowledge import KnowledgeService
from jarvis.knowledge.ingestion import (
    KnowledgeIngestionService,
)

from jarvis.memory.long_term import (
    LongTermMemoryService,
)

from jarvis.relationships.models import (
    Relationship,
)

from jarvis.relationships.store import (
    RelationshipStore,
)

from jarvis.recall.service import (
    RecallService,
)

from jarvis.retrieval import (
    KnowledgeProvider,
    MemoryProvider,
    RecallProvider,
    RelationshipProvider,
    RetrievalService,
    build_retrieval_service,
)

from jarvis.storage.database import (
    Database,
)

from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)

from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)

from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)


def build_services(database: Database):
    """
    Construct fresh information services from a database.

    This helper is intentionally used for the reload test.
    Nothing is reused from the previous service instances.
    """

    recall = RecallService(
        ConversationRepository(
            database
        )
    )

    memory = LongTermMemoryService(
        LongTermMemoryRepository(
            database
        ),
        agent_id="test-jarvis",
    )

    knowledge = KnowledgeService(
        KnowledgeRepository(
            database
        )
    )

    relationships = RelationshipStore(database)

    return (
        recall,
        memory,
        knowledge,
        relationships,
    )


def build_retrieval(
    recall,
    memory,
    knowledge,
    relationships,
    conversation_id,
):
    """
    Construct a fresh unified RetrievalService.
    """

    return build_retrieval_service(
        recall_service=recall,
        memory_service=memory,
        relationship_store=relationships,
        knowledge_service=knowledge,
        conversation_id=conversation_id,
    )


def main() -> None:

    # ==================================================
    # Use an isolated database.
    #
    # This makes G.5 a genuine persistence/reload test
    # instead of relying on the application's database.
    # ==================================================

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "retrieval_integration.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        # ==================================================
        # Initial service construction
        # ==================================================

        (
            recall,
            memory,
            knowledge,
            relationships,
        ) = build_services(
            database
        )

        # ==================================================
        # Seed Recall
        # ==================================================

        conversation_id = (
            recall.create_conversation()
        )

        recall.add_message(
            conversation_id,
            "user",
            "I am working on Jarvis retrieval architecture.",
        )

        # ==================================================
        # Seed Long-Term Memory
        # ==================================================

        memory.create(
            content=(
                "Jarvis uses unified retrieval "
                "for modular information access."
            ),
            category="project",
            subject="retrieval",
            project="Jarvis",
            importance=0.9,
            confidence=1.0,
        )

        # ==================================================
        # Seed Relationship
        # ==================================================

        relationships.save(
            Relationship(
                id=None,
                source="Jarvis",
                target_type="developed_with",
                target="Cursor",
                confidence=0.9,
            )
        )

        # ==================================================
        # Seed Knowledge
        # ==================================================

        source = knowledge.create_source(
            name="Integration Test",
            source_type="test",
            origin="test://retrieval",
        )

        ingestion = KnowledgeIngestionService(
            knowledge
        )

        ingestion_result = (
            ingestion.ingest_text(
                source_id=source.id,
                title="Jarvis Retrieval",
                content=(
                    "Jarvis uses unified retrieval "
                    "to combine information from "
                    "memory, recall, relationships, "
                    "and archival knowledge."
                ),
                chunk_size=120,
                chunk_overlap=10,
            )
        )

        assert ingestion_result.passages

        # ==================================================
        # Build initial Retrieval
        # ==================================================

        retrieval = build_retrieval(
            recall,
            memory,
            knowledge,
            relationships,
            conversation_id,
        )

        # ==================================================
        # Provider registration
        # ==================================================

        provider_names = (
            retrieval.providers()
        )

        print(
            "REGISTERED PROVIDERS:"
        )

        for name in provider_names:
            print(
                f" - {name}"
            )

        assert "recall" in provider_names
        assert "memory" in provider_names
        assert "relationship" in provider_names
        assert "knowledge" in provider_names

        print(
            "PASS: All four providers are registered."
        )

        # ==================================================
        # G.3 — Source filtering
        # ==================================================

        knowledge_results = (
            retrieval.search(
                "archival knowledge",
                sources=["knowledge"],
                limit=10,
            )
        )

        assert knowledge_results

        assert all(
            result.source == "knowledge"
            for result in knowledge_results
        )

        print(
            "PASS: Knowledge source filtering works."
        )

        memory_results = (
            retrieval.search(
                "unified retrieval",
                sources=["memory"],
                limit=10,
            )
        )

        assert memory_results

        assert all(
            result.source == "memory"
            for result in memory_results
        )

        print(
            "PASS: Memory source filtering works."
        )

        recall_results = (
            retrieval.search(
                "Jarvis retrieval",
                sources=["recall"],
                limit=10,
            )
        )

        assert recall_results

        assert all(
            result.source == "recall"
            for result in recall_results
        )

        print(
            "PASS: Recall source filtering works."
        )

        relationship_results = (
            retrieval.search(
                "Cursor",
                sources=["relationship"],
                limit=10,
            )
        )

        assert relationship_results

        assert all(
            result.source == "relationship"
            for result in relationship_results
        )

        print(
            "PASS: Relationship source filtering works."
        )

        # ==================================================
        # Multiple-source filtering
        # ==================================================

        selected_results = (
            retrieval.search(
                "Jarvis retrieval",
                sources=[
                    "memory",
                    "knowledge",
                ],
                limit=10,
            )
        )

        assert selected_results

        selected_sources = {
            result.source
            for result in selected_results
        }

        assert selected_sources <= {
            "memory",
            "knowledge",
        }

        assert (
            "knowledge"
            in selected_sources
        )

        print(
            "PASS: Multi-source filtering works."
        )

        # ==================================================
        # G.4 — Global ranking
        # ==================================================

        unified_results = (
            retrieval.search(
                "Jarvis retrieval",
                limit=20,
            )
        )

        assert unified_results

        print()
        print(
            "UNIFIED RANKED RESULTS:"
        )

        for result in unified_results:

            print(
                f"[{result.source}] "
                f"score={result.score:.3f} "
                f"id={result.identifier}"
            )

            print(
                f"  {result.content}"
            )

        for result in unified_results:

            assert result.source
            assert result.content

            assert isinstance(
                result.score,
                float,
            )

            assert (
                0.0
                <= result.score
                <= 1.0
            )

        scores = [
            result.score
            for result in unified_results
        ]

        assert scores == sorted(
            scores,
            reverse=True,
        )

        print(
            "PASS: Results are globally ranked "
            "by descending score."
        )

        unified_sources = {
            result.source
            for result in unified_results
        }

        print()
        print(
            "PARTICIPATING SOURCES:"
        )

        for source_name in sorted(
            unified_sources
        ):
            print(
                f" - {source_name}"
            )

        assert (
            len(unified_sources)
            >= 2
        )

        print(
            "PASS: Unified retrieval combines "
            "multiple providers."
        )

        # ==================================================
        # G.4 — Selected-provider global ranking
        # ==================================================

        knowledge_only = (
            retrieval.search(
                "Jarvis retrieval",
                sources=["knowledge"],
                limit=10,
            )
        )

        memory_only = (
            retrieval.search(
                "Jarvis retrieval",
                sources=["memory"],
                limit=10,
            )
        )

        combined = (
            retrieval.search(
                "Jarvis retrieval",
                sources=[
                    "knowledge",
                    "memory",
                ],
                limit=20,
            )
        )

        assert combined

        combined_scores = [
            result.score
            for result in combined
        ]

        assert combined_scores == sorted(
            combined_scores,
            reverse=True,
        )

        if knowledge_only and memory_only:

            combined_sources = {
                result.source
                for result in combined
            }

            assert (
                "knowledge"
                in combined_sources
            )

            assert (
                "memory"
                in combined_sources
            )

        print(
            "PASS: Global ranking operates across "
            "selected providers."
        )

        # ==================================================
        # Invalid provider filtering
        # ==================================================

        try:

            retrieval.search(
                "Jarvis",
                sources=["does-not-exist"],
                limit=10,
            )

        except KeyError as exc:

            assert (
                "Unknown retrieval source"
                in str(exc)
            )

            print(
                "PASS: Unknown retrieval sources "
                "are rejected explicitly."
            )

        else:

            raise AssertionError(
                "Expected unknown retrieval source "
                "to raise KeyError."
            )

        # ==================================================
        # G.5 — Persistence / Reload
        # ==================================================
        #
        # The important part:
        #
        # We throw away the existing service and
        # provider objects and reconstruct everything
        # from the same SQLite database.
        #
        # This verifies that Retrieval depends on
        # persistent information, not in-memory state.
        # ==================================================

        (
            reloaded_recall,
            reloaded_memory,
            reloaded_knowledge,
            reloaded_relationships,
        ) = build_services(
            database
        )

        reloaded_retrieval = build_retrieval(
            reloaded_recall,
            reloaded_memory,
            reloaded_knowledge,
            reloaded_relationships,
            conversation_id,
        )

        # --------------------------------------------------
        # Provider registration survives reconstruction
        # --------------------------------------------------

        reloaded_provider_names = (
            reloaded_retrieval.providers()
        )

        assert (
            reloaded_provider_names
            == provider_names
        )

        print(
            "PASS: Retrieval providers can be "
            "reconstructed after reload."
        )

        # --------------------------------------------------
        # Recall survives reload
        # --------------------------------------------------

        reloaded_recall_results = (
            reloaded_retrieval.search(
                "Jarvis retrieval architecture",
                sources=["recall"],
                limit=10,
            )
        )

        assert reloaded_recall_results

        assert any(
            "retrieval architecture"
            in result.content.lower()
            for result in reloaded_recall_results
        )

        print(
            "PASS: Recall retrieval survives reload."
        )

        # --------------------------------------------------
        # Long-Term Memory survives reload
        # --------------------------------------------------

        reloaded_memory_results = (
            reloaded_retrieval.search(
                "unified retrieval",
                sources=["memory"],
                limit=10,
            )
        )

        assert reloaded_memory_results

        assert any(
            "unified retrieval"
            in result.content.lower()
            for result in reloaded_memory_results
        )

        print(
            "PASS: Memory retrieval survives reload."
        )

        # --------------------------------------------------
        # Knowledge survives reload
        # --------------------------------------------------

        reloaded_knowledge_results = (
            reloaded_retrieval.search(
                "archival knowledge",
                sources=["knowledge"],
                limit=10,
            )
        )

        assert reloaded_knowledge_results

        assert any(
            "archival knowledge"
            in result.content.lower()
            for result in reloaded_knowledge_results
        )

        print(
            "PASS: Knowledge retrieval survives reload."
        )

        # --------------------------------------------------
        # Relationship survives reload
        # --------------------------------------------------

        reloaded_relationship_results = (
            reloaded_retrieval.search(
                "Cursor",
                sources=["relationship"],
                limit=10,
            )
        )

        assert reloaded_relationship_results

        assert any(
            "Cursor"
            in result.content
            for result in reloaded_relationship_results
        )

        print(
            "PASS: Relationship retrieval survives reload."
        )

        # --------------------------------------------------
        # Unified retrieval survives reload
        # --------------------------------------------------

        reloaded_unified_results = (
            reloaded_retrieval.search(
                "Jarvis retrieval",
                limit=20,
            )
        )

        assert reloaded_unified_results

        reloaded_sources = {
            result.source
            for result in reloaded_unified_results
        }

        assert (
            "recall"
            in reloaded_sources
        )

        assert (
            "memory"
            in reloaded_sources
        )

        assert (
            "knowledge"
            in reloaded_sources
        )

        print(
            "PASS: Unified retrieval survives reload."
        )

        # --------------------------------------------------
        # Global ranking still holds after reload
        # --------------------------------------------------

        reloaded_scores = [
            result.score
            for result in reloaded_unified_results
        ]

        assert reloaded_scores == sorted(
            reloaded_scores,
            reverse=True,
        )

        print(
            "PASS: Global ranking survives reload."
        )

        # ==================================================
        # G.6 — Final Retrieval Integration
        # ==================================================

        final_results = (
            reloaded_retrieval.search(
                "Jarvis retrieval",
                limit=20,
            )
        )

        assert final_results

        # --------------------------------------------------
        # Common result contract
        # --------------------------------------------------

        for result in final_results:

            assert isinstance(
                result.source,
                str,
            )

            assert result.source

            assert result.identifier is not None

            assert isinstance(
                result.content,
                str,
            )

            assert result.content.strip()

            assert isinstance(
                result.score,
                float,
            )

            assert (
                0.0
                <= result.score
                <= 1.0
            )

            assert isinstance(
                result.metadata,
                dict,
            )

        print(
            "PASS: Final RetrievalResult contract "
            "is consistent across providers."
        )

        # --------------------------------------------------
        # All expected persistent information domains
        # participate in the final integrated retrieval.
        # --------------------------------------------------

        final_sources = {
            result.source
            for result in final_results
        }

        assert (
            "recall"
            in final_sources
        )

        assert (
            "memory"
            in final_sources
        )

        assert (
            "knowledge"
            in final_sources
        )

        assert (
            "relationship"
            in final_sources
        )

        print(
            "PASS: Final retrieval includes all "
            "four information providers."
        )

        # --------------------------------------------------
        # Final global ordering
        # --------------------------------------------------

        final_scores = [
            result.score
            for result in final_results
        ]

        assert final_scores == sorted(
            final_scores,
            reverse=True,
        )

        print(
            "PASS: Final integrated results are "
            "globally ranked."
        )

        # --------------------------------------------------
        # Global limit
        # --------------------------------------------------

        limited_results = (
            reloaded_retrieval.search(
                "Jarvis retrieval",
                limit=3,
            )
        )

        assert (
            len(limited_results)
            <= 3
        )

        print(
            "PASS: Global result limit is respected."
        )

        # --------------------------------------------------
        # Source filtering still works after the
        # complete integration/reload cycle.
        # --------------------------------------------------

        final_knowledge = (
            reloaded_retrieval.search(
                "archival knowledge",
                sources=["knowledge"],
                limit=5,
            )
        )

        assert final_knowledge

        assert all(
            result.source == "knowledge"
            for result in final_knowledge
        )

        print(
            "PASS: Source filtering remains correct "
            "after reload."
        )

        # ==================================================
        # Complete
        # ==================================================

        print()
        print(
            "R2.4G.5 — Persistence / Reload PASS."
        )

        print(
            "R2.4G.6 — Retrieval Integration Tests PASS."
        )

        print()
        print(
            "R2.4G — RETRIEVAL INTEGRATION COMPLETE."
        )


if __name__ == "__main__":
    main()