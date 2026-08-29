"""
Knowledge ingestion pipeline.

R2.4E provides a deterministic text-ingestion path:

    raw text
        ↓
    normalization
        ↓
    document
        ↓
    passages
        ↓
    persistent archive

This module intentionally does not perform embeddings,
vector indexing, or semantic retrieval.
"""

from dataclasses import dataclass
import hashlib

from jarvis.knowledge.models import (
    KnowledgeDocument,
    KnowledgePassage,
)
from jarvis.knowledge.service import KnowledgeService


# ==================================================
# Ingestion Result
# ==================================================


@dataclass
class KnowledgeIngestionResult:
    """
    Result of a successful Knowledge ingestion operation.
    """

    document: KnowledgeDocument
    passages: list[KnowledgePassage]


# ==================================================
# Ingestion Service
# ==================================================


class KnowledgeIngestionService:
    """
    Converts raw text into persistent Knowledge.

    Responsibilities:

        - validate ingestion input
        - normalize line endings
        - compute deterministic hashes
        - create the KnowledgeDocument
        - split content into passages
        - persist passages
        - maintain source ingestion status

    Retrieval and embeddings are deliberately outside
    this service.
    """

    def __init__(
        self,
        knowledge: KnowledgeService,
    ) -> None:

        self.knowledge = knowledge

    # ==================================================
    # Public API
    # ==================================================

    def ingest_text(
        self,
        *,
        source_id: int,
        title: str,
        content: str,
        content_type: str = "text/plain",
        external_id: str | None = None,
        metadata: dict | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
    ) -> KnowledgeIngestionResult:
        """
        Ingest raw text into a Knowledge source.

        The operation creates one document and a deterministic
        ordered set of passages.

        Args:
            source_id:
                Existing KnowledgeSource ID.

            title:
                Human-readable document title.

            content:
                Raw document text.

            content_type:
                MIME-like content type.

            external_id:
                Optional identifier supplied by the source.

            metadata:
                Document-level metadata.

            chunk_size:
                Maximum passage size in characters.

            chunk_overlap:
                Number of characters shared between adjacent
                passages.

        Returns:
            KnowledgeIngestionResult

        Raises:
            ValueError:
                If the source, content, or chunk configuration
                is invalid.
        """

        self._validate_input(
            content=content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        source = self.knowledge.get_source(
            source_id
        )

        if source is None:
            raise ValueError(
                f"Knowledge source {source_id} does not exist."
            )

        normalized_content = (
            self._normalize_text(content)
        )

        source.ingestion_status = "ingesting"
        self.knowledge.update_source(
            source
        )

        document: KnowledgeDocument | None = None

        try:

            document_hash = (
                self._hash_text(
                    normalized_content
                )
            )

            document = self.knowledge.create_document(
                source_id=source_id,
                title=title,
                content_type=content_type,
                external_id=external_id,
                metadata=metadata or {},
                content_hash=document_hash,
            )

            chunks = self._chunk_text(
                normalized_content,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            passages: list[KnowledgePassage] = []

            for sequence, chunk in enumerate(
                chunks
            ):

                passage = (
                    self.knowledge.create_passage(
                        document_id=document.id,
                        sequence=sequence,
                        content=chunk,
                        metadata={
                            "chunking": "character",
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                        },
                        content_hash=self._hash_text(
                            chunk
                        ),
                    )
                )

                passages.append(
                    passage
                )

            source.ingestion_status = "completed"

            self.knowledge.update_source(
                source
            )

            return KnowledgeIngestionResult(
                document=document,
                passages=passages,
            )

        except Exception:

            source.ingestion_status = "failed"

            try:
                self.knowledge.update_source(
                    source
                )
            except Exception:
                pass

            self._cleanup_partial_document(
                document
            )

            raise

    # ==================================================
    # Validation
    # ==================================================

    @staticmethod
    def _validate_input(
        *,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:

        if not isinstance(
            content,
            str,
        ):
            raise ValueError(
                "Knowledge ingestion content must be a string."
            )

        if not content.strip():
            raise ValueError(
                "Knowledge ingestion content cannot be empty."
            )

        if chunk_size <= 0:
            raise ValueError(
                "chunk_size must be positive."
            )

        if chunk_overlap < 0:
            raise ValueError(
                "chunk_overlap cannot be negative."
            )

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

    # ==================================================
    # Normalization
    # ==================================================

    @staticmethod
    def _normalize_text(
        content: str,
    ) -> str:
        """
        Normalize line endings without altering document
        content semantics.
        """

        normalized = content.replace(
            "\r\n",
            "\n",
        )

        normalized = normalized.replace(
            "\r",
            "\n",
        )

        return normalized.strip()

    # ==================================================
    # Hashing
    # ==================================================

    @staticmethod
    def _hash_text(
        content: str,
    ) -> str:
        """
        Return a deterministic SHA-256 hash.
        """

        return hashlib.sha256(
            content.encode(
                "utf-8"
            )
        ).hexdigest()

    # ==================================================
    # Chunking
    # ==================================================

    @staticmethod
    def _chunk_text(
        content: str,
        *,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[str]:
        """
        Deterministically split text into overlapping chunks.

        Character offsets are used deliberately for R2.4E.
        More advanced semantic/paragraph-aware chunking can
        be introduced later without changing the persistence
        model.
        """

        chunks: list[str] = []

        start = 0
        length = len(content)

        step = (
            chunk_size
            - chunk_overlap
        )

        while start < length:

            end = min(
                start + chunk_size,
                length,
            )

            chunk = content[
                start:end
            ].strip()

            if chunk:
                chunks.append(
                    chunk
                )

            if end >= length:
                break

            start += step

        return chunks

    # ==================================================
    # Failure cleanup
    # ==================================================

    def _cleanup_partial_document(
        self,
        document: KnowledgeDocument | None,
    ) -> None:
        """
        Remove partially persisted ingestion output.

        This is a compensating cleanup for failures occurring
        after the document has been created.
        """

        if document is None:
            return

        if document.id is None:
            return

        try:
            self.knowledge.delete_document(
                document.id
            )
        except Exception:
            pass