
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationStatus,
)


def make_tool_call(
    name="apps.launch",
    arguments=None,
    call_id="call-1",
):
    if arguments is None:
        arguments = {
            "query": "WhatsApp",
        }

    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def make_stream_chunk(
    *,
    content="",
    thinking="",
    tool_calls=None,
    done=False,
):
    return {
        "thinking": thinking,
        "content": content,
        "tool_calls": tool_calls or [],
        "done": done,
        "timing": {},
    }


def make_context():
    context = Mock()

    context.as_messages.return_value = [
        {
            "role": "user",
            "content": "Open WhatsApp",
        }
    ]

    return context


def make_agent():
    """
    Construct only the dependencies required by the Phase 4
    execution tests.

    _get_llm_tools() is replaced because these tests are testing
    the execution boundary, not tool-definition discovery.
    """

    agent = JarvisAgent.__new__(JarvisAgent)

    agent.llm = Mock()

    agent.capability_registry = Mock()
    agent.capability_controller = Mock()

    # Keep tool discovery out of these boundary tests.
    agent._get_llm_tools = Mock(
        return_value=[]
    )

    # apps.launch resolves through the Capability path.
    agent.capability_registry.resolve_operation.return_value = (
        Mock()
    )

    return agent


def configure_run_dependencies(agent):
    """
    Configure the minimum Agent state required by run().
    """

    agent.messages = []
    agent.operation_results = []

    agent.state = Mock()
    agent.state.conversation_id = "conversation-1"

    agent.recall = Mock()
    agent.diary = Mock()
    agent.state_repository = Mock()

    agent._form_memories = Mock()
    agent._persist_state = Mock()


def test_capability_request_goes_through_controller():
    agent = make_agent()

    request = Mock()
    request.operation = "apps.launch"
    request.arguments = {
        "query": "WhatsApp",
    }

    expected_result = OperationResult.success_result(
        operation="apps.launch",
        data="WhatsApp launched",
    )

    agent.capability_controller.execute.return_value = (
        expected_result
    )

    result = agent._execute_capability_request(
        request
    )

    assert result is expected_result

    agent.capability_controller.execute.assert_called_once_with(
        request
    )


def test_capability_result_is_returned_as_operation_result():
    agent = make_agent()

    request = Mock()
    request.operation = "apps.launch"
    request.arguments = {
        "query": "WhatsApp",
    }

    expected_result = OperationResult.success_result(
        operation="apps.launch",
        data="WhatsApp launched",
    )

    agent.capability_controller.execute.return_value = (
        expected_result
    )

    result = agent._execute_capability_request(
        request
    )

    assert isinstance(
        result,
        OperationResult,
    )

    assert (
        result.status
        == OperationStatus.SUCCESS
    )

    assert result.operation == "apps.launch"
    assert result.data == "WhatsApp launched"


def test_model_does_not_get_second_turn_before_capability_result():
    """
    Primary Phase 4 invariant:

        LLM turn #1
            ↓
        structured action
            ↓
        CapabilityController.execute()
            ↓
        OperationResult
            ↓
        LLM turn #2

    The second LLM stream must not start until the
    OperationResult has been added to Agent evidence.
    """

    agent = make_agent()

    first_tool_call = make_tool_call(
        name="apps.launch",
        arguments={
            "query": "WhatsApp",
        },
        call_id="call-1",
    )

    capability_result = OperationResult.success_result(
        operation="apps.launch",
        data="WhatsApp launched successfully",
    )

    events = []

    def capability_execute(request):
        events.append(
            (
                "capability_execute",
                request.operation,
            )
        )

        return capability_result

    agent.capability_controller.execute.side_effect = (
        capability_execute
    )

    first_stream = iter(
        [
            make_stream_chunk(
                thinking="Open WhatsApp.",
            ),
            make_stream_chunk(
                tool_calls=[
                    first_tool_call,
                ],
            ),
        ]
    )

    second_stream = iter(
        [
            make_stream_chunk(
                content="WhatsApp is open.",
            ),
            make_stream_chunk(
                done=True,
            ),
        ]
    )

    stream_number = 0

    def stream(*, messages, tools):
        nonlocal stream_number

        stream_number += 1

        events.append(
            (
                "llm_stream",
                stream_number,
            )
        )

        if stream_number == 1:
            return first_stream

        if stream_number == 2:
            # This is the architectural assertion.
            assert capability_result in (
                agent.operation_results
            )

            return second_stream

        raise AssertionError(
            "Unexpected additional LLM stream"
        )

    agent.llm.stream.side_effect = stream

    configure_run_dependencies(agent)

    agent._build_context = Mock(
        side_effect=[
            make_context(),
            make_context(),
        ]
    )

    result = agent.run(
        "Open WhatsApp"
    )

    assert result == "WhatsApp is open."

    assert events == [
        (
            "llm_stream",
            1,
        ),
        (
            "capability_execute",
            "apps.launch",
        ),
        (
            "llm_stream",
            2,
        ),
    ]

    assert agent.llm.stream.call_count == 2

    assert agent.operation_results == [
        capability_result
    ]


def test_failed_capability_result_reaches_next_model_turn():
    """
    A failed capability result is still evidence.

    The Agent must receive the OperationResult before the
    next model turn starts.
    """

    agent = make_agent()

    first_tool_call = make_tool_call(
        name="apps.launch",
        arguments={
            "query": "NotARealApplication",
        },
        call_id="call-1",
    )

    failed_result = OperationResult.failure_result(
        operation="apps.launch",
        error_code=OperationErrorCode.NOT_FOUND,
        error_message="Application not found",
    )

    agent.capability_controller.execute.return_value = (
        failed_result
    )

    first_stream = iter(
        [
            make_stream_chunk(
                tool_calls=[
                    first_tool_call,
                ],
            ),
        ]
    )

    second_stream = iter(
        [
            make_stream_chunk(
                content="I couldn't find that application.",
            ),
            make_stream_chunk(
                done=True,
            ),
        ]
    )

    agent.llm.stream.side_effect = [
        first_stream,
        second_stream,
    ]

    configure_run_dependencies(agent)

    agent._build_context = Mock(
        side_effect=[
            make_context(),
            make_context(),
        ]
    )

    result = agent.run(
        "Open NotARealApplication"
    )

    assert result == (
        "I couldn't find that application."
    )

    assert agent.operation_results == [
        failed_result
    ]

    assert agent.llm.stream.call_count == 2

    agent.capability_controller.execute.assert_called_once()


def test_no_capability_means_no_second_model_turn():
    """
    A completed conversational response requires only one
    model turn and no capability execution.
    """

    agent = make_agent()

    agent.llm.stream.return_value = iter(
        [
            make_stream_chunk(
                content="Hello!",
            ),
            make_stream_chunk(
                done=True,
            ),
        ]
    )

    configure_run_dependencies(agent)

    agent._build_context = Mock(
        return_value=make_context()
    )

    result = agent.run(
        "Hello"
    )

    assert result == "Hello!"

    assert agent.llm.stream.call_count == 1

    agent.capability_controller.execute.assert_not_called()

    assert agent.operation_results == []

