"""
Long-Term Memory consolidation.

Consolidation identifies overlapping active memories and
produces a safe replacement plan.

It does not modify persistence directly.

The actual persistence operation is delegated to
LongTermMemoryService so the repository boundary remains
intact.
"""

from collections import defaultdict

from jarvis.memory.models import (
    LongTermMemory,
)

from jarvis.memory.formation.models import (
    ConsolidationAction,
    ConsolidationDecision,
)


class MemoryConsolidator:
    """
    Detect and consolidate related active memories.
    """

    def find_candidates(
        self,
        memories: list[LongTermMemory],
    ) -> list[
        ConsolidationDecision
    ]:
        """
        Find groups of memories that can be consolidated.

        Only active memories are considered.
        """

        active = [
            memory
            for memory in memories
            if memory.status == "active"
        ]

        groups: dict[
            tuple[str | None, str | None, str | None],
            list[LongTermMemory],
        ] = defaultdict(list)

        for memory in active:

            identity = (
                memory.category,
                memory.subject,
                memory.project,
            )

            # Without semantic identity, we cannot safely
            # consolidate automatically.
            if not any(identity):
                continue

            groups[identity].append(
                memory
            )

        decisions: list[
            ConsolidationDecision
        ] = []

        for group in groups.values():

            if len(group) < 2:
                continue

            ordered = sorted(
                group,
                key=lambda memory: (
                    memory.importance,
                    memory.confidence,
                    memory.updated_at or "",
                    memory.id or 0,
                ),
                reverse=True,
            )

            primary = ordered[0]

            # If all contents are identical, retain the
            # strongest representation and consolidate the
            # duplicate records into one replacement.
            normalized = {
                self._normalize(
                    memory.content
                )
                for memory in group
            }

            if len(normalized) == 1:

                decisions.append(
                    ConsolidationDecision(
                        action=(
                            ConsolidationAction.MERGE
                        ),
                        memories=tuple(group),
                        reason=(
                            "Active memories share the "
                            "same identity and contain "
                            "duplicate information."
                        ),
                        replacement_content=(
                            primary.content
                        ),
                        category=primary.category,
                        subject=primary.subject,
                        project=primary.project,
                        importance=max(
                            memory.importance
                            for memory in group
                        ),
                        confidence=max(
                            memory.confidence
                            for memory in group
                        ),
                    )
                )

                continue

            # Different content under the same semantic
            # identity means the records represent evolving
            # knowledge. We do not guess a merged sentence.
            #
            # Instead, surface the group as a supersession
            # candidate using the strongest/latest memory.
            decisions.append(
                ConsolidationDecision(
                    action=(
                        ConsolidationAction.SUPERSEDE
                    ),
                    memories=tuple(group),
                    reason=(
                        "Multiple active memories share "
                        "the same semantic identity but "
                        "contain different information. "
                        "The strongest current memory "
                        "should become the active "
                        "representation."
                    ),
                    replacement_content=(
                        primary.content
                    ),
                    category=primary.category,
                    subject=primary.subject,
                    project=primary.project,
                    importance=primary.importance,
                    confidence=primary.confidence,
                )
            )

        return decisions

    @staticmethod
    def _normalize(
        content: str,
    ) -> str:

        return " ".join(
            content.lower().split()
        )