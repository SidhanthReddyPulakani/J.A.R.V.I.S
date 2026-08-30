from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.knowledge import (
    KnowledgeIngestionService,
    KnowledgeService,
)
from jarvis.storage.database import Database
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "knowledge_ingestion_test.db"
        )

        db = Database(
            database_path
        )

        db.initialize()

        repository = KnowledgeRepository(
            db
        )

        knowledge = KnowledgeService(
            repository
        )

        # --------------------------------------------------
        # Source
        # --------------------------------------------------

        source = knowledge.create_source(
            name="Test Documentation",
            source_type="manual",
            origin="test://documentation",
        )

        assert source.id is not None
        assert (
            source.ingestion_status
            == "pending"
        )

        # --------------------------------------------------
        # Ingestion
        # --------------------------------------------------

        content = (
            "Jarvis is a persistent personal agent.\n"
            "It maintains state and memory.\n"
            "Knowledge is stored separately from memory.\n"
            "Retrieved knowledge can later enter context."
        )

        ingestion = KnowledgeIngestionService(
            knowledge
        )

        result = ingestion.ingest_text(
            source_id=source.id,
            title="Jarvis Architecture Notes",
            content=content,
            chunk_size=60,
            chunk_overlap=10,
        )

        # --------------------------------------------------
        # Document
        # --------------------------------------------------

        assert result.document.id is not None
        assert (
            result.document.source_id
            == source.id
        )

        assert (
            result.document.title
            == "Jarvis Architecture Notes"
        )

        assert (
            result.document.content_hash
            is not None
        )

        assert len(
            result.document.content_hash
        ) == 64

        # --------------------------------------------------
        # Passages
        # --------------------------------------------------

        assert len(
            result.passages
        ) > 1

        for expected_sequence, passage in enumerate(
            result.passages
        ):

            assert passage.id is not None

            assert (
                passage.document_id
                == result.document.id
            )

            assert (
                passage.sequence
                == expected_sequence
            )

            assert passage.content.strip()

            assert (
                passage.content_hash
                is not None
            )

            assert len(
                passage.content_hash
            ) == 64

            assert (
                passage.metadata["chunking"]
                == "character"
            )

        # --------------------------------------------------
        # Source status
        # --------------------------------------------------

        restored_source = (
            knowledge.get_source(
                source.id
            )
        )

        assert restored_source is not None

        assert (
            restored_source.ingestion_status
            == "completed"
        )

        # --------------------------------------------------
        # Persistence
        # --------------------------------------------------

        db_again = Database(
            database_path
        )

        db_again.initialize()

        repository_again = (
            KnowledgeRepository(
                db_again
            )
        )

        knowledge_again = (
            KnowledgeService(
                repository_again
            )
        )

        restored_document = (
            knowledge_again.get_document(
                result.document.id
            )
        )

        assert restored_document is not None

        assert (
            restored_document.content_hash
            == result.document.content_hash
        )

        restored_passages = (
            knowledge_again.list_passages(
                result.document.id
            )
        )

        assert len(
            restored_passages
        ) == len(
            result.passages
        )

        for expected, actual in zip(
            result.passages,
            restored_passages,
        ):

            assert (
                actual.sequence
                == expected.sequence
            )

            assert (
                actual.content
                == expected.content
            )

            assert (
                actual.content_hash
                == expected.content_hash
            )

        print(
            "INGESTED DOCUMENT:"
        )

        print(
            f"Title: {result.document.title}"
        )

        print(
            f"Hash: {result.document.content_hash}"
        )

        print(
            f"Passages: {len(result.passages)}"
        )

        print()

        for passage in result.passages:

            print(
                f"[{passage.sequence}] "
                f"{passage.content}"
            )

        print()

        print(
            "PASS: Knowledge ingestion works."
        )

        print(
            "PASS: Passage chunking works."
        )

        print(
            "PASS: Knowledge hashes are deterministic."
        )

        print(
            "PASS: Ingested Knowledge persists across reload."
        )


if __name__ == "__main__":
    main()