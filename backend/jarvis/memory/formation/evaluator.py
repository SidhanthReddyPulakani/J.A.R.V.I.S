"""
Deterministic Memory Formation evaluator.

This component decides whether a MemoryCandidate should be:

    DISCARD
    CREATE
    UPDATE

It does not persist anything.

The evaluator is intentionally deterministic for the first
implementation. An LLM-assisted evaluator can be introduced
later without changing the FormationDecision contract.
"""

from jarvis.memory.formation.models import (
    FormationAction,
    FormationDecision,
    MemoryCandidate,
    RetentionReason,
)
from jarvis.memory.models import LongTermMemory


class MemoryEvaluator:
    """
    Evaluates memory candidates against existing memories.
    """

    MIN_CONFIDENCE = 0.50

    MIN_IMPORTANCE = 0.20

    def evaluate(
        self,
        candidate: MemoryCandidate,
        existing_memories: list[
            LongTermMemory
        ] | None = None,
    ) -> FormationDecision:
        """
        Evaluate a candidate.

        Rules, in order:

        1. Explicitly requested memories are retained.
        2. Very low-confidence candidates are discarded.
        3. Very low-importance candidates are discarded.
        4. Exact duplicates are discarded.
        5. A matching active memory with different content
           becomes an UPDATE decision.
        6. Otherwise CREATE.
        """

        memories = (
            existing_memories
            if existing_memories is not None
            else []
        )

        # --------------------------------------------------
        # Explicit retention
        # --------------------------------------------------

        explicit = (
            candidate.reason
            == RetentionReason.EXPLICIT_REQUEST
        )

        # --------------------------------------------------
        # Confidence
        # --------------------------------------------------

        if (
            not explicit
            and candidate.confidence
            < self.MIN_CONFIDENCE
        ):

            return FormationDecision(
                action=FormationAction.DISCARD,
                candidate=candidate,
                reason=(
                    "Candidate confidence is below "
                    f"the minimum threshold of "
                    f"{self.MIN_CONFIDENCE:.2f}."
                ),
            )

        # --------------------------------------------------
        # Importance
        # --------------------------------------------------

        if (
            not explicit
            and candidate.importance
            < self.MIN_IMPORTANCE
        ):

            return FormationDecision(
                action=FormationAction.DISCARD,
                candidate=candidate,
                reason=(
                    "Candidate importance is below "
                    f"the minimum threshold of "
                    f"{self.MIN_IMPORTANCE:.2f}."
                ),
            )

        # --------------------------------------------------
        # Existing memory analysis
        # --------------------------------------------------

        normalized_candidate = (
            self._normalize(
                candidate.content
            )
        )

        for memory in memories:

            if memory.status != "active":
                continue

            normalized_existing = (
                self._normalize(
                    memory.content
                )
            )

            # Exact duplicate.
            if (
                normalized_candidate
                == normalized_existing
            ):

                return FormationDecision(
                    action=FormationAction.DISCARD,
                    candidate=candidate,
                    reason=(
                        "An identical active "
                        "memory already exists."
                    ),
                )

        # --------------------------------------------------
        # Matching memory
        # --------------------------------------------------

        matching_memory = (
            self._find_matching_memory(
                candidate,
                memories,
            )
        )

        if matching_memory is not None:

            return FormationDecision(
                action=FormationAction.UPDATE,
                candidate=candidate,
                existing_memory=matching_memory,
                reason=(
                    "An active memory with the "
                    "same semantic identity exists; "
                    "the candidate should replace it."
                ),
            )

        # --------------------------------------------------
        # New memory
        # --------------------------------------------------

        return FormationDecision(
            action=FormationAction.CREATE,
            candidate=candidate,
            reason=(
                "No matching active memory exists."
            ),
        )

    @classmethod
    def _find_matching_memory(
        cls,
        candidate: MemoryCandidate,
        memories: list[
            LongTermMemory
        ],
    ) -> LongTermMemory | None:
        """
        Find an existing memory representing the same
        semantic identity.

        Identity is currently based on:

            category
            subject
            project

        Only fields explicitly supplied by the candidate
        participate in matching.

        This is deliberately conservative and deterministic.
        """

        for memory in memories:

            if memory.status != "active":
                continue

            if (
                candidate.category is not None
                and memory.category
                != candidate.category
            ):
                continue

            if (
                candidate.subject is not None
                and memory.subject
                != candidate.subject
            ):
                continue

            if (
                candidate.project is not None
                and memory.project
                != candidate.project
            ):
                continue

            # At least one semantic identity field must exist.
            if not any(
                value is not None
                for value in (
                    candidate.category,
                    candidate.subject,
                    candidate.project,
                )
            ):
                continue

            return memory

        return None

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:
        """
        Normalize text for duplicate comparison.
        """

        return " ".join(
            value.lower().split()
        )