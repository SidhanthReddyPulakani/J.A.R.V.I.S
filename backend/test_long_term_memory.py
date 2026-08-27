from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory import (
    LongTermMemory,
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
            / "long_term_memory_test.db"
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

        memory = LongTermMemoryService(
            repository,
            agent_id="test-jarvis",
        )

        # --------------------------------------------------
        # Create
        # --------------------------------------------------

        created = memory.create(
            content=(
                "The user's primary editor "
                "for Jarvis is Cursor."
            ),
            category="preference",
            subject="editor",
            project="Jarvis",
            importance=0.9,
            confidence=1.0,
        )

        assert isinstance(
            created,
            LongTermMemory,
        )

        assert created.id is not None

        assert (
            created.agent_id
            == "test-jarvis"
        )

        assert (
            created.status
            == "active"
        )

        assert (
            created.importance
            == 0.9
        )

        # --------------------------------------------------
        # Read
        # --------------------------------------------------

        restored = memory.get(
            created.id
        )

        assert restored is not None

        assert (
            restored.content
            == (
                "The user's primary editor "
                "for Jarvis is Cursor."
            )
        )

        assert (
            restored.subject
            == "editor"
        )

        assert (
            restored.project
            == "Jarvis"
        )

        # --------------------------------------------------
        # Update
        # --------------------------------------------------

        restored.content = (
            "The user's primary editor "
            "for Jarvis development is Cursor."
        )

        restored.confidence = 0.95

        updated = memory.update(
            restored
        )

        assert (
            updated.confidence
            == 0.95
        )

        reread = memory.get(
            created.id
        )

        assert reread is not None

        assert (
            "Jarvis development"
            in reread.content
        )

        assert (
            reread.confidence
            == 0.95
        )

        # --------------------------------------------------
        # Create another memory
        # --------------------------------------------------

        second = memory.create(
            content=(
                "The Jarvis project uses "
                "SQLite for persistence."
            ),
            category="project",
            subject="database",
            project="Jarvis",
            importance=0.8,
            confidence=1.0,
        )

        assert second.id is not None

        # --------------------------------------------------
        # Agent isolation
        # --------------------------------------------------

        other_memory = LongTermMemoryService(
            repository,
            agent_id="other-agent",
        )

        assert (
            other_memory.get(
                created.id
            )
            is None
        )

        assert (
            len(
                other_memory.list()
            )
            == 0
        )

        # --------------------------------------------------
        # Supersede
        # --------------------------------------------------

        replacement = memory.supersede(
            created.id,
            (
                "The user's primary editor "
                "for Jarvis development is "
                "now Cursor."
            ),
            category="preference",
            subject="editor",
            project="Jarvis",
            importance=0.95,
            confidence=1.0,
        )

        assert (
            replacement.id is not None
        )

        assert (
            replacement.id
            != created.id
        )

        assert (
            replacement.status
            == "active"
        )

        # Old memory should now be superseded.

        old = memory.get(
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

        # Default listing excludes superseded memory.

        active = memory.list()

        active_ids = {
            item.id
            for item in active
        }

        assert (
            created.id
            not in active_ids
        )

        assert (
            replacement.id
            in active_ids
        )

        assert (
            second.id
            in active_ids
        )

        # Full listing includes history.

        all_memories = memory.list(
            include_superseded=True
        )

        all_ids = {
            item.id
            for item in all_memories
        }

        assert (
            created.id
            in all_ids
        )

        assert (
            replacement.id
            in all_ids
        )

        # --------------------------------------------------
        # Persistence across reload
        # --------------------------------------------------

        database_again = Database(
            database_path
        )

        database_again.initialize()

        repository_again = (
            LongTermMemoryRepository(
                database_again
            )
        )

        memory_again = LongTermMemoryService(
            repository_again,
            agent_id="test-jarvis",
        )

        persisted_replacement = (
            memory_again.get(
                replacement.id
            )
        )

        assert (
            persisted_replacement
            is not None
        )

        assert (
            persisted_replacement.content
            == (
                "The user's primary editor "
                "for Jarvis development is "
                "now Cursor."
            )
        )

        persisted_old = (
            memory_again.get(
                created.id
            )
        )

        assert (
            persisted_old
            is not None
        )

        assert (
            persisted_old.status
            == "superseded"
        )

        assert (
            persisted_old.superseded_by_id
            == replacement.id
        )

        # --------------------------------------------------
        # Delete active memory
        # --------------------------------------------------

        memory_again.delete(
            second.id
        )

        assert (
            memory_again.get(
                second.id
            )
            is None
        )

        print(
            "LONG-TERM MEMORY:"
        )

        print()

        for item in (
            memory_again.list(
                include_superseded=True
            )
        ):

            print(
                f"[{item.status}] "
                f"{item.content}"
            )

        print()

        print(
            "PASS: Long-Term Memory CRUD works."
        )

        print(
            "PASS: Long-Term Memory is "
            "agent-scoped."
        )

        print(
            "PASS: Memory superseding works."
        )

        print(
            "PASS: Long-Term Memory persists "
            "across reload."
        )


if __name__ == "__main__":
    main()