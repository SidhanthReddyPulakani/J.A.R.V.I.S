from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.knowledge import KnowledgeService
from jarvis.knowledge.ingestion import (
    KnowledgeIngestionService,
)
from jarvis.retrieval import (
    KnowledgeProvider,
    RetrievalService,
)
from jarvis.storage.database import Database
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "knowledge_retrieval.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        repository = KnowledgeRepository(
            database
        )

        knowledge = KnowledgeService(
            repository
        )

        ingestion = KnowledgeIngestionService(
            knowledge
        )

        source = knowledge.create_source(
            name="Jarvis Documentation",
            source_type="manual",
            origin="test://jarvis",
        )

        result = ingestion.ingest_text(
            source_id=source.id,
            title="Jarvis Architecture",
            content=(
                "Jarvis uses persistent memory.\n"
                "Jarvis uses archival knowledge.\n"
                "Knowledge can be retrieved when relevant.\n"
                "Retrieval results are provided to Context."
            ),
            chunk_size=80,
            chunk_overlap=10,
        )

        assert result.passages

        # --------------------------------------------------
        # Provider directly
        # --------------------------------------------------

        provider = KnowledgeProvider(
            knowledge
        )

        direct_results = provider.search(
            "archival knowledge",
            limit=5,
        )

        assert direct_results

        for item in direct_results:

            assert (
                item.source
                == "knowledge"
            )

            assert item.identifier is not None

            assert item.content

            assert (
                0.0
                <= item.score
                <= 1.0
            )

            assert (
                item.metadata[
                    "document_id"
                ]
                == result.document.id
            )

        # --------------------------------------------------
        # Unified Retrieval
        # --------------------------------------------------

        retrieval = RetrievalService(
            providers=[
                provider
            ]
        )

        results = retrieval.search(
            "retrieval knowledge",
            sources=["knowledge"],
            limit=5,
        )
        print("DIRECT:", direct_results)
        print("ALL PASSAGES:", result.passages)
        print("UNIFIED:", results)
        assert results

        assert all(
            result.source
            == "knowledge"
            for result in results
        )

        assert results[0].score >= 0.0

        print(
            "KNOWLEDGE RETRIEVAL RESULTS:"
        )

        for item in results:

            print(
                f"[{item.source}] "
                f"score={item.score:.3f} "
                f"id={item.identifier}"
            )

            print(
                item.content
            )

        print()

        print(
            "PASS: KnowledgeProvider retrieves passages."
        )

        print(
            "PASS: Knowledge results use RetrievalResult."
        )

        print(
            "PASS: Knowledge metadata preserves provenance."
        )

        print(
            "PASS: Knowledge integrates with RetrievalService."
        )


if __name__ == "__main__":
    main()