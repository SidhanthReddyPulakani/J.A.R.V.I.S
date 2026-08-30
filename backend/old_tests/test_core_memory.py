from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory import (
    CoreMemoryService,
    MemoryBlock,
)
from jarvis.storage.database import Database
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "core_memory_test.db"
        )

        db = Database(
            database_path
        )

        db.initialize()

        # Create Agent State first because
        # Core Memory belongs to an agent.
        db.execute(
            """
            INSERT INTO agent_state (
                agent_id,
                mode,
                operation_status,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "test-jarvis",
                "testing",
                "idle",
                "2026-08-27T00:00:00+00:00",
            ),
        )

        repository = CoreMemoryRepository(
            db
        )

        memory = CoreMemoryService(
            repository,
            agent_id="test-jarvis",
        )

        # --------------------------------------------------
        # Create
        # --------------------------------------------------

        block = memory.create_block(
            label="human",
            content="Name: Sidhanth",
            capacity=200,
        )

        assert isinstance(
            block,
            MemoryBlock,
        )

        assert block.id is not None
        assert block.label == "human"
        assert block.content == "Name: Sidhanth"
        assert block.capacity == 200

        # --------------------------------------------------
        # Read
        # --------------------------------------------------

        restored = memory.get(
            "human"
        )

        assert restored is not None

        assert (
            restored.content
            == "Name: Sidhanth"
        )

        # --------------------------------------------------
        # Replace
        # --------------------------------------------------

        memory.replace(
            "human",
            "Name: Sidhanth\nEditor: Cursor",
        )

        replaced = memory.get(
            "human"
        )

        assert replaced is not None

        assert (
            "Editor: Cursor"
            in replaced.content
        )

        # --------------------------------------------------
        # Append
        # --------------------------------------------------

        memory.append(
            "human",
            "\nOS: Windows",
        )

        appended = memory.get(
            "human"
        )

        assert appended is not None

        assert (
            "OS: Windows"
            in appended.content
        )

        # --------------------------------------------------
        # Capacity enforcement
        # --------------------------------------------------

        try:

            memory.append(
                "human",
                "X" * 1000,
            )

        except ValueError:
            pass

        else:
            raise AssertionError(
                "Capacity limit was not enforced."
            )

        # --------------------------------------------------
        # Persistence
        # --------------------------------------------------

        db_again = Database(
            database_path
        )

        db_again.initialize()

        repository_again = (
            CoreMemoryRepository(
                db_again
            )
        )

        memory_again = (
            CoreMemoryService(
                repository_again,
                agent_id="test-jarvis",
            )
        )

        persisted = memory_again.get(
            "human"
        )

        assert persisted is not None

        assert (
            "Editor: Cursor"
            in persisted.content
        )

        assert (
            "OS: Windows"
            in persisted.content
        )

        print(
            "CORE MEMORY:"
        )

        print(
            f"[{persisted.label}]"
        )

        print(
            persisted.content
        )

        print()

        print(
            "PASS: Core Memory persistence "
            "and editing work."
        )


if __name__ == "__main__":
    main()