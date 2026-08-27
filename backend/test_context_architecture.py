from jarvis.context import (
    AgentContext,
    ContextCompiler,
    ContextRequest,
    ContextWindowManager,
)
from jarvis.state.models import AgentState


def main() -> None:

    state = AgentState(
        agent_id="architecture-test",
        conversation_id=1,
        current_task="Testing Context",
        current_goal="Verify architecture",
        mode="testing",
    )

    request = ContextRequest(
        user_input="Hello",
        state=state,
        conversation=[
            {
                "role": "user",
                "content": "Hello",
            }
        ],
    )

    compiler = ContextCompiler(
        "You are Jarvis."
    )

    compiled = compiler.compile(
        request
    )

    assert isinstance(
        compiled,
        AgentContext,
    )

    assert len(
        compiled.as_messages()
    ) == 2

    window = ContextWindowManager(
        max_messages=2
    )

    prepared = window.prepare(
        compiled
    )

    assert len(
        prepared.as_messages()
    ) == 2

    assert (
        prepared.as_messages()[0]["role"]
        == "system"
    )

    print(
        "PASS: Context architecture works."
    )


if __name__ == "__main__":
    main()