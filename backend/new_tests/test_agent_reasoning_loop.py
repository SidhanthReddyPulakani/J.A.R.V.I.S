from types import SimpleNamespace

from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import (
    OperationStatus,
)
from jarvis.state.models import AgentState
from jarvis.core.agent_trace import (
    AgentTerminationReason,
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if not self.responses:
            raise AssertionError(
                "FakeLLM received more calls than expected."
            )

        return self.responses.pop(0)


def make_response(
    content="",
    tool_calls=None,
):
    return SimpleNamespace(
        message=SimpleNamespace(
            content=content,
            tool_calls=tool_calls or [],
        )
    )


def make_tool_call(
    call_id,
    name,
    arguments,
):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def make_agent(fake_llm):
    agent = object.__new__(JarvisAgent)

    agent.llm = fake_llm
    agent.messages = []
    agent.operation_results = []

    agent.state = AgentState(
        agent_id="test-agent",
        conversation_id=1,
    )
    agent.recall = SimpleNamespace(
        add_message=lambda *args, **kwargs: None,
    )

    agent.diary = SimpleNamespace(
        record=lambda *args, **kwargs: None,
    )

    agent._persist_state = lambda: None
    agent._form_memories = lambda *args, **kwargs: None

    agent._get_llm_tools = lambda: []

    agent._build_context = lambda user_input=None: (
        SimpleNamespace(
            as_messages=lambda: list(agent.messages)
        )
    )

    return agent


def test_agent_can_execute_three_reasoning_steps():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I need the first piece of information.",
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
                content="I need one more piece of information.",
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
                content="I have enough information now.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    execution_count = {
        "value": 0,
    }

    def fake_memory_operation(
        name,
        args,
    ):
        execution_count["value"] += 1

        from jarvis.memory.operation_results import (
            OperationResult,
        )

        return OperationResult.success_result(
            operation=name,
            data={
                "query": args["query"],
                "step": execution_count["value"],
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find the information."
    )

    assert result == (
        "I have enough information now."
    )

    assert len(fake_llm.calls) == 3

    assert execution_count["value"] == 2

    assert len(agent.operation_results) == 2

    assert all(
        operation.status
        == OperationStatus.SUCCESS
        for operation in agent.operation_results
    )


def test_agent_stops_when_model_returns_no_tool_calls():
    fake_llm = FakeLLM(
        [
            make_response(
                content="Final answer.",
            )
        ]
    )

    agent = make_agent(fake_llm)

    result = agent.run(
        "Answer this."
    )

    assert result == "Final answer."

    assert len(fake_llm.calls) == 1

    assert agent.operation_results == []


def test_agent_executes_multiple_tool_calls_in_one_turn():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I need two things.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "first",
                        },
                    ),
                    make_tool_call(
                        "call-2",
                        "memory_search",
                        {
                            "query": "second",
                        },
                    ),
                ],
            ),
            make_response(
                content="Done.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    executed_calls = []

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationResult,
        )

        executed_calls.append(
            {
                "name": name,
                "args": args,
            }
        )

        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Gather both pieces."
    )

    assert result == "Done."

    assert len(fake_llm.calls) == 2

    assert executed_calls == [
        {
            "name": "memory_search",
            "args": {
                "query": "first",
            },
        },
        {
            "name": "memory_search",
            "args": {
                "query": "second",
            },
        },
    ]

    assert len(agent.operation_results) == 2


