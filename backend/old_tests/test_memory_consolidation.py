from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory.formation import (
    MemoryCandidate,
    MemoryFormationService,
    MemorySource,
    RetentionReason,
    ConsolidationAction,
)

from jarvis.memory.long_term import (
    LongTermMemoryService,
)

from jarvis.storage.database import (
    Database,
)

from jarvis.storage.repositories.long_term_memory import (
    LongTermMemoryRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "memory_consolidation_test.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        repository = (
            LongTermMemoryRepository(
                database
            )
        )

        memory_service = (
            LongTermMemoryService(
                repository,
                agent_id="test-jarvis",
            )
        )

        formation = (
            MemoryFormationService(
                memory_service
            )
        )

        # ==================================================
        # Create two related memories directly.
        #
        # Normally Formation would prevent this, but
        # consolidation must also be able to repair
        # pre-existing or imported duplicates.
        # ==================================================

        first = memory_service.create(
            content=(
                "Sidhanth uses Cursor "
                "for Jarvis development."
            ),
            category="preference",
            subject="editor",
            project="Jarvis",
            importance=0.70,
            confidence=0.80,
        )

        second = memory_service.create(
            content=(
                "Sidhanth uses Cursor "
                "as the primary editor "
                "for Jarvis."
            ),
            category="preference",
            subject="editor",
            project="Jarvis",
            importance=0.95,
            confidence=0.98,
        )

        assert first.id is not None
        assert second.id is not None

        assert len(
            memory_service.list()
        ) == 2

        print(
            "PASS: Duplicate active memories "
            "can be represented for consolidation."
        )

        # ==================================================
        # Inspect consolidation plan.
        # ==================================================

        decisions = (
            formation.consolidation_candidates()
        )

        assert len(decisions) == 1

        decision = decisions[0]

        assert (
            decision.action
            == ConsolidationAction.SUPERSEDE
        )

        assert (
            len(decision.memories)
            == 2
        )

        assert (
            decision.replacement_content
            == second.content
        )

        print(
            "PASS: Consolidator identifies "
            "related memories."
        )

        # ==================================================
        # Apply consolidation.
        # ==================================================

        applied = (
            formation.consolidate()
        )

        assert len(applied) == 1

        active = (
            memory_service.list()
        )

        assert len(active) == 1

        replacement = active[0]

        assert (
            replacement.content
            == second.content
        )

        assert (
            replacement.status
            == "active"
        )

        # ==================================================
        # Historical records remain.
        # ==================================================

        history = (
            memory_service.list(
                include_superseded=True
            )
        )

        assert len(history) == 3

        superseded = [
            memory
            for memory in history
            if memory.status
            == "superseded"
        ]

        assert len(superseded) == 2

        for memory in superseded:

            assert (
                memory.superseded_by_id
                == replacement.id
            )

        print(
            "PASS: Consolidation preserves "
            "historical memories."
        )

        # ==================================================
        # Persistence after reload.
        # ==================================================

        database_again = Database(
            database_path
        )

        database_again.initialize()

        repository_again = (
            LongTermMemoryRepository(
                database_again
            )
        )

        memory_again = (
            LongTermMemoryService(
                repository_again,
                agent_id="test-jarvis",
            )
        )

        restored_active = (
            memory_again.list()
        )

        assert len(
            restored_active
        ) == 1

        restored_history = (
            memory_again.list(
                include_superseded=True
            )
        )

        assert len(
            restored_history
        ) == 3

        print(
            "PASS: Consolidation persists "
            "across reload."
        )

        print()
        print(
            "CONSOLIDATED MEMORY:"
        )

        for memory in restored_history:

            print(
                f"[{memory.status}] "
                f"{memory.content}"
            )

        print()
        print(
            "PASS: Memory consolidation works."
        )


if __name__ == "__main__":
    main()