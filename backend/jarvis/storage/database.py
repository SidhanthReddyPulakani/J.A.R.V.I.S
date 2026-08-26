"""
Jarvis SQLite database connection manager.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from jarvis.core.config import DATA_DIR
from jarvis.storage.migrations import migrate


DATABASE_PATH = DATA_DIR / "jarvis.db"


class Database:
    """
    Manages the Jarvis SQLite database.

    Responsibilities:
    - Create the database directory.
    - Open SQLite connections.
    - Enable foreign keys.
    - Apply migrations.
    - Provide transaction-safe access.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATABASE_PATH

    def initialize(self) -> None:
        """
        Create the database if necessary and apply migrations.
        """

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = self._connect()

        try:
            migrate(connection)
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        """
        Create a configured SQLite connection.
        """

        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """
        Provide a database connection.

        The transaction is committed if the block succeeds.
        It is rolled back if an exception occurs.
        """

        connection = self._connect()

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> None:
        """
        Execute a single SQL statement.
        """

        with self.connection() as connection:
            connection.execute(
                sql,
                parameters,
            )

    def fetch_one(
        self,
        sql: str,
        parameters: tuple = (),
    ):
        """
        Execute a query and return one row.
        """

        with self.connection() as connection:
            cursor = connection.execute(
                sql,
                parameters,
            )

            return cursor.fetchone()

    def fetch_all(
        self,
        sql: str,
        parameters: tuple = (),
    ):
        """
        Execute a query and return all rows.
        """

        with self.connection() as connection:
            cursor = connection.execute(
                sql,
                parameters,
            )

            return cursor.fetchall()


database = Database()