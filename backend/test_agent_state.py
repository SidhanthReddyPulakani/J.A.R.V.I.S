"""
Manual persistence test for Agent State.

Run from backend/:

    python test_agent_state.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.state.models import AgentState
from jarvis.storage.database import Database
from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "test_jarvis.db"
        )

        db = Database(
            database_path
        )

        # First process/session.
        db.initialize()

        repository = AgentStateRepository(
            db
        )

        state = AgentState(
            agent_id="test-jarvis",
            current_task="Test persistence",
            current_goal="Verify state survives reload",
            mode="testing",
            active_project="Jarvis",
        )

        repository.save(state)

        print("SAVED:")
        print(state.to_dict())

        # Simulate a completely fresh repository
        # using the same database file.
        db_again = Database(
            database_path
        )

        db_again.initialize()

        repository_again = AgentStateRepository(
            db_again
        )

        loaded = repository_again.get(
            "test-jarvis"
        )

        print()
        print("LOADED:")

        if loaded is None:
            print("FAIL: state was not found")
            raise SystemExit(1)

        print(loaded.to_dict())

        assert loaded.agent_id == "test-jarvis"
        assert (
            loaded.current_task
            == "Test persistence"
        )
        assert (
            loaded.current_goal
            == "Verify state survives reload"
        )
        assert loaded.mode == "testing"
        assert (
            loaded.active_project
            == "Jarvis"
        )

        print()
        print("PASS: Agent State persisted successfully.")


if __name__ == "__main__":
    main()