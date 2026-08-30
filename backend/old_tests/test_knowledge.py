"""Knowledge repository/service smoke test.

Run from backend/:

    python test_knowledge.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.knowledge import KnowledgeService
from jarvis.storage.database import Database
from jarvis.storage.repositories.knowledge import KnowledgeRepository


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "knowledge_test.db"

        db = Database(database_path)
        db.initialize()

        repository = KnowledgeRepository(db)
        service = KnowledgeService(repository)

        # --------------------------------------------------
        # Source
        # --------------------------------------------------
        source = service.create_source(
            name="Jarvis Test Documentation",
            source_type="file",
            origin="test://jarvis/docs",
            metadata={"project": "Jarvis"},
        )

        assert source.id is not None

        loaded_source = service.get_source(source.id)
        assert loaded_source is not None
        assert loaded_source.name == "Jarvis Test Documentation"
        assert loaded_source.metadata["project"] == "Jarvis"

        # --------------------------------------------------
        # Document
        # --------------------------------------------------
        document = service.create_document(
            source_id=source.id,
            title="architecture.md",
            content_type="text/markdown",
            external_id="architecture.md",
            metadata={"section_count": 3},
            content_hash="document-hash",
        )

        assert document.id is not None

        loaded_document = service.get_document(document.id)
        assert loaded_document is not None
        assert loaded_document.source_id == source.id
        assert loaded_document.title == "architecture.md"
        assert loaded_document.metadata["section_count"] == 3

        documents = service.list_documents(source_id=source.id)
        assert len(documents) == 1

        # --------------------------------------------------
        # Passages
        # --------------------------------------------------
        passage_1 = service.create_passage(
            document_id=document.id,
            sequence=0,
            content="Jarvis is a persistent personal agent.",
            metadata={"section": "Introduction"},
            content_hash="passage-1",
        )

        passage_2 = service.create_passage(
            document_id=document.id,
            sequence=1,
            content="The agent uses persistent state.",
            metadata={"section": "Architecture"},
            content_hash="passage-2",
        )

        assert passage_1.id is not None
        assert passage_2.id is not None

        passages = service.list_passages(document.id)
        assert len(passages) == 2
        assert passages[0].sequence == 0
        assert passages[1].sequence == 1

        # --------------------------------------------------
        # Update
        # --------------------------------------------------
        passage_1.content = "Jarvis is a persistent local personal agent."
        updated = service.update_passage(passage_1)

        assert updated.content == passage_1.content

        loaded = service.get_passage(passage_1.id)
        assert loaded is not None
        assert loaded.content == passage_1.content

        # --------------------------------------------------
        # Replace passages
        # --------------------------------------------------
        replacement = service.create_passage(
            document_id=document.id,
            sequence=0,
            content="Temporary replacement.",
        )

        replaced = service.replace_document_passages(
            document.id,
            [replacement],
        )

        assert len(replaced) == 1

        passages = service.list_passages(document.id)
        assert len(passages) == 1
        assert passages[0].content == "Temporary replacement."

        # --------------------------------------------------
        # Validation
        # --------------------------------------------------
        try:
            service.create_document(
                source_id=999999,
                title="Invalid document",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Document creation should reject a nonexistent source."
            )

        try:
            service.create_passage(
                document_id=999999,
                sequence=0,
                content="Invalid passage",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Passage creation should reject a nonexistent document."
            )

        print("PASS: Knowledge source CRUD works.")
        print("PASS: Knowledge document CRUD works.")
        print("PASS: Knowledge passage CRUD works.")
        print("PASS: Knowledge hierarchy is enforced.")
        print("PASS: Knowledge metadata persists.")
        print("PASS: Passage replacement works.")


if __name__ == "__main__":
    main()
