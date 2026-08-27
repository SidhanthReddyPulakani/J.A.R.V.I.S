"""
Memory Formation service.

Coordinates:

    candidate
        ↓
    evaluation
        ↓
    create / update / discard

and:

    existing memories
        ↓
    consolidation
        ↓
    atomic supersession
"""

from jarvis.memory.formation.consolidation import (
    MemoryConsolidator,
)

from jarvis.memory.formation.evaluator import (
    MemoryEvaluator,
)

from jarvis.memory.formation.models import (
    ConsolidationAction,
    ConsolidationDecision,
    FormationAction,
    FormationDecision,
    MemoryCandidate,
)

from jarvis.memory.long_term import (
    LongTermMemoryService,
)


class MemoryFormationService:
    """
    Agent-facing service for memory formation.
    """

    def __init__(
        self,
        memory_service: LongTermMemoryService,
        evaluator: MemoryEvaluator | None = None,
        consolidator: MemoryConsolidator | None = None,
    ) -> None:

        self.memory_service = (
            memory_service
        )

        self.evaluator = (
            evaluator
            if evaluator is not None
            else MemoryEvaluator()
        )

        self.consolidator = (
            consolidator
            if consolidator is not None
            else MemoryConsolidator()
        )

    # ==================================================
    # Formation
    # ==================================================

    def evaluate(
        self,
        candidate: MemoryCandidate,
    ) -> FormationDecision:
        """
        Evaluate a candidate against the agent's
        current active memories.
        """

        existing = (
            self.memory_service.list()
        )

        return self.evaluator.evaluate(
            candidate,
            existing_memories=existing,
        )

    def form(
        self,
        candidate: MemoryCandidate,
    ) -> FormationDecision:
        """
        Evaluate and persist a candidate.
        """

        decision = self.evaluate(
            candidate
        )

        if (
            decision.action
            == FormationAction.DISCARD
        ):

            return decision

        if (
            decision.action
            == FormationAction.CREATE
        ):

            self.memory_service.create(
                content=candidate.content,
                category=candidate.category,
                subject=candidate.subject,
                project=candidate.project,
                importance=candidate.importance,
                confidence=candidate.confidence,
            )

            return decision

        if (
            decision.action
            == FormationAction.UPDATE
        ):

            existing = (
                decision.existing_memory
            )

            if existing is None:
                raise RuntimeError(
                    "UPDATE decision has no "
                    "existing memory."
                )

            if existing.id is None:
                raise RuntimeError(
                    "UPDATE decision references "
                    "a memory without an ID."
                )

            self.memory_service.supersede(
                memory_id=existing.id,
                content=candidate.content,
                category=candidate.category,
                subject=candidate.subject,
                project=candidate.project,
                importance=candidate.importance,
                confidence=candidate.confidence,
            )

            return decision

        raise RuntimeError(
            f"Unsupported formation action: "
            f"{decision.action}"
        )

    # ==================================================
    # Consolidation
    # ==================================================

    def consolidation_candidates(
        self,
    ) -> list[ConsolidationDecision]:
        """
        Inspect the agent's active memories and return
        safe consolidation decisions.

        No persistence occurs.
        """

        memories = (
            self.memory_service.list()
        )

        return (
            self.consolidator.find_candidates(
                memories
            )
        )

    def consolidate(
        self,
    ) -> list[ConsolidationDecision]:
        """
        Apply all safe consolidation decisions.

        Consolidation creates one replacement memory and
        atomically supersedes the memories represented by
        the decision.

        Historical records remain persisted.
        """

        decisions = (
            self.consolidation_candidates()
        )

        applied: list[
            ConsolidationDecision
        ] = []

        for decision in decisions:

            if (
                decision.action
                not in (
                    ConsolidationAction.MERGE,
                    ConsolidationAction.SUPERSEDE,
                )
            ):
                continue

            memories = list(
                decision.memories
            )

            if len(memories) < 2:
                continue

            if any(
                memory.id is None
                for memory in memories
            ):
                raise RuntimeError(
                    "Cannot consolidate a memory "
                    "without an ID."
                )

            self.memory_service.consolidate(
                memory_ids=[
                    memory.id
                    for memory in memories
                ],
                content=(
                    decision.replacement_content
                    or ""
                ),
                category=decision.category,
                subject=decision.subject,
                project=decision.project,
                importance=decision.importance,
                confidence=decision.confidence,
            )

            applied.append(
                decision
            )

        return applied