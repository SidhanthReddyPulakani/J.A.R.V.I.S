from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.retrieval import (
    RetrievalResult,
)
from jarvis.state.models import (
    AgentState,
)


SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
"""


def main() -> None:

    state = AgentState(
        agent_id="test-jarvis",
        conversation_id=42,
        current_task="Testing retrieval context",
        current_goal=(
            "Verify retrieved information "
            "enters Context correctly"
        ),
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )

    conversation = [
        {
            "role": "user",
            "content": (
                "What editor am I using?"
            ),
        },
    ]

    retrieval_results = [
        RetrievalResult(
            source="memory",
            identifier=101,
            content=(
                "Sidhanth uses Cursor as "
                "the primary editor."
            ),
            score=0.95,
            metadata={
                "category": "preference",
                "subject": "editor",
            },
        ),
        RetrievalResult(
            source="recall",
            identifier=202,
            content=(
                "We previously discussed "
                "using Cursor for Jarvis."
            ),
            score=0.72,
            metadata={
                "role": "user",
            },
        ),
        RetrievalResult(
            source="relationship",
            identifier=303,
            content=(
                "Jarvis → developed_with: Cursor"
            ),
            score=0.61,
        ),
    ]

    manager = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input=(
            "What editor am I using?"
        ),
        state=state,
        conversation=conversation,
        retrieval_results=(
            retrieval_results
        ),
    )

    context = manager.compile(
        request
    )

    messages = (
        context.as_messages()
    )

    assert len(messages) == 2

    system_message = messages[0]

    assert (
        system_message["role"]
        == "system"
    )

    system_content = (
        system_message["content"]
    )

    # --------------------------------------------------
    # System prompt
    # --------------------------------------------------

    assert (
        "You are Jarvis"
        in system_content
    )

    # --------------------------------------------------
    # Retrieved information section
    # --------------------------------------------------

    assert (
        "RETRIEVED INFORMATION"
        in system_content
    )

    assert (
        "Sidhanth uses Cursor"
        in system_content
    )

    assert (
        "We previously discussed"
        in system_content
    )

    assert (
        "developed_with: Cursor"
        in system_content
    )

    # --------------------------------------------------
    # Scores are preserved
    # --------------------------------------------------

    assert (
        "score=0.950"
        in system_content
    )

    assert (
        "score=0.720"
        in system_content
    )

    # --------------------------------------------------
    # Source identity is preserved
    # --------------------------------------------------

    assert (
        "[memory]"
        in system_content
    )

    assert (
        "[recall]"
        in system_content
    )

    assert (
        "[relationship]"
        in system_content
    )

    # --------------------------------------------------
    # Identifier is preserved
    # --------------------------------------------------

    assert (
        "id=101"
        in system_content
    )

    # --------------------------------------------------
    # Agent State remains separate
    # --------------------------------------------------

    assert (
        "CURRENT AGENT STATE"
        in system_content
    )

    assert (
        "Testing retrieval context"
        in system_content
    )

    assert (
        "Verify retrieved information"
        in system_content
    )

    # --------------------------------------------------
    # Conversation remains separate
    # --------------------------------------------------

    assert (
        messages[1]["role"]
        == "user"
    )

    assert (
        messages[1]["content"]
        == "What editor am I using?"
    )

    # --------------------------------------------------
    # Retrieval is optional
    # --------------------------------------------------

    request_without_retrieval = (
        ContextRequest(
            user_input="Hello",
            state=state,
            conversation=[],
        )
    )

    context_without_retrieval = (
        manager.compile(
            request_without_retrieval
        )
    )

    content_without_retrieval = (
        context_without_retrieval
        .as_messages()[0]["content"]
    )

    assert (
        "RETRIEVED INFORMATION"
        not in content_without_retrieval
    )

    # --------------------------------------------------
    # Empty retrieval results are ignored
    # --------------------------------------------------

    empty_result_request = (
        ContextRequest(
            user_input="Hello",
            state=state,
            conversation=[],
            retrieval_results=[],
        )
    )

    empty_result_context = (
        manager.compile(
            empty_result_request
        )
    )

    empty_content = (
        empty_result_context
        .as_messages()[0]["content"]
    )

    assert (
        "RETRIEVED INFORMATION"
        not in empty_content
    )

    print(
        "COMPILED RETRIEVAL CONTEXT:"
    )

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
        "PASS: Retrieval results enter Context correctly."
    )

    print(
        "PASS: Retrieval remains separate from Agent State."
    )

    print(
        "PASS: Retrieval remains optional."
    )

    print(
        "PASS: Retrieval → Context integration works."
    )


if __name__ == "__main__":
    main()