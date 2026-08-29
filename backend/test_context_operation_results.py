"""
R2.10B.8

Operation Results -> Context integration tests.
"""

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationStatus,
)
from jarvis.state.models import (
    AgentState,
)


SYSTEM_PROMPT = "You are Jarvis."


def _build_state() -> AgentState:
    return AgentState(
        agent_id="operation-result-test",
        conversation_id=None,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def test_success_result_reaches_context() -> None:
    result = OperationResult.success_result(
        operation="memory_create",
        data={
            "memory_id": 42,
            "content": (
                "Jarvis uses a modular architecture."
            ),
        },
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What just happened?",
        state=_build_state(),
        operation_results=[
            result
        ],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "OPERATION RESULTS" in content
    assert "[operation=memory_create]" in content
    assert "status=success" in content
    assert "success=True" in content
    assert "memory_id" in content
    assert "modular architecture" in content


def test_failure_result_reaches_context() -> None:
    result = OperationResult.failure_result(
        operation="memory_get",
        error_code=OperationErrorCode.NOT_FOUND,
        error_message=(
            "Memory 999 does not exist."
        ),
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What happened?",
        state=_build_state(),
        operation_results=[
            result
        ],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "OPERATION RESULTS" in content
    assert "[operation=memory_get]" in content
    assert "status=failure" in content
    assert "success=False" in content
    assert "error_code=not_found" in content
    assert (
        "Memory 999 does not exist."
        in content
    )


def test_multiple_operation_results_preserve_order() -> None:
    results = [
        OperationResult.success_result(
            operation="memory_create",
            data={"memory_id": 10},
        ),
        OperationResult.failure_result(
            operation="memory_get",
            error_code=OperationErrorCode.NOT_FOUND,
            error_message="Memory not found.",
        ),
    ]

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="What happened?",
        state=_build_state(),
        operation_results=results,
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    first_position = content.index(
        "[operation=memory_create]"
    )

    second_position = content.index(
        "[operation=memory_get]"
    )

    assert first_position < second_position


def test_empty_operation_results_are_omitted() -> None:
    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="Hello",
        state=_build_state(),
        operation_results=[],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "OPERATION RESULTS" not in content


def test_operation_result_is_transport_safe() -> None:
    result = OperationResult.success_result(
        operation="memory_list",
        data={"count": 3},
    )

    transport = result.to_dict()

    assert transport == {
        "operation": "memory_list",
        "status": "success",
        "success": True,
        "data": {"count": 3},
        "error_code": None,
        "error_message": None,
    }


def main() -> None:
    test_success_result_reaches_context()
    test_failure_result_reaches_context()
    test_multiple_operation_results_preserve_order()
    test_empty_operation_results_are_omitted()
    test_operation_result_is_transport_safe()

    print(
        "R2.10B.8 Operation Results -> Context passed."
    )


if __name__ == "__main__":
    main()