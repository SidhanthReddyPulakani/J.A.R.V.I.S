from jarvis.context.models import AgentContext
from jarvis.context.window import (
    ContextWindowManager,
)
from jarvis.recall.service import RecallService
from jarvis.storage.repositories.conversations import (
    ConversationRepository,
)
from jarvis.storage.database import database


def test_evicted_message_remains_reachable_in_recall():
    """
    P5.6 — Safety invariant

    Evicting a message from the active Context must NOT
    delete it from Recall.

    The message should disappear from the prepared
    context while remaining searchable in persistent
    Recall storage.
    """

    # ------------------------------------------------------
    # Persistence
    # ------------------------------------------------------

    database.initialize()

    recall = RecallService(
        ConversationRepository(
            database
        )
    )

    conversation_id = (
        recall.create_conversation()
    )

    memorable_text = (
        "P5.6 RETENTION TEST: "
        "The hidden historical memory must survive "
        "context eviction."
    )

    # ------------------------------------------------------
    # Persist the historical message
    # ------------------------------------------------------

    recall.add_message(
        conversation_id,
        "user",
        memorable_text,
    )

    # ------------------------------------------------------
    # Confirm it exists in Recall BEFORE eviction
    # ------------------------------------------------------

    before = recall.search(
        memorable_text,
        conversation_id=conversation_id,
        limit=10,
    )

    assert any(
        memorable_text in message["content"]
        for message in before
    )

    # ------------------------------------------------------
    # Build an intentionally over-budget context.
    #
    # The historical message is old and should therefore
    # be selected for eviction before the newest message.
    # ------------------------------------------------------

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": memorable_text,
            },
            {
                "role": "assistant",
                "content": "A" * 4000,
            },
            {
                "role": "user",
                "content": "Newest message.",
            },
        ]
    )

    manager = ContextWindowManager(
        context_budget=500,
    )

    # ------------------------------------------------------
    # Prepare the active context
    # ------------------------------------------------------

    prepared = manager.prepare(
        context
    )

    prepared_contents = [
        message.get(
            "content",
            "",
        )
        for message in prepared.as_messages()
    ]

    # ------------------------------------------------------
    # The historical message must have been evicted
    # ------------------------------------------------------

    assert not any(
        memorable_text in content
        for content in prepared_contents
    )

    # ------------------------------------------------------
    # P5.6 SAFETY INVARIANT
    #
    # Eviction from active context must NOT delete the
    # persisted Recall record.
    # ------------------------------------------------------

    after = recall.search(
        memorable_text,
        conversation_id=conversation_id,
        limit=10,
    )

    assert any(
        memorable_text in message["content"]
        for message in after
    )