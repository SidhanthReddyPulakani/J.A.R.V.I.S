"""
Persistence repository for Jarvis Knowledge / Archive.
"""

import json
from typing import Any

from jarvis.knowledge.models import (
    KnowledgeDocument,
    KnowledgePassage,
    KnowledgeSource,
)
from jarvis.storage.repositories.base import BaseRepository


class KnowledgeRepository(BaseRepository):
    """Persistence operations for Knowledge entities."""

    # ==================================================
    # Serialization helpers
    # ==================================================

    @staticmethod
    def _encode_metadata(
        metadata: dict[str, Any],
    ) -> str:
        return json.dumps(
            metadata,
            ensure_ascii=False,
        )

    @staticmethod
    def _decode_metadata(
        value: str | None,
    ) -> dict[str, Any]:

        if not value:
            return {}

        decoded = json.loads(value)

        if not isinstance(decoded, dict):
            raise ValueError(
                "Knowledge metadata must decode to a dictionary."
            )

        return decoded

    # ==================================================
    # Sources
    # ==================================================

    def create_source(
        self,
        source: KnowledgeSource,
    ) -> KnowledgeSource:

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO knowledge_sources (
                    name,
                    source_type,
                    origin,
                    metadata,
                    ingestion_status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.name,
                    source.source_type,
                    source.origin,
                    self._encode_metadata(
                        source.metadata
                    ),
                    source.ingestion_status,
                    source.created_at,
                    source.updated_at,
                ),
            )

            source.id = cursor.lastrowid

        return source

    def get_source(
        self,
        source_id: int,
    ) -> KnowledgeSource | None:

        row = self.database.fetch_one(
            """
            SELECT
                id,
                name,
                source_type,
                origin,
                metadata,
                ingestion_status,
                created_at,
                updated_at
            FROM knowledge_sources
            WHERE id = ?
            """,
            (source_id,),
        )

        if row is None:
            return None

        return KnowledgeSource(
            id=row[0],
            name=row[1],
            source_type=row[2],
            origin=row[3],
            metadata=self._decode_metadata(
                row[4]
            ),
            ingestion_status=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def list_sources(
        self,
    ) -> list[KnowledgeSource]:

        rows = self.database.fetch_all(
            """
            SELECT
                id,
                name,
                source_type,
                origin,
                metadata,
                ingestion_status,
                created_at,
                updated_at
            FROM knowledge_sources
            ORDER BY id ASC
            """
        )

        return [
            KnowledgeSource(
                id=row[0],
                name=row[1],
                source_type=row[2],
                origin=row[3],
                metadata=self._decode_metadata(
                    row[4]
                ),
                ingestion_status=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    def update_source(
        self,
        source: KnowledgeSource,
    ) -> KnowledgeSource:

        if source.id is None:
            raise ValueError(
                "Cannot update a source without an id."
            )

        source.touch()

        self.database.execute(
            """
            UPDATE knowledge_sources
            SET
                name = ?,
                source_type = ?,
                origin = ?,
                metadata = ?,
                ingestion_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                source.name,
                source.source_type,
                source.origin,
                self._encode_metadata(
                    source.metadata
                ),
                source.ingestion_status,
                source.updated_at,
                source.id,
            ),
        )

        return source

    def delete_source(
        self,
        source_id: int,
    ) -> bool:

        existing = self.database.fetch_one(
            """
            SELECT id
            FROM knowledge_sources
            WHERE id = ?
            """,
            (source_id,),
        )

        if existing is None:
            return False

        self.database.execute(
            """
            DELETE FROM knowledge_sources
            WHERE id = ?
            """,
            (source_id,),
        )

        return True

    # ==================================================
    # Documents
    # ==================================================

    def create_document(
        self,
        document: KnowledgeDocument,
    ) -> KnowledgeDocument:

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO knowledge_documents (
                    source_id,
                    title,
                    content_type,
                    external_id,
                    metadata,
                    content_hash,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.source_id,
                    document.title,
                    document.content_type,
                    document.external_id,
                    self._encode_metadata(
                        document.metadata
                    ),
                    document.content_hash,
                    document.updated_at,
                    document.updated_at,
                ),
            )

            document.id = cursor.lastrowid

        return document

    def get_document(
        self,
        document_id: int,
    ) -> KnowledgeDocument | None:

        row = self.database.fetch_one(
            """
            SELECT
                id,
                source_id,
                title,
                content_type,
                external_id,
                metadata,
                content_hash,
                created_at,
                updated_at
            FROM knowledge_documents
            WHERE id = ?
            """,
            (document_id,),
        )

        if row is None:
            return None

        return KnowledgeDocument(
            id=row[0],
            source_id=row[1],
            title=row[2],
            content_type=row[3],
            external_id=row[4],
            metadata=self._decode_metadata(
                row[5]
            ),
            content_hash=row[6],
            created_at=row[7],
            updated_at=row[8],
        )

    def list_documents(
        self,
        source_id: int | None = None,
    ) -> list[KnowledgeDocument]:

        if source_id is None:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source_id,
                    title,
                    content_type,
                    external_id,
                    metadata,
                    content_hash,
                    created_at,
                    updated_at
                FROM knowledge_documents
                ORDER BY id ASC
                """
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source_id,
                    title,
                    content_type,
                    external_id,
                    metadata,
                    content_hash,
                    created_at,
                    updated_at
                FROM knowledge_documents
                WHERE source_id = ?
                ORDER BY id ASC
                """,
                (source_id,),
            )

        return [
            KnowledgeDocument(
                id=row[0],
                source_id=row[1],
                title=row[2],
                content_type=row[3],
                external_id=row[4],
                metadata=self._decode_metadata(
                    row[5]
                ),
                content_hash=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]

    def update_document(
        self,
        document: KnowledgeDocument,
    ) -> KnowledgeDocument:

        if document.id is None:
            raise ValueError(
                "Cannot update a document without an id."
            )

        document.touch()

        self.database.execute(
            """
            UPDATE knowledge_documents
            SET
                source_id = ?,
                title = ?,
                content_type = ?,
                external_id = ?,
                metadata = ?,
                content_hash = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                document.source_id,
                document.title,
                document.content_type,
                document.external_id,
                self._encode_metadata(
                    document.metadata
                ),
                document.content_hash,
                document.updated_at,
                document.id,
            ),
        )

        return document

    def delete_document(
        self,
        document_id: int,
    ) -> bool:

        existing = self.database.fetch_one(
            """
            SELECT id
            FROM knowledge_documents
            WHERE id = ?
            """,
            (document_id,),
        )

        if existing is None:
            return False

        self.database.execute(
            """
            DELETE FROM knowledge_documents
            WHERE id = ?
            """,
            (document_id,),
        )

        return True

    # ==================================================
    # Passages
    # ==================================================

    def create_passage(
        self,
        passage: KnowledgePassage,
    ) -> KnowledgePassage:

        with self.database.connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO knowledge_passages (
                    document_id,
                    sequence,
                    content,
                    metadata,
                    content_hash,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    passage.document_id,
                    passage.sequence,
                    passage.content,
                    self._encode_metadata(
                        passage.metadata
                    ),
                    passage.content_hash,
                    passage.created_at,
                    passage.updated_at,
                ),
            )

            passage.id = cursor.lastrowid

        return passage

    def get_passage(
        self,
        passage_id: int,
    ) -> KnowledgePassage | None:

        row = self.database.fetch_one(
            """
            SELECT
                id,
                document_id,
                sequence,
                content,
                metadata,
                content_hash,
                created_at,
                updated_at
            FROM knowledge_passages
            WHERE id = ?
            """,
            (passage_id,),
        )

        if row is None:
            return None

        return KnowledgePassage(
            id=row[0],
            document_id=row[1],
            sequence=row[2],
            content=row[3],
            metadata=self._decode_metadata(
                row[4]
            ),
            content_hash=row[5],
            created_at=row[6],
            updated_at=row[7],
        )

    def list_passages(
        self,
        document_id: int,
    ) -> list[KnowledgePassage]:

        rows = self.database.fetch_all(
            """
            SELECT
                id,
                document_id,
                sequence,
                content,
                metadata,
                content_hash,
                created_at,
                updated_at
            FROM knowledge_passages
            WHERE document_id = ?
            ORDER BY sequence ASC, id ASC
            """,
            (document_id,),
        )

        return [
            KnowledgePassage(
                id=row[0],
                document_id=row[1],
                sequence=row[2],
                content=row[3],
                metadata=self._decode_metadata(
                    row[4]
                ),
                content_hash=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]
    # ==================================================
    # Retrieval
    # ==================================================

    # ==================================================
    # Retrieval
    # ==================================================

    def search_passages(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[KnowledgePassage]:
        """
        Return candidate Knowledge passages for retrieval.

        The repository performs candidate lookup only.
        Relevance scoring belongs to the retrieval provider.

        Query terms are matched independently so a multi-word
        query does not have to occur as one contiguous phrase.
        """

        if not query.strip():
            raise ValueError(
                "Knowledge search query cannot be empty."
            )

        if limit <= 0:
            raise ValueError(
                "Knowledge search limit must be positive."
            )

        tokens = [
            token.strip()
            for token in query.lower().split()
            if token.strip()
        ]

        if not tokens:
            return []

        conditions = " OR ".join(
            "LOWER(content) LIKE ?"
            for _ in tokens
        )

        parameters = tuple(
            f"%{token}%"
            for token in tokens
        )

        rows = self.database.fetch_all(
            f"""
            SELECT
                id,
                document_id,
                sequence,
                content,
                metadata,
                content_hash,
                created_at,
                updated_at
            FROM knowledge_passages
            WHERE {conditions}
            ORDER BY id ASC
            LIMIT ?
            """,
            (
                *parameters,
                limit,
            ),
        )

        return [
            KnowledgePassage(
                id=row[0],
                document_id=row[1],
                sequence=row[2],
                content=row[3],
                metadata=self._decode_metadata(
                    row[4]
                ),
                content_hash=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    def update_passage(
        self,
        passage: KnowledgePassage,
    ) -> KnowledgePassage:

        if passage.id is None:
            raise ValueError(
                "Cannot update a passage without an id."
            )

        passage.touch()

        self.database.execute(
            """
            UPDATE knowledge_passages
            SET
                document_id = ?,
                sequence = ?,
                content = ?,
                metadata = ?,
                content_hash = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                passage.document_id,
                passage.sequence,
                passage.content,
                self._encode_metadata(
                    passage.metadata
                ),
                passage.content_hash,
                passage.updated_at,
                passage.id,
            ),
        )

        return passage

    def delete_passage(
        self,
        passage_id: int,
    ) -> bool:

        existing = self.database.fetch_one(
            """
            SELECT id
            FROM knowledge_passages
            WHERE id = ?
            """,
            (passage_id,),
        )

        if existing is None:
            return False

        self.database.execute(
            """
            DELETE FROM knowledge_passages
            WHERE id = ?
            """,
            (passage_id,),
        )

        return True

    def delete_passages_for_document(
        self,
        document_id: int,
    ) -> int:

        rows = self.database.fetch_all(
            """
            SELECT id
            FROM knowledge_passages
            WHERE document_id = ?
            """,
            (document_id,),
        )

        if not rows:
            return 0

        self.database.execute(
            """
            DELETE FROM knowledge_passages
            WHERE document_id = ?
            """,
            (document_id,),
        )

        return len(rows)