"""
R2.10B.9

Capability Information Boundary tests.

No capability implementation is required.

These tests verify only that information supplied through the
ContextRequest capability-information boundary is compiled into
Context correctly.
"""

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.state.models import AgentState


SYSTEM_PROMPT = "You are Jarvis."


def _build_state() -> AgentState:
    return AgentState(
        agent_id="capability-information-test",
        conversation_id=None,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def test_capability_information_reaches_context() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What information is available?",
        state=_build_state(),
        capability_information=[
            "The active application is Cursor.",
            "The current workspace is Jarvis.",
        ],
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "CAPABILITY INFORMATION"
        in system_content
    )

    assert (
        "The active application is Cursor."
        in system_content
    )

    assert (
        "The current workspace is Jarvis."
        in system_content
    )


def test_structured_capability_information_is_supported() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What is the capability reporting?",
        state=_build_state(),
        capability_information=[
            {
                "capability": "example",
                "status": "available",
                "description": (
                    "Example capability information."
                ),
            }
        ],
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "CAPABILITY INFORMATION"
        in system_content
    )

    assert (
        "capability: example"
        in system_content
    )

    assert (
        "status: available"
        in system_content
    )

    assert (
        "Example capability information."
        in system_content
    )


def test_empty_capability_information_is_omitted() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="Hello",
        state=_build_state(),
        capability_information=[],
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "CAPABILITY INFORMATION"
        not in system_content
    )


def test_blank_capability_information_is_omitted() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="Hello",
        state=_build_state(),
        capability_information=[
            "",
            "   ",
            None,
        ],
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "CAPABILITY INFORMATION"
        not in system_content
    )


def test_context_has_no_capability_implementation_dependency() -> None:
    """
    This is intentionally a lightweight architectural assertion.

    The Context package must be able to compile capability information
    without importing or instantiating any capability implementation.
    """

    import jarvis.context.compiler as compiler_module

    assert not hasattr(
        compiler_module,
        "Capability",
    )


def main() -> None:
    test_capability_information_reaches_context()
    test_structured_capability_information_is_supported()
    test_empty_capability_information_is_omitted()
    test_blank_capability_information_is_omitted()
    test_context_has_no_capability_implementation_dependency()

    print(
        "R2.10B.9 Capability Information Boundary passed."
    )


if __name__ == "__main__":
    main()