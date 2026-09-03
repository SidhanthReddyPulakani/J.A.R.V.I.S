from types import SimpleNamespace

from jarvis.core.agent import JarvisAgent
from jarvis.core.agent_trace import (
    AgentTerminationReason,
)
from jarvis.memory.operation_results import (
    OperationStatus,
)

from backend.new_tests.test_agent_reasoning_loop import (
    FakeLLM,
    make_agent,
    make_response,
    make_tool_call,
)


def test_p7_multistep_tool_chain_completes_after_multiple_steps():
    """
    P7.8

    Exercise a complete multi-step Agent execution:

        LLM
          -> tool
          -> observation
          -> LLM
          -> tool
          -> observation
          -> LLM
          -> tool
          -> observation
          -> LLM
          -> final answer

    The test verifies the complete run lifecycle rather than
    testing an individual loop mechanism in isolation.
    """

    fake_llm = FakeLLM(
        [
            make_response(
                content="I need the first piece.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "first",
                        },
                    )
                ],
            ),
            make_response(
                content="I have the first piece. I need another.",
                tool_calls=[
                    make_tool_call(
                        "call-2",
                        "memory_search",
                        {
                            "query": "second",
                        },
                    )
                ],
            ),
            make_response(
                content="I have two pieces. One final lookup.",
                tool_calls=[
                    make_tool_call(
                        "call-3",
                        "memory_search",
                        {
                            "query": "third",
                        },
                    )
                ],
            ),
            make_response(
                content="I have everything I need.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    executed_operations = []

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    def fake_memory_operation(
        name,
        args,
    ):
        executed_operations.append(
            {
                "name": name,
                "query": args["query"],
            }
        )

        return OperationResult.success_result(
            operation=name,
            data={
                "query": args["query"],
                "result": (
                    f"result for {args['query']}"
                ),
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Gather all three pieces of information."
    )

    assert result == (
        "I have everything I need."
    )

    # Four model turns:
    # three action turns + final completion.
    assert len(fake_llm.calls) == 4

    assert executed_operations == [
        {
            "name": "memory_search",
            "query": "first",
        },
        {
            "name": "memory_search",
            "query": "second",
        },
        {
            "name": "memory_search",
            "query": "third",
        },
    ]

    assert len(agent.operation_results) == 3

    assert all(
        result.status == OperationStatus.SUCCESS
        for result in agent.operation_results
    )

    trace = agent.last_execution_trace

    assert (
        trace.termination_reason
        == AgentTerminationReason.MODEL_COMPLETED
    )

    assert len(trace.steps) == 4

    assert [
        step.step
        for step in trace.steps
    ] == [1, 2, 3, 4]

    assert [
        len(step.observations)
        for step in trace.steps
    ] == [1, 1, 1, 0]


def test_p7_multistep_execution_recovers_and_continues():
    """
    P7.8

    Verify that a multi-step execution can contain a failure,
    recover from it, continue with another operation, and finally
    terminate normally.
    """

    fake_llm = FakeLLM(
        [
            make_response(
                content="I will try the primary lookup.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "primary",
                        },
                    )
                ],
            ),
            make_response(
                content=(
                    "The primary lookup failed. "
                    "I will use a fallback."
                ),
                tool_calls=[
                    make_tool_call(
                        "call-2",
                        "memory_search",
                        {
                            "query": "fallback",
                        },
                    )
                ],
            ),
            make_response(
                content="The fallback worked. I am done.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationErrorCode,
        OperationResult,
    )

    executed_queries = []

    def fake_memory_operation(
        name,
        args,
    ):
        query = args["query"]

        executed_queries.append(
            query
        )

        if query == "primary":
            return OperationResult.failure_result(
                operation=name,
                error_code=(
                    OperationErrorCode.SERVICE_ERROR
                ),
                error_message=(
                    "Primary lookup failed."
                ),
            )

        return OperationResult.success_result(
            operation=name,
            data={
                "result": "Fallback information."
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find the information."
    )

    assert result == (
        "The fallback worked. I am done."
    )

    assert len(fake_llm.calls) == 3

    assert executed_queries == [
        "primary",
        "fallback",
    ]

    assert len(agent.operation_results) == 2

    assert (
        agent.operation_results[0].status
        == OperationStatus.FAILURE
    )

    assert (
        agent.operation_results[1].status
        == OperationStatus.SUCCESS
    )

    trace = agent.last_execution_trace

    assert (
        trace.termination_reason
        == AgentTerminationReason.MODEL_COMPLETED
    )

    assert len(trace.steps) == 3

    assert (
        trace.steps[0]
        .observations[0]
        .result
        .status
        == OperationStatus.FAILURE
    )

    assert (
        trace.steps[1]
        .observations[0]
        .result
        .status
        == OperationStatus.SUCCESS
    )

    assert (
        trace.steps[2].observations
        == []
    )


def test_p9_continuous_tool_requests_are_hard_bounded():
    """
    P7.9

    Deliberately provide a model that never completes.

    The Agent must terminate exactly at MAX_REASONING_STEPS
    rather than continuing indefinitely.
    """

    responses = []

    for index in range(
        JarvisAgent.MAX_REASONING_STEPS
    ):
        responses.append(
            make_response(
                content=(
                    f"I am still working: {index}"
                ),
                tool_calls=[
                    make_tool_call(
                        f"call-{index}",
                        "memory_search",
                        {
                            "query": f"step-{index}",
                        },
                    )
                ],
            )
        )

    fake_llm = FakeLLM(
        responses
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    executed_queries = []

    def fake_memory_operation(
        name,
        args,
    ):
        executed_queries.append(
            args["query"]
        )

        return OperationResult.success_result(
            operation=name,
            data={
                "result": "still running",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Keep working forever."
    )

    # The Agent must terminate with its safety response.
    assert result == (
        "I wasn't able to finish reasoning "
        "about that within the allowed number "
        "of steps."
    )

    # Exactly the allowed number of model turns.
    assert (
        len(fake_llm.calls)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    # Exactly one operation per model turn.
    assert (
        len(executed_queries)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    assert (
        len(agent.operation_results)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    trace = agent.last_execution_trace

    assert (
        trace.termination_reason
        == AgentTerminationReason.MAX_STEPS_REACHED
    )

    assert (
        len(trace.steps)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    assert [
        step.step
        for step in trace.steps
    ] == list(
        range(
            1,
            JarvisAgent.MAX_REASONING_STEPS + 1,
        )
    )


def test_p9_model_completion_before_limit_terminates_immediately():
    """
    P7.9

    Verify that the safety ceiling is a ceiling, not a target.

    A model that completes after several tool-producing turns
    must stop immediately rather than consuming the remaining
    reasoning budget.
    """

    tool_steps = 4

    responses = []

    for index in range(
        tool_steps
    ):
        responses.append(
            make_response(
                content=f"Working on step {index}.",
                tool_calls=[
                    make_tool_call(
                        f"call-{index}",
                        "memory_search",
                        {
                            "query": f"step-{index}",
                        },
                    )
                ],
            )
        )

    responses.append(
        make_response(
            content="Finished before the limit."
        )
    )

    fake_llm = FakeLLM(
        responses
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    execution_count = {
        "value": 0,
    }

    def fake_memory_operation(
        name,
        args,
    ):
        execution_count["value"] += 1

        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Work until you have enough."
    )

    assert result == (
        "Finished before the limit."
    )

    assert len(fake_llm.calls) == (
        tool_steps + 1
    )

    assert (
        execution_count["value"]
        == tool_steps
    )

    assert (
        len(agent.operation_results)
        == tool_steps
    )

    trace = agent.last_execution_trace

    assert (
        trace.termination_reason
        == AgentTerminationReason.MODEL_COMPLETED
    )

    assert len(trace.steps) == (
        tool_steps + 1
    )

    assert (
        trace.steps[-1].observations
        == []
    )


def test_p9_no_extra_model_call_occurs_after_max_steps():
    """
    P7.9

    This specifically verifies the boundary condition.

    FakeLLM has exactly MAX_REASONING_STEPS responses.
    If Agent.run() accidentally performs one additional model
    call, FakeLLM raises AssertionError and this test fails.
    """

    responses = [
        make_response(
            content="Never finish.",
            tool_calls=[
                make_tool_call(
                    f"call-{index}",
                    "memory_search",
                    {
                        "query": f"step-{index}",
                    },
                )
            ],
        )
        for index in range(
            JarvisAgent.MAX_REASONING_STEPS
        )
    ]

    fake_llm = FakeLLM(
        responses
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    def fake_memory_operation(
        name,
        args,
    ):
        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    agent.run(
        "Do not stop."
    )

    # FakeLLM itself guarantees that an additional call
    # would fail the test.
    assert (
        len(fake_llm.calls)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    assert fake_llm.responses == []