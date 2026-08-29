"""
Persistent storage for generic Jarvis relationships.
"""

from datetime import datetime, timezone

from jarvis.relationships.models import Relationship
from jarvis.storage.database import Database, database


class RelationshipStore:
    """
    Stores and retrieves generic relationships.

    This class does not know what a relationship points to.

    Args:
        database: Optional database instance. When omitted, the application
            database is used for normal runtime behavior. Tests and isolated
            consumers can inject a dedicated database.
    """

    def __init__(
        self,
        database_instance: Database | None = None,
    ) -> None:
        self.database = database_instance or database

    def initialize(self) -> None:
        """
        Create the relationship table if it does not exist.
        """

        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                source TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target TEXT NOT NULL,

                confidence REAL NOT NULL DEFAULT 0.5,
                confirmations INTEGER NOT NULL DEFAULT 0,
                uses INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_used_at TEXT,

                UNIQUE (
                    source,
                    target_type,
                    target
                )
            )
            """
        )

        self.database.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_relationships_source
            ON relationships(source)
            """
        )

        self.database.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_relationships_target_type
            ON relationships(target_type)
            """
        )

    # ======================================================
    # CREATE / UPDATE
    # ======================================================

    def save(
        self,
        relationship: Relationship,
    ) -> Relationship:
        """
        Insert or update a relationship.
        """

        self.initialize()

        existing = self.find_exact(
            source=relationship.source,
            target_type=relationship.target_type,
            target=relationship.target,
        )

        if existing is None:

            self.database.execute(
                """
                INSERT INTO relationships (
                    source,
                    target_type,
                    target,
                    confidence,
                    confirmations,
                    uses,
                    created_at,
                    updated_at,
                    last_used_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship.source,
                    relationship.target_type,
                    relationship.target,
                    relationship.confidence,
                    relationship.confirmations,
                    relationship.uses,
                    relationship.created_at,
                    relationship.updated_at,
                    relationship.last_used_at,
                ),
            )

            saved = self.find_exact(
                source=relationship.source,
                target_type=relationship.target_type,
                target=relationship.target,
            )

            if saved is None:
                raise RuntimeError(
                    "Relationship was inserted but could not be retrieved."
                )

            return saved

        # Update existing record.
        self.database.execute(
            """
            UPDATE relationships
            SET
                confidence = ?,
                confirmations = ?,
                uses = ?,
                updated_at = ?,
                last_used_at = ?
            WHERE id = ?
            """,
            (
                relationship.confidence,
                relationship.confirmations,
                relationship.uses,
                relationship.updated_at,
                relationship.last_used_at,
                existing.id,
            ),
        )

        relationship.id = existing.id

        return relationship

    # ======================================================
    # LOOKUP
    # ======================================================

    def find_exact(
        self,
        source: str,
        target_type: str,
        target: str,
    ) -> Relationship | None:
        """
        Find one exact relationship.
        """

        self.initialize()

        row = self.database.fetch_one(
            """
            SELECT
                id,
                source,
                target_type,
                target,
                confidence,
                confirmations,
                uses,
                created_at,
                updated_at,
                last_used_at
            FROM relationships
            WHERE source = ?
              AND target_type = ?
              AND target = ?
            LIMIT 1
            """,
            (
                source,
                target_type,
                target,
            ),
        )

        if row is None:
            return None

        return self._from_row(row)

    def find_by_source(
        self,
        source: str,
        target_type: str | None = None,
    ) -> list[Relationship]:
        """
        Find all relationships associated with a source phrase.
        """

        self.initialize()

        if target_type is None:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source,
                    target_type,
                    target,
                    confidence,
                    confirmations,
                    uses,
                    created_at,
                    updated_at,
                    last_used_at
                FROM relationships
                WHERE source = ?
                ORDER BY confidence DESC, uses DESC
                """,
                (source,),
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source,
                    target_type,
                    target,
                    confidence,
                    confirmations,
                    uses,
                    created_at,
                    updated_at,
                    last_used_at
                FROM relationships
                WHERE source = ?
                  AND target_type = ?
                ORDER BY confidence DESC, uses DESC
                """,
                (
                    source,
                    target_type,
                ),
            )

        return [
            self._from_row(row)
            for row in rows
        ]

    def all(
        self,
        target_type: str | None = None,
    ) -> list[Relationship]:
        """
        Return all stored relationships.
        """

        self.initialize()

        if target_type is None:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source,
                    target_type,
                    target,
                    confidence,
                    confirmations,
                    uses,
                    created_at,
                    updated_at,
                    last_used_at
                FROM relationships
                ORDER BY source, confidence DESC
                """
            )

        else:

            rows = self.database.fetch_all(
                """
                SELECT
                    id,
                    source,
                    target_type,
                    target,
                    confidence,
                    confirmations,
                    uses,
                    created_at,
                    updated_at,
                    last_used_at
                FROM relationships
                WHERE target_type = ?
                ORDER BY source, confidence DESC
                """,
                (target_type,),
            )

        return [
            self._from_row(row)
            for row in rows
        ]

    # ======================================================
    # USAGE
    # ======================================================

    def record_use(
        self,
        relationship_id: int,
    ) -> None:
        """
        Record successful use of a relationship.
        """

        now = datetime.now(
            timezone.utc
        ).isoformat()

        self.database.execute(
            """
            UPDATE relationships
            SET
                uses = uses + 1,
                last_used_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                now,
                relationship_id,
            ),
        )

    # ======================================================
    # DELETE
    # ======================================================

    def delete(
        self,
        relationship_id: int,
    ) -> None:
        """
        Delete a relationship.
        """

        self.database.execute(
            """
            DELETE FROM relationships
            WHERE id = ?
            """,
            (relationship_id,),
        )

    # ======================================================
    # INTERNAL
    # ======================================================

    @staticmethod
    def _from_row(
        row,
    ) -> Relationship:
        return Relationship(
            id=row[0],
            source=row[1],
            target_type=row[2],
            target=row[3],
            confidence=row[4],
            confirmations=row[5],
            uses=row[6],
            created_at=row[7],
            updated_at=row[8],
            last_used_at=row[9],
        )