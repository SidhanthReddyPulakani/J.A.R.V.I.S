"""
Generic relationship resolution.

This module does not know what targets represent.
"""

import re

from jarvis.relationships.models import Relationship
from jarvis.relationships.store import RelationshipStore


class RelationshipResolver:
    """
    Resolves a source phrase to known relationships.
    """

    def __init__(
        self,
        store: RelationshipStore | None = None,
    ) -> None:

        self.store = (
            store
            or RelationshipStore()
        )

    def resolve(
        self,
        source: str,
        target_type: str | None = None,
    ) -> Relationship | None:
        """
        Return the strongest known relationship.

        Exact normalized source matching is used here.
        Semantic interpretation belongs to higher layers.
        """

        normalized = self._normalize(
            source
        )

        if not normalized:
            return None

        relationships = self.store.all(
            target_type=target_type
        )

        matches = [
            relationship
            for relationship in relationships
            if self._normalize(
                relationship.source
            ) == normalized
        ]

        if not matches:
            return None

        return max(
            matches,
            key=self._ranking_key,
        )

    def candidates(
        self,
        source: str,
        target_type: str | None = None,
    ) -> list[Relationship]:
        """
        Return all relationships matching a source.
        """

        normalized = self._normalize(
            source
        )

        if not normalized:
            return []

        relationships = self.store.all(
            target_type=target_type
        )

        matches = [
            relationship
            for relationship in relationships
            if self._normalize(
                relationship.source
            ) == normalized
        ]

        return sorted(
            matches,
            key=self._ranking_key,
            reverse=True,
        )

    @staticmethod
    def _ranking_key(
        relationship: Relationship,
    ) -> tuple:
        """
        Higher confidence wins.

        Confirmation count and successful usage provide
        secondary ranking signals.
        """

        return (
            relationship.confidence,
            relationship.confirmations,
            relationship.uses,
        )

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """
        Normalize a relationship source.
        """

        value = value.strip().lower()

        value = re.sub(
            r"[^a-z0-9]+",
            " ",
            value,
        )

        return " ".join(
            value.split()
        )