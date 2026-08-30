from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.storage.database import Database
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "conversation_test.db"
        )

        db = Database(
            database_path
        )

        db.initialize()

        repository = ConversationRepository(
            db
        )

        # Create conversation.
        conversation_id = (
            repository.create()
        )

        assert conversation_id is not None

        # Add messages.
        repository.add_message(
            conversation_id,
            "user",
            "Hello Jarvis",
        )

        repository.add_message(
            conversation_id,
            "assistant",
            "Hello. How can I help?",
        )

        repository.add_message(
            conversation_id,
            "user",
            "We are working on Jarvis.",
        )

        # Retrieve.
        messages = repository.get_messages(
            conversation_id
        )

        assert len(messages) == 3

        assert (
            messages[0]["content"]
            == "Hello Jarvis"
        )

        assert (
            messages[1]["content"]
            == "Hello. How can I help?"
        )

        assert (
            messages[2]["content"]
            == "We are working on Jarvis."
        )

        # Search.
        results = repository.search(
            "Jarvis",
            conversation_id=conversation_id,
        )

        assert len(results) == 2

        assert (
            results[0]["content"]
            == "We are working on Jarvis."
        )

        assert (
            results[1]["content"]
            == "Hello Jarvis"
        )
        # Simulate another process.
        db_again = Database(
            database_path
        )

        db_again.initialize()

        repository_again = (
            ConversationRepository(
                db_again
            )
        )

        restored = (
            repository_again.get_messages(
                conversation_id
            )
        )

        assert len(restored) == 3

        print("RESTORED CONVERSATION:")

        for message in restored:
            print(
                f"[{message['role']}] "
                f"{message['content']}"
            )

        print()
        print(
            "PASS: Conversation recall "
            "persists across reload."
        )


if __name__ == "__main__":
    main()