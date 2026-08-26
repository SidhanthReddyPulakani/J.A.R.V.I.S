from jarvis.core.context import ContextManager
from jarvis.core.state import AgentState


SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
"""


def main() -> None:

    state = AgentState(
        agent_id="test-jarvis",
        conversation_id=42,
        current_task="Testing context",
        current_goal="Verify state compilation",
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )

    conversation = [
        {
            "role": "user",
            "content": "What are we working on?",
        },
    ]

    manager = ContextManager(
        system_prompt=SYSTEM_PROMPT
    )

    context = manager.build(
        state=state,
        conversation=conversation,
    )

    messages = context.as_messages()

    assert len(messages) == 2

    system_message = messages[0]

    assert system_message["role"] == "system"

    assert (
        "Testing context"
        in system_message["content"]
    )

    assert (
        "Verify state compilation"
        in system_message["content"]
    )

    assert (
        "Jarvis"
        in system_message["content"]
    )

    assert (
        messages[1]["content"]
        == "What are we working on?"
    )

    print("COMPILED CONTEXT:")
    print()

    for message in messages:
        print(
            f"[{message['role']}]"
        )
        print(
            message["content"]
        )
        print()

    print(
        "PASS: Context compilation works."
    )
    state.set_task(
        "Build the Context Manager"
    )

    context = manager.build(
        state=state,
        conversation=conversation,
    )

    system_content = (
        context.as_messages()[0]["content"]
    )

    assert (
        "Build the Context Manager"
        in system_content
    )

    print(
        "PASS: Context reflects updated Agent State."
    )


if __name__ == "__main__":
    main()