"""
Application name resolution.

This module resolves user-provided application names against
the applications discovered by ApplicationDiscovery.

The resolver does NOT contain a hard-coded application list.
"""

from dataclasses import dataclass
import re
from difflib import SequenceMatcher

from jarvis.features.apps.models import Application


@dataclass(frozen=True)
class ResolutionResult:
    """
    Result of attempting to resolve an application query.
    """

    query: str
    application: Application | None
    candidates: list[Application]
    confidence: float
    reason: str

    @property
    def resolved(self) -> bool:
        return self.application is not None

    @property
    def ambiguous(self) -> bool:
        return (
            self.application is None
            and len(self.candidates) > 1
        )


class ApplicationResolver:
    """
    Resolves application names using discovered applications.

    Matching order:

    1. Exact normalized match
    2. Token-aware match
    3. Fuzzy similarity
    4. Candidate scoring

    No application names are hard-coded here.
    """

    # Minimum score required for an automatic resolution.
    RESOLUTION_THRESHOLD = 0.72

    # Difference required between first and second candidate
    # before we consider the result confidently resolvable.
    MIN_SCORE_MARGIN = 0.12

    def resolve(
        self,
        query: str,
        applications: list[Application],
    ) -> Application | None:
        """
        Resolve an application query.

        Returns an application only when the resolver is
        sufficiently confident.

        Returns None when:
        - nothing matches
        - the result is too weak
        - multiple candidates are too close
        """

        result = self.resolve_detailed(
            query,
            applications,
        )

        return result.application

    def resolve_detailed(
        self,
        query: str,
        applications: list[Application],
    ) -> ResolutionResult:
        """
        Resolve an application query while preserving
        information about candidate matches.
        """

        normalized_query = self._normalize(query)

        if not normalized_query:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=[],
                confidence=0.0,
                reason="empty_query",
            )

        if not applications:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=[],
                confidence=0.0,
                reason="no_applications",
            )

        # --------------------------------------------------
        # 1. Exact match
        # --------------------------------------------------

        exact_matches = [
            application
            for application in applications
            if self._normalize(application.name)
            == normalized_query
        ]

        if len(exact_matches) == 1:
            return ResolutionResult(
                query=query,
                application=exact_matches[0],
                candidates=exact_matches,
                confidence=1.0,
                reason="exact_match",
            )

        if len(exact_matches) > 1:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=exact_matches,
                confidence=1.0,
                reason="ambiguous_exact_match",
            )

        # --------------------------------------------------
        # 2. Score all candidates
        # --------------------------------------------------

        scored = []

        for application in applications:
            score = self._score(
                normalized_query,
                application,
            )

            if score <= 0:
                continue

            scored.append(
                (
                    score,
                    application,
                )
            )

        if not scored:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=[],
                confidence=0.0,
                reason="no_match",
            )

        # Highest score first.
        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_score, best_application = scored[0]

        candidates = [
            application
            for _, application in scored[:5]
        ]

        # --------------------------------------------------
        # 3. Weak match
        # --------------------------------------------------

        if best_score < self.RESOLUTION_THRESHOLD:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=candidates,
                confidence=best_score,
                reason="weak_match",
            )

        # --------------------------------------------------
        # 4. Ambiguous match
        # --------------------------------------------------

        if len(scored) > 1:
            second_score = scored[1][0]

            if (
                best_score - second_score
                < self.MIN_SCORE_MARGIN
            ):
                return ResolutionResult(
                    query=query,
                    application=None,
                    candidates=candidates,
                    confidence=best_score,
                    reason="ambiguous_match",
                )

        # --------------------------------------------------
        # 5. Strong match
        # --------------------------------------------------

        return ResolutionResult(
            query=query,
            application=best_application,
            candidates=candidates,
            confidence=best_score,
            reason="scored_match",
        )

    # ======================================================
    # Scoring
    # ======================================================

    def _score(
        self,
        query: str,
        application: Application,
    ) -> float:
        """
        Calculate how well an application matches a query.
        """

        name = self._normalize(
            application.name
        )

        if not name:
            return 0.0

        # Exact should normally be handled earlier.
        if name == query:
            return 1.0

        query_tokens = set(
            query.split()
        )

        name_tokens = set(
            name.split()
        )

        # --------------------------------------------------
        # Token overlap
        # --------------------------------------------------

        if query_tokens:
            overlap = (
                len(query_tokens & name_tokens)
                / len(query_tokens)
            )
        else:
            overlap = 0.0

        # --------------------------------------------------
        # Prefix
        # --------------------------------------------------

        prefix_score = 0.0

        if name.startswith(query):
            prefix_score = 0.92
        elif query.startswith(name):
            prefix_score = 0.85

        # --------------------------------------------------
        # Substring
        # --------------------------------------------------

        substring_score = 0.0

        if query in name:
            substring_score = 0.82
        elif name in query:
            substring_score = 0.76

        # --------------------------------------------------
        # Fuzzy similarity
        # --------------------------------------------------

        fuzzy_score = SequenceMatcher(
            None,
            query,
            name,
        ).ratio()

        # --------------------------------------------------
        # Combined score
        # --------------------------------------------------

        return max(
            prefix_score,
            substring_score,
            fuzzy_score * 0.85,
            overlap * 0.80,
        )

    # ======================================================
    # Normalization
    # ======================================================

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """
        Normalize text for comparison.

        Examples:

            "Visual Studio Code"
            "visual-studio code"
            "  VISUAL   STUDIO CODE "

        all become approximately:

            "visual studio code"
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