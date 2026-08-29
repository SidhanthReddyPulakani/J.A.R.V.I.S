"""
Service layer for Jarvis Knowledge / Archive.
"""

from jarvis.knowledge.models import (
    KnowledgeDocument,
    KnowledgePassage,
    KnowledgeSource,
)
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)


class KnowledgeService:
    """
    Domain service for managing persistent Knowledge.

    The service sits above the repository and below
    ingestion/retrieval systems.
    """

    def __init__(
        self,
        repository: KnowledgeRepository,
    ) -> None:

        self.repository = repository

    # ==================================================
    # Sources
    # ==================================================

    def create_source(
        self,
        name: str,
        source_type: str,
        origin: str,
        metadata: dict | None = None,
    ) -> KnowledgeSource:

        source = KnowledgeSource(
            name=name,
            source_type=source_type,
            origin=origin,
            metadata=metadata or {},
        )

        return self.repository.create_source(
            source
        )

    def get_source(
        self,
        source_id: int,
    ) -> KnowledgeSource | None:

        return self.repository.get_source(
            source_id
        )

    def list_sources(
        self,
    ) -> list[KnowledgeSource]:

        return self.repository.list_sources()

    def update_source(
        self,
        source: KnowledgeSource,
    ) -> KnowledgeSource:

        return self.repository.update_source(
            source
        )

    def delete_source(
        self,
        source_id: int,
    ) -> bool:

        return self.repository.delete_source(
            source_id
        )

    # ==================================================
    # Documents
    # ==================================================

    def create_document(
        self,
        source_id: int,
        title: str,
        content_type: str = "text/plain",
        external_id: str | None = None,
        metadata: dict | None = None,
        content_hash: str | None = None,
    ) -> KnowledgeDocument:

        if self.repository.get_source(
            source_id
        ) is None:

            raise ValueError(
                f"Knowledge source {source_id} does not exist."
            )

        document = KnowledgeDocument(
            source_id=source_id,
            title=title,
            content_type=content_type,
            external_id=external_id,
            metadata=metadata or {},
            content_hash=content_hash,
        )

        return self.repository.create_document(
            document
        )

    def get_document(
        self,
        document_id: int,
    ) -> KnowledgeDocument | None:

        return self.repository.get_document(
            document_id
        )

    def list_documents(
        self,
        source_id: int | None = None,
    ) -> list[KnowledgeDocument]:

        return self.repository.list_documents(
            source_id
        )

    def update_document(
        self,
        document: KnowledgeDocument,
    ) -> KnowledgeDocument:

        if self.repository.get_source(
            document.source_id
        ) is None:

            raise ValueError(
                f"Knowledge source "
                f"{document.source_id} does not exist."
            )

        return self.repository.update_document(
            document
        )

    def delete_document(
        self,
        document_id: int,
    ) -> bool:

        return self.repository.delete_document(
            document_id
        )

    # ==================================================
    # Passages
    # ==================================================

    def create_passage(
        self,
        document_id: int,
        sequence: int,
        content: str,
        metadata: dict | None = None,
        content_hash: str | None = None,
    ) -> KnowledgePassage:

        if self.repository.get_document(
            document_id
        ) is None:

            raise ValueError(
                f"Knowledge document {document_id} "
                "does not exist."
            )

        passage = KnowledgePassage(
            document_id=document_id,
            sequence=sequence,
            content=content,
            metadata=metadata or {},
            content_hash=content_hash,
        )

        return self.repository.create_passage(
            passage
        )

    def get_passage(
        self,
        passage_id: int,
    ) -> KnowledgePassage | None:

        return self.repository.get_passage(
            passage_id
        )

    def list_passages(
        self,
        document_id: int,
    ) -> list[KnowledgePassage]:

        if self.repository.get_document(
            document_id
        ) is None:

            raise ValueError(
                f"Knowledge document {document_id} "
                "does not exist."
            )

        return self.repository.list_passages(
            document_id
        )

    def update_passage(
        self,
        passage: KnowledgePassage,
    ) -> KnowledgePassage:

        if self.repository.get_document(
            passage.document_id
        ) is None:

            raise ValueError(
                f"Knowledge document "
                f"{passage.document_id} does not exist."
            )

        return self.repository.update_passage(
            passage
        )

    def delete_passage(
        self,
        passage_id: int,
    ) -> bool:

        return self.repository.delete_passage(
            passage_id
        )

    def replace_document_passages(
        self,
        document_id: int,
        passages: list[KnowledgePassage],
    ) -> list[KnowledgePassage]:
        """
        Replace all passages belonging to a document.
        """

        if self.repository.get_document(
            document_id
        ) is None:

            raise ValueError(
                f"Knowledge document {document_id} "
                "does not exist."
            )

        for passage in passages:

            if passage.document_id != document_id:

                raise ValueError(
                    "All passages must belong to "
                    "the supplied document."
                )

        self.repository.delete_passages_for_document(
            document_id
        )

        return [
            self.repository.create_passage(
                passage
            )
            for passage in passages
        ]

    # ==================================================
    # Retrieval Support
    # ==================================================

    def search_passages(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[KnowledgePassage]:
        """
        Search archived Knowledge passages lexically.

        This is intentionally a simple deterministic search
        foundation for R2.4F.

        Semantic/vector retrieval can be added behind the
        retrieval provider architecture later.
        """

        if not query.strip():
            raise ValueError(
                "Knowledge search query cannot be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Knowledge search limit must be positive."
            )

        passages = (
            self.repository.search_passages(
                query,
                limit=limit,
            )
        )

        return passages