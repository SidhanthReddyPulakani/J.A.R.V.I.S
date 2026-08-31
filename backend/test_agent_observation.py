from jarvis.core.agent_observation import (
    AgentOperationObservation,
)
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationStatus,
)


def test_successful_operation_observation_preserves_result():
    result = OperationResult.success_result(
        operation="memory_search",
        data=[
            {
                "id": "memory-1",
                "content": "JARVIS project",
            }
        ],
    )

    observation = AgentOperationObservation(
        tool_call_id="call-1",
        operation="memory_search",
        result=result,
    )

    assert observation.tool_call_id == "call-1"
    assert observation.operation == "memory_search"

    assert observation.result is result
    assert observation.result.status == OperationStatus.SUCCESS
    assert observation.result.data == [
        {
            "id": "memory-1",
            "content": "JARVIS project",
        }
    ]


def test_failed_operation_observation_preserves_failure():
    result = OperationResult.failure_result(
        operation="knowledge_search",
        error_code=OperationErrorCode.SERVICE_ERROR,
        error_message="Search failed.",
    )

    observation = AgentOperationObservation(
        tool_call_id="call-2",
        operation="knowledge_search",
        result=result,
    )

    assert observation.tool_call_id == "call-2"
    assert observation.operation == "knowledge_search"

    assert observation.result is result
    assert observation.result.status == OperationStatus.FAILURE
    assert observation.result.error_message == "Search failed."


def test_observation_allows_missing_tool_call_id():
    result = OperationResult.success_result(
        operation="memory_read_core",
        data=[],
    )

    observation = AgentOperationObservation(
        tool_call_id=None,
        operation="memory_read_core",
        result=result,
    )

    assert observation.tool_call_id is None
    assert observation.operation == "memory_read_core"
    assert observation.result is result


def test_observation_is_immutable():
    result = OperationResult.success_result(
        operation="memory_list",
        data=[],
    )

    observation = AgentOperationObservation(
        tool_call_id="call-3",
        operation="memory_list",
        result=result,
    )

    try:
        observation.operation = "memory_delete"
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "AgentOperationObservation must be immutable."
        )