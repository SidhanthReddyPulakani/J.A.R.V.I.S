"""
Jarvis database migrations.

Migrations allow the database schema to evolve without
destroying existing user data.
"""

import sqlite3

from jarvis.storage.schema import SCHEMA_SQL, SCHEMA_VERSION


def get_schema_version(connection: sqlite3.Connection) -> int:
    """
    Return the current database schema version.

    A brand-new database starts at version 0.
    """

    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'schema_version'
        """
    )

    if cursor.fetchone() is None:
        return 0

    cursor = connection.execute(
        """
        SELECT version
        FROM schema_version
        ORDER BY version DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    if row is None:
        return 0

    return int(row[0])


def initialize_schema(connection: sqlite3.Connection) -> None:
    """
    Create the initial database schema.
    """

    current_version = get_schema_version(connection)

    if current_version >= SCHEMA_VERSION:
        return

    if current_version == 0:
        connection.executescript(SCHEMA_SQL)

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

        from datetime import datetime, timezone

        connection.execute(
            """
            INSERT INTO schema_version (
                version,
                applied_at
            )
            VALUES (?, ?)
            """,
            (
                SCHEMA_VERSION,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        connection.commit()

        return

    raise RuntimeError(
        f"Unsupported database schema version: {current_version}"
    )


def migrate(connection: sqlite3.Connection) -> None:
    """
    Apply all required database migrations.
    """

    initialize_schema(connection)