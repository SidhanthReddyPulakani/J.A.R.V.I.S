"""
Jarvis database migrations.

Migrations allow the database schema to evolve without
destroying existing user data.
"""

import sqlite3
from datetime import datetime, timezone

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


def record_schema_version(
    connection: sqlite3.Connection,
    version: int,
) -> None:
    """Record a successfully applied schema version."""

    connection.execute(
        """
        INSERT INTO schema_version (
            version,
            applied_at
        )
        VALUES (?, ?)
        """,
        (
            version,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def initialize_schema(connection: sqlite3.Connection) -> None:
    """
    Create the initial database schema.

    This is only used for a brand-new database.
    """

    current_version = get_schema_version(connection)

    if current_version != 0:
        return

    connection.executescript(SCHEMA_SQL)

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )

    record_schema_version(
        connection,
        SCHEMA_VERSION,
    )

    connection.commit()

def migrate_to_v2(connection: sqlite3.Connection) -> None:
    """
    Upgrade an existing v1 database to v2.

    v2 introduces persistent Agent State.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_state (
            agent_id TEXT PRIMARY KEY,

            conversation_id INTEGER,

            current_task TEXT,
            current_goal TEXT,

            mode TEXT NOT NULL DEFAULT 'idle',

            active_project TEXT,

            active_operation TEXT,
            operation_status TEXT NOT NULL DEFAULT 'idle',

            updated_at TEXT NOT NULL,

            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE SET NULL
        )
        """
    )

    record_schema_version(
        connection,
        2,
    )

    connection.commit()

def migrate_to_v3(
    connection: sqlite3.Connection,
) -> None:
    """
    Upgrade an existing v2 database to v3.

    v3 introduces persistent Core Memory blocks.
    """

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS core_memory_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            agent_id TEXT NOT NULL,

            label TEXT NOT NULL,

            content TEXT NOT NULL DEFAULT '',

            capacity INTEGER NOT NULL DEFAULT 2000,

            priority INTEGER NOT NULL DEFAULT 100,

            writable INTEGER NOT NULL DEFAULT 1,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL,

            UNIQUE(agent_id, label),

            FOREIGN KEY (agent_id)
                REFERENCES agent_state(agent_id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_core_memory_agent
        ON core_memory_blocks(agent_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_core_memory_priority
        ON core_memory_blocks(
            agent_id,
            priority
        )
        """
    )

    record_schema_version(
        connection,
        3,
    )

    connection.commit()

def migrate(connection: sqlite3.Connection) -> None:
    """
    Apply all required database migrations.
    """

    current_version = get_schema_version(
        connection
    )

    if current_version == 0:
        initialize_schema(connection)
        return

    if current_version == 1:
        migrate_to_v2(connection)
        current_version = 2

    if current_version == 2:
        migrate_to_v3(connection)
        current_version = 3

    if current_version > SCHEMA_VERSION:
        raise RuntimeError(
            "Database schema version "
            f"{current_version} is newer than the "
            f"supported version {SCHEMA_VERSION}."
        )

    if current_version != SCHEMA_VERSION:
        raise RuntimeError(
            "Database migration incomplete: "
            f"database={current_version}, "
            f"expected={SCHEMA_VERSION}"
        )
    