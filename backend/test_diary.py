from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.diary import (
    DiaryEvent,
    DiaryService,
)
from jarvis.storage.database import Database
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)
from jarvis.storage.repositories.diary import (
    DiaryRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "diary_test.db"
        )

        db = Database(
            database_path
        )

        db.initialize()

        # --------------------------------------------------
        # Create agent state
        # --------------------------------------------------

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

        # --------------------------------------------------
        # Create conversation
        # --------------------------------------------------

        conversations = ConversationRepository(
            db
        )

        conversation_id = (
            conversations.create()
        )

        assert conversation_id is not None

        # --------------------------------------------------
        # Create Diary service
        # --------------------------------------------------

        repository = DiaryRepository(
            db
        )

        diary = DiaryService(
            repository,
            agent_id="test-jarvis",
        )

        # --------------------------------------------------
        # Record event 1
        # --------------------------------------------------

        first = diary.record(
            event_type="interaction",
            description=(
                "User discussed the Jarvis "
                "memory architecture."
            ),
            conversation_id=conversation_id,
            source="test",
            metadata={
                "topic": "memory",
                "phase": "R2.3",
            },
        )

        assert isinstance(
            first,
            DiaryEvent,
        )

        assert first.id is not None

        assert (
            first.agent_id
            == "test-jarvis"
        )

        assert (
            first.event_type
            == "interaction"
        )

        assert (
            first.description
            == (
                "User discussed the Jarvis "
                "memory architecture."
            )
        )

        assert (
            first.metadata["topic"]
            == "memory"
        )

        # --------------------------------------------------
        # Record event 2
        # --------------------------------------------------

        second = diary.record(
            event_type="system",
            description=(
                "Diary persistence test passed."
            ),
            source="test",
        )

        assert second.id is not None

        assert (
            second.id
            != first.id
        )

        # --------------------------------------------------
        # Retrieve
        # --------------------------------------------------

        restored = diary.get(
            first.id
        )

        assert restored is not None

        assert (
            restored.description
            == first.description
        )

        assert (
            restored.metadata["phase"]
            == "R2.3"
        )

        # --------------------------------------------------
        # Recent events
        # --------------------------------------------------

        recent = diary.recent()

        assert len(recent) == 2

        assert (
            recent[0].id
            == second.id
        )

        assert (
            recent[1].id
            == first.id
        )

        # --------------------------------------------------
        # Conversation filtering
        # --------------------------------------------------

        conversation_events = (
            diary.recent(
                conversation_id=conversation_id
            )
        )

        assert len(
            conversation_events
        ) == 1

        assert (
            conversation_events[0].id
            == first.id
        )

        # --------------------------------------------------
        # Event type filtering
        # --------------------------------------------------

        interaction_events = (
            diary.recent(
                event_type="interaction"
            )
        )

        assert len(
            interaction_events
        ) == 1

        assert (
            interaction_events[0].id
            == first.id
        )

        # --------------------------------------------------
        # Search
        # --------------------------------------------------

        results = diary.search(
            "memory"
        )

        assert len(results) == 1

        assert (
            results[0].id
            == first.id
        )

        # --------------------------------------------------
        # Append-only behavior
        #
        # We don't update the first event.
        # A new event represents a new occurrence.
        # --------------------------------------------------

        third = diary.record(
            event_type="correction",
            description=(
                "Diary remains append-only."
            ),
            source="test",
        )

        assert third.id is not None

        all_events = diary.recent()

        assert len(all_events) == 3

        # --------------------------------------------------
        # Agent isolation
        # --------------------------------------------------

        # --------------------------------------------------
        # Agent isolation
        # --------------------------------------------------

        # Create a second Agent so that the foreign-key
        # relationship is valid.
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
                "other-agent",
                "testing",
                "idle",
                "2026-08-27T00:00:00+00:00",
            ),
        )

        other_diary = DiaryService(
            repository,
            agent_id="other-agent",
        )

        other_event = other_diary.record(
            event_type="interaction",
            description=(
                "This belongs to another agent."
            ),
        )

        assert other_event.id is not None

        test_agent_events = diary.recent()

        assert len(
            test_agent_events
        ) == 3

        other_agent_events = (
            other_diary.recent()
        )

        assert len(
            other_agent_events
        ) == 1

        assert (
            other_agent_events[0].id
            == other_event.id
        )
        # --------------------------------------------------
        # Persistence across reload
        # --------------------------------------------------

        db_again = Database(
            database_path
        )

        db_again.initialize()

        repository_again = DiaryRepository(
            db_again
        )

        diary_again = DiaryService(
            repository_again,
            agent_id="test-jarvis",
        )

        restored_events = (
            diary_again.recent()
        )

        assert len(
            restored_events
        ) == 3

        restored_first = diary_again.get(
            first.id
        )

        assert restored_first is not None

        assert (
            restored_first.description
            == first.description
        )

        print(
            "DIARY EVENTS:"
        )

        for event in restored_events:

            print(
                f"[{event.event_type}] "
                f"{event.description}"
            )

        print()

        print(
            "PASS: Diary persistence, "
            "querying, filtering, and "
            "agent isolation work."
        )


if __name__ == "__main__":
    main()