def test_agent_continues_after_tool_failure():
    fake_llm = FakeLLM(
        [
            make_response(
                content="The first search failed. I will try another.",
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
                content="I recovered and have the answer.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationErrorCode,
            OperationResult,
        )

        return OperationResult.failure_result(
            operation=name,
            error_code=OperationErrorCode.SERVICE_ERROR,
            error_message="Search failed.",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find something."
    )

    assert result == (
        "I recovered and have the answer."
    )

    assert len(fake_llm.calls) == 2

    assert len(agent.operation_results) == 1

    assert (
        agent.operation_results[0].status
        == OperationStatus.FAILURE
    )


def test_agent_respects_max_reasoning_steps():
    responses = []

    for index in range(
        JarvisAgent.MAX_REASONING_STEPS
    ):
        responses.append(
            make_response(
                content=(
                    f"Still reasoning: {index}"
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

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationResult,
        )

        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Keep reasoning."
    )

    assert result == (
        "I wasn't able to finish reasoning "
        "about that within the allowed number "
        "of steps."
    )

    assert (
        len(fake_llm.calls)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    assert (
        len(agent.operation_results)
        == JarvisAgent.MAX_REASONING_STEPS
    )


def test_next_reasoning_step_receives_previous_tool_result():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="I can now answer.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationResult,
        )

        return OperationResult.success_result(
            operation=name,
            data={
                "found": "JARVIS memory",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "What do you know about JARVIS?"
    )

    assert result == "I can now answer."

    assert len(fake_llm.calls) == 2

    second_turn_messages = (
        fake_llm.calls[1]["messages"]
    )

    assert any(
        message.get("role") == "tool"
        and message.get("tool_name")
        == "memory_search"
        for message in second_turn_messages
    )


def test_assistant_tool_calls_are_preserved_between_steps():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="Done.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationResult,
        )

        return OperationResult.success_result(
            operation=name,
            data="found",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Search memory."
    )

    assert result == "Done."

    second_turn_messages = (
        fake_llm.calls[1]["messages"]
    )

    assistant_messages = [
        message
        for message in second_turn_messages
        if message.get("role")
        == "assistant"
    ]

    assert len(assistant_messages) == 1

    assistant_message = (
        assistant_messages[0]
    )

    assert assistant_message[
        "tool_calls"
    ] == [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "memory_search",
                "arguments": {
                    "query": "JARVIS",
                },
            },
        }
    ]

def test_context_is_rebuilt_between_reasoning_steps():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I need to search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="I have the information now.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    contexts = []

    def fake_build_context(user_input=None):
        context = SimpleNamespace(
            user_input=user_input,
            messages=list(agent.messages),
            operation_results=list(
                agent.operation_results
            ),
            as_messages=lambda: list(
                agent.messages
            ),
        )

        contexts.append(context)

        return context

    agent._build_context = fake_build_context

    def fake_memory_operation(
        name,
        args,
    ):
        from jarvis.memory.operation_results import (
            OperationResult,
        )

        return OperationResult.success_result(
            operation=name,
            data={
                "result": "JARVIS information",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "What do you know about JARVIS?"
    )

    assert result == (
        "I have the information now."
    )

    # Initial context + rebuilt context.
    assert len(contexts) == 2

    first_context = contexts[0]
    second_context = contexts[1]

    # They must be separate context objects.
    assert second_context is not first_context

    # The first context was assembled before the
    # operation executed.
    assert first_context.operation_results == []

    # The second context was assembled after the
    # operation executed.
    assert len(
        second_context.operation_results
    ) == 1

    assert (
        second_context.operation_results[0].data
        == {
            "result": "JARVIS information",
        }
    )

    # The second context also contains the runtime
    # messages produced by the previous reasoning step.
    assert any(
        message.get("role") == "assistant"
        and message.get("tool_calls")
        for message in second_context.messages
    )

    assert any(
        message.get("role") == "tool"
        and message.get("tool_name")
        == "memory_search"
        for message in second_context.messages
    )
def test_real_context_pipeline_is_rebuilt_between_reasoning_steps(
    monkeypatch,
    tmp_path,
):
    """
    Verify that a later reasoning step receives context produced
    by the real Agent context-assembly pipeline after an operation
    has executed.

    Only the LLM and operation execution are controlled. The real
    _build_context(), ContextCompiler, and ContextWindowManager
    remain active.
    """

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    fake_llm = FakeLLM(
        [
            make_response(
                content="I need to search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="I found the information.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    # --------------------------------------------------------------
    # Preserve the REAL _build_context implementation.
    #
    # The lightweight agent fixture normally replaces it, so bind
    # the real method back onto this instance.
    # --------------------------------------------------------------

    from jarvis.core.agent import JarvisAgent

    agent._build_context = (
        JarvisAgent._build_context.__get__(
            agent,
            JarvisAgent,
        )
    )

    # --------------------------------------------------------------
    # Provide the real context dependencies required by
    # JarvisAgent._build_context().
    # --------------------------------------------------------------

    agent.retrieval = SimpleNamespace(
        search=lambda *args, **kwargs: [],
    )

    agent.diary = SimpleNamespace(
        search=lambda *args, **kwargs: [],
        recent=lambda *args, **kwargs: [],
        record=lambda *args, **kwargs: None,
    )

    agent.core_memory = SimpleNamespace(
        list_blocks=lambda: [],
    )

    agent.context_compiler = (
        __import__(
            "jarvis.context.compiler",
            fromlist=["ContextCompiler"],
        ).ContextCompiler(
            system_prompt="Test system prompt",
        )
    )

    agent.context_window = (
        __import__(
            "jarvis.context.window",
            fromlist=["ContextWindowManager"],
        ).ContextWindowManager()
    )

    # --------------------------------------------------------------
    # Capture the actual AgentContext objects returned by the real
    # context pipeline.
    # --------------------------------------------------------------

    built_contexts = []

    real_build_context = agent._build_context

    def recording_build_context(
        user_input="",
        operation_results=None,
    ):
        context = real_build_context(
            user_input=user_input,
            operation_results=operation_results,
        )

        built_contexts.append(context)

        return context

    agent._build_context = recording_build_context

    # --------------------------------------------------------------
    # Fake the operation itself, but keep the real
    # OperationResult contract.
    # --------------------------------------------------------------

    def fake_memory_operation(
        name,
        args,
    ):
        return OperationResult.success_result(
            operation=name,
            data={
                "answer": "JARVIS context information",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    # --------------------------------------------------------------
    # Run the real Agent loop.
    # --------------------------------------------------------------

    result = agent.run(
        "What do you know about JARVIS?"
    )

    assert result == (
        "I found the information."
    )

    # Initial context + one rebuilt context.
    assert len(built_contexts) == 2

    first_context = built_contexts[0]
    second_context = built_contexts[1]

    # They must be different compiled context objects.
    assert second_context is not first_context

    # --------------------------------------------------------------
    # The first context must not contain the operation result.
    # --------------------------------------------------------------

    first_messages = (
        first_context.as_messages()
    )

    assert not any(
        "JARVIS context information"
        in str(message)
        for message in first_messages
    )

    # --------------------------------------------------------------
    # The second context must contain the result produced after
    # step 1.
    # --------------------------------------------------------------

    second_messages = (
        second_context.as_messages()
    )

    assert any(
        "JARVIS context information"
        in str(message)
        for message in second_messages
    )

    # --------------------------------------------------------------
    # The actual LLM call must have received that rebuilt context.
    # --------------------------------------------------------------

    second_llm_messages = (
        fake_llm.calls[1]["messages"]
    )

    assert any(
        "JARVIS context information"
        in str(message)
        for message in second_llm_messages
    )

def test_agent_recovers_from_tool_failure_with_another_operation():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will try the first search.",
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
                content="The first search failed. I will try another.",
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
                content="I found the information using the fallback search.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationErrorCode,
        OperationResult,
    )

    calls = []

    def fake_memory_operation(name, args):
        calls.append(args["query"])

        if args["query"] == "primary":
            return OperationResult.failure_result(
                operation=name,
                error_code=OperationErrorCode.SERVICE_ERROR,
                error_message="Primary search failed.",
            )

        return OperationResult.success_result(
            operation=name,
            data={
                "answer": "Fallback result.",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find the information."
    )

    assert result == (
        "I found the information using the fallback search."
    )

    assert calls == [
        "primary",
        "fallback",
    ]

    assert len(fake_llm.calls) == 3

    assert len(agent.operation_results) == 2

    assert (
        agent.operation_results[0].status
        == OperationStatus.FAILURE
    )

    assert (
        agent.operation_results[1].status
        == OperationStatus.SUCCESS
    )

def test_tool_failure_is_visible_to_recovery_turn():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will search.",
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
                content="I saw the failure and changed strategy.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationErrorCode,
        OperationResult,
    )

    def fake_memory_operation(name, args):
        return OperationResult.failure_result(
            operation=name,
            error_code=OperationErrorCode.SERVICE_ERROR,
            error_message="Primary search failed.",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find something."
    )

    assert result == (
        "I saw the failure and changed strategy."
    )

    assert len(fake_llm.calls) == 2

    second_turn = fake_llm.calls[1]["messages"]

    assert any(
        "Primary search failed."
        in str(message)
        for message in second_turn
    )

def test_execution_trace_records_successful_operation():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="Done.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    def fake_memory_operation(name, args):
        return OperationResult.success_result(
            operation=name,
            data={
                "answer": "JARVIS found",
            },
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    result = agent.run(
        "Find JARVIS."
    )

    assert result == "Done."

    trace = agent.last_execution_trace

    assert trace.termination_reason == (
        AgentTerminationReason.MODEL_COMPLETED
    )

    assert len(trace.steps) == 2

    first_step = trace.steps[0]

    assert first_step.step == 1
    assert len(first_step.observations) == 1

    observation = first_step.observations[0]

    assert observation.tool_call_id == "call-1"
    assert observation.operation == "memory_search"

    assert (
        observation.result.status
        == OperationStatus.SUCCESS
    )

    assert observation.result.data == {
        "answer": "JARVIS found",
    }

    # The final model turn had no operations.
    assert trace.steps[1].step == 2
    assert trace.steps[1].observations == []


def test_execution_trace_records_failed_operation():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I will search.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "JARVIS",
                        },
                    )
                ],
            ),
            make_response(
                content="The search failed.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationErrorCode,
        OperationResult,
    )

    def fake_memory_operation(name, args):
        return OperationResult.failure_result(
            operation=name,
            error_code=OperationErrorCode.SERVICE_ERROR,
            error_message="Search failed.",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    agent.run(
        "Search for JARVIS."
    )

    trace = agent.last_execution_trace

    assert trace.termination_reason == (
        AgentTerminationReason.MODEL_COMPLETED
    )

    observation = (
        trace.steps[0].observations[0]
    )

    assert observation.tool_call_id == "call-1"
    assert observation.operation == "memory_search"

    assert (
        observation.result.status
        == OperationStatus.FAILURE
    )

    assert (
        observation.result.error_message
        == "Search failed."
    )

    assert (
        observation.result.error_code
        == OperationErrorCode.SERVICE_ERROR
    )


def test_execution_trace_records_multiple_operations_in_one_step():
    fake_llm = FakeLLM(
        [
            make_response(
                content="I need both.",
                tool_calls=[
                    make_tool_call(
                        "call-1",
                        "memory_search",
                        {
                            "query": "first",
                        },
                    ),
                    make_tool_call(
                        "call-2",
                        "memory_search",
                        {
                            "query": "second",
                        },
                    ),
                ],
            ),
            make_response(
                content="Done.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    from jarvis.memory.operation_results import (
        OperationResult,
    )

    def fake_memory_operation(name, args):
        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    agent.run(
        "Find both."
    )

    trace = agent.last_execution_trace

    assert len(trace.steps) == 2

    observations = (
        trace.steps[0].observations
    )

    assert len(observations) == 2

    assert observations[0].tool_call_id == "call-1"
    assert observations[0].operation == "memory_search"

    assert observations[1].tool_call_id == "call-2"
    assert observations[1].operation == "memory_search"

    assert observations[0].result.data == {
        "query": "first",
    }

    assert observations[1].result.data == {
        "query": "second",
    }


def test_execution_trace_records_max_steps_termination():
    responses = []

    for index in range(
        JarvisAgent.MAX_REASONING_STEPS
    ):
        responses.append(
            make_response(
                content=f"Step {index}.",
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

    def fake_memory_operation(name, args):
        return OperationResult.success_result(
            operation=name,
            data=args,
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    agent.run(
        "Keep going."
    )

    trace = agent.last_execution_trace

    assert trace.termination_reason == (
        AgentTerminationReason.MAX_STEPS_REACHED
    )

    assert (
        len(trace.steps)
        == JarvisAgent.MAX_REASONING_STEPS
    )

    assert all(
        step.step == index + 1
        for index, step in enumerate(
            trace.steps
        )
    )

    assert all(
        len(step.observations) == 1
        for step in trace.steps
    )


def test_execution_trace_resets_between_runs():
    fake_llm = FakeLLM(
        [
            make_response(
                content="First answer.",
            ),
            make_response(
                content="Second answer.",
            ),
        ]
    )

    agent = make_agent(fake_llm)

    first_result = agent.run(
        "First request."
    )

    first_trace = (
        agent.last_execution_trace
    )

    assert first_result == "First answer."

    assert len(first_trace.steps) == 1

    assert first_trace.termination_reason == (
        AgentTerminationReason.MODEL_COMPLETED
    )

    second_result = agent.run(
        "Second request."
    )

    second_trace = (
        agent.last_execution_trace
    )

    assert second_result == "Second answer."

    # A new trace object must be created for
    # every independent Agent run.
    assert second_trace is not first_trace

    assert len(second_trace.steps) == 1

    assert second_trace.termination_reason == (
        AgentTerminationReason.MODEL_COMPLETED
    )


def test_execution_trace_does_not_record_hidden_reasoning():
    fake_llm = FakeLLM(
        [
            make_response(
                content=(
                    "VISIBLE FINAL ANSWER"
                ),
            )
        ]
    )

    agent = make_agent(fake_llm)

    agent.run(
        "Answer this."
    )

    trace = agent.last_execution_trace

    # The trace should contain execution events,
    # not model reasoning/content.
    trace_text = repr(trace)

    assert (
        "VISIBLE FINAL ANSWER"
        not in trace_text
    )

    assert not hasattr(
        trace.steps[0],
        "reasoning",
    )

    assert not hasattr(
        trace.steps[0],
        "thought",
    )

    assert not hasattr(
        trace.steps[0],
        "chain_of_thought",
    )