from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory import (
    FormationAction,
    MemoryCandidate,
    MemoryFormationService,
    MemorySource,
    RetentionReason,
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
            / "memory_formation_test.db"
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
        # CREATE
        # ==================================================

        candidate = MemoryCandidate(
            content=(
                "The user's primary editor "
                "is Cursor."
            ),
            source=MemorySource.USER,
            reason=RetentionReason.PREFERENCE,
            confidence=0.95,
            importance=0.90,
            category="preference",
            subject="editor",
            project="Jarvis",
        )

        decision = formation.form(
            candidate
        )

        assert (
            decision.action
            == FormationAction.CREATE
        )

        active = memory_service.list()

        assert len(active) == 1

        created = active[0]

        assert (
            created.content
            == (
                "The user's primary editor "
                "is Cursor."
            )
        )

        assert (
            created.status
            == "active"
        )

        print(
            "PASS: New candidate creates "
            "Long-Term Memory."
        )

        # ==================================================
        # DUPLICATE
        # ==================================================

        duplicate = MemoryCandidate(
            content=(
                "The user's primary editor "
                "is Cursor."
            ),
            source=MemorySource.USER,
            reason=RetentionReason.PREFERENCE,
            confidence=0.95,
            importance=0.90,
            category="preference",
            subject="editor",
            project="Jarvis",
        )

        duplicate_decision = (
            formation.form(
                duplicate
            )
        )

        assert (
            duplicate_decision.action
            == FormationAction.DISCARD
        )

        active = memory_service.list()

        assert len(active) == 1

        print(
            "PASS: Duplicate candidate is discarded."
        )

        # ==================================================
        # UPDATE / SUPERSEDE
        # ==================================================

        correction = MemoryCandidate(
            content=(
                "The user's primary editor "
                "for Jarvis development is "
                "now VS Code."
            ),
            source=MemorySource.USER,
            reason=RetentionReason.CORRECTION,
            confidence=1.0,
            importance=0.95,
            category="preference",
            subject="editor",
            project="Jarvis",
        )

        update_decision = (
            formation.form(
                correction
            )
        )

        assert (
            update_decision.action
            == FormationAction.UPDATE
        )

        active = memory_service.list()

        assert len(active) == 1

        replacement = active[0]

        assert (
            replacement.content
            == (
                "The user's primary editor "
                "for Jarvis development is "
                "now VS Code."
            )
        )

        assert (
            replacement.status
            == "active"
        )

        assert (
            replacement.id
            != created.id
        )

        old = memory_service.get(
            created.id
        )

        assert old is not None

        assert (
            old.status
            == "superseded"
        )

        assert (
            old.superseded_by_id
            == replacement.id
        )

        print(
            "PASS: Conflicting candidate "
            "supersedes existing memory."
        )

        # ==================================================
        # LOW CONFIDENCE
        # ==================================================

        uncertain = MemoryCandidate(
            content=(
                "The user might possibly "
                "prefer Vim."
            ),
            source=MemorySource.CONVERSATION,
            reason=RetentionReason.OTHER,
            confidence=0.20,
            importance=0.80,
            category="preference",
            subject="editor",
            project="Jarvis",
        )

        uncertain_decision = (
            formation.form(
                uncertain
            )
        )

        assert (
            uncertain_decision.action
            == FormationAction.DISCARD
        )

        assert (
            len(
                memory_service.list()
            )
            == 1
        )

        print(
            "PASS: Low-confidence candidate "
            "is discarded."
        )

        # ==================================================
        # LOW IMPORTANCE
        # ==================================================

        trivial = MemoryCandidate(
            content=(
                "The user mentioned "
                "a temporary detail."
            ),
            source=MemorySource.CONVERSATION,
            reason=RetentionReason.OTHER,
            confidence=0.90,
            importance=0.10,
            category="temporary",
            subject="detail",
        )

        trivial_decision = (
            formation.form(
                trivial
            )
        )

        assert (
            trivial_decision.action
            == FormationAction.DISCARD
        )

        assert (
            len(
                memory_service.list()
            )
            == 1
        )

        print(
            "PASS: Low-importance candidate "
            "is discarded."
        )

        # ==================================================
        # EXPLICIT REQUEST
        # ==================================================

        explicit = MemoryCandidate(
            content=(
                "The user explicitly requested "
                "that Jarvis remember their "
                "preferred terminal."
            ),
            source=MemorySource.USER,
            reason=(
                RetentionReason.EXPLICIT_REQUEST
            ),
            confidence=0.45,
            importance=0.10,
            category="preference",
            subject="terminal",
            project="Jarvis",
        )

        explicit_decision = (
            formation.form(
                explicit
            )
        )

        assert (
            explicit_decision.action
            == FormationAction.CREATE
        )

        active = memory_service.list()

        assert len(active) == 2

        print(
            "PASS: Explicit retention request "
            "overrides normal thresholds."
        )

        # ==================================================
        # PERSISTENCE
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

        persisted = (
            memory_again.list(
                include_superseded=True
            )
        )

        assert len(persisted) == 3

        active_persisted = (
            memory_again.list()
        )

        assert len(
            active_persisted
        ) == 2

        print(
            "PASS: Formation results persist "
            "across reload."
        )

        # ==================================================
        # SUMMARY
        # ==================================================

        print()
        print(
            "FORMATION RESULTS:"
        )

        for memory in persisted:

            print(
                f"[{memory.status}] "
                f"{memory.content}"
            )

        print()
        print(
            "PASS: Memory Formation lifecycle works."
        )


if __name__ == "__main__":
    main()