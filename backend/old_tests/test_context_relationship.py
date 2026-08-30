from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.relationships.models import (
    Relationship,
)
from jarvis.state.models import (
    AgentState,
)


SYSTEM_PROMPT = "You are Jarvis."


def _build_state() -> AgentState:
    return AgentState(
        agent_id="relationship-test",
        conversation_id=None,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def test_relationship_reaches_context() -> None:
    relationship = Relationship(
        id=42,
        source="Jarvis",
        target_type="technology",
        target="Python",
        confidence=0.91,
        confirmations=2,
        uses=3,
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What does Jarvis use?",
        state=_build_state(),
        relationships=[
            relationship
        ],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "RELATIONSHIPS" in content
    assert "[relationship]" in content
    assert "id=42" in content
    assert "confidence=0.910" in content
    assert "Jarvis → technology: Python" in content


def test_empty_relationships_are_omitted() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="Hello",
        state=_build_state(),
        relationships=[],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "RELATIONSHIPS" not in content


def main() -> None:
    test_relationship_reaches_context()
    test_empty_relationships_are_omitted()

    print(
        "R2.10B.7 Relationship → Context passed."
    )


if __name__ == "__main__":
    main()