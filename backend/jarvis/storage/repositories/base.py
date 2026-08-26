"""
Base repository utilities for Jarvis storage.
"""

from jarvis.storage.database import Database


class BaseRepository:
    """
    Base class for feature-specific repositories.

    Repositories are responsible for translating feature operations
    into database operations.
    """

    def __init__(self, database: Database) -> None:
        self.database = database