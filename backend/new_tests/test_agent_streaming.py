from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.core.agent import JarvisAgent
from jarvis.core.agent_turn import AgentToolCall


def make_tool_call(
    name="open_whatsapp",
    arguments=None,
    call_id="call-1",
):
    if arguments is None:
        arguments = {}

    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )


def make_chunk(
    *,
    thinking="",
    content="",
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
            "content": "test",
        }
    ]
    return context


def make_agent(stream_chunks):
    """
    Build only the dependencies required by _run_agent_turn().

    We intentionally bypass JarvisAgent.__init__() because the
    streaming tests should test the turn-level behavior without
    initializing the database, memory, retrieval, diary, etc.
    """

    agent = JarvisAgent.__new__(JarvisAgent)

    # LLM under test
    agent.llm = Mock()
    agent.llm.stream.return_value = iter(stream_chunks)

    # _get_llm_tools() requires a capability registry.
    agent.capability_registry = Mock()
    agent.capability_registry.discover.return_value = []

    return agent


def assert_normalized_tool_call(result, expected):
    assert len(result.tool_calls) == 1

    actual = result.tool_calls[0]

    assert isinstance(actual, AgentToolCall)

    assert actual.id == expected.id
    assert actual.name == expected.function.name
    assert actual.arguments == dict(expected.function.arguments)


def test_open_whatsapp_stops_at_first_complete_tool_call():
    tool_call = make_tool_call(
        name="open_whatsapp",
        arguments={
            "query": "WhatsApp",
        },
    )

    chunks = [
        make_chunk(
            thinking="I should open WhatsApp.",
        ),
        make_chunk(
            tool_calls=[tool_call],
        ),
        make_chunk(
            content="This chunk must not be consumed.",
            done=True,
        ),
    ]

    agent = make_agent(chunks)

    result = agent._run_agent_turn(
        make_context()
    )

    assert_normalized_tool_call(
        result,
        tool_call,
    )

    # The LLM stream was requested once.
    agent.llm.stream.assert_called_once()

    # Verify the tool definitions were requested successfully.
    agent.capability_registry.discover.assert_called_once()


def test_ambiguous_app_request_without_tool_call():
    chunks = [
        make_chunk(
            thinking="The application is ambiguous.",
            content="Which application would you like me to open?",
        ),
        make_chunk(
            done=True,
        ),
    ]

    agent = make_agent(chunks)

    result = agent._run_agent_turn(
        make_context()
    )

    assert result.tool_calls == ()

    assert result.assistant_message["role"] == "assistant"

    assert (
        result.assistant_message["content"]
        == "Which application would you like me to open?"
    )


def test_simple_conversation_without_tool_call():
    chunks = [
        make_chunk(
            thinking="I can answer directly.",
            content="Hello! How can I help?",
        ),
        make_chunk(
            done=True,
        ),
    ]

    agent = make_agent(chunks)

    result = agent._run_agent_turn(
        make_context()
    )

    assert result.tool_calls == ()

    assert result.assistant_message["role"] == "assistant"

    assert (
        result.assistant_message["content"]
        == "Hello! How can I help?"
    )


def test_unknown_capability_does_not_create_fake_tool_call():
    chunks = [
        make_chunk(
            thinking="There is no matching capability.",
            content="I don't have a capability for that.",
        ),
        make_chunk(
            done=True,
        ),
    ]

    agent = make_agent(chunks)

    result = agent._run_agent_turn(
        make_context()
    )

    assert result.tool_calls == ()

    assert (
        result.assistant_message["content"]
        == "I don't have a capability for that."
    )


def test_second_request_after_stream_cancellation():
    first_tool_call = make_tool_call(
        name="open_whatsapp",
        arguments={
            "query": "WhatsApp",
        },
        call_id="call-1",
    )

    second_tool_call = make_tool_call(
        name="open_camera",
        arguments={},
        call_id="call-2",
    )

    first_chunks = [
        make_chunk(
            thinking="Open WhatsApp.",
        ),
        make_chunk(
            tool_calls=[first_tool_call],
        ),
        make_chunk(
            content="This must not be consumed.",
            done=True,
        ),
    ]

    second_chunks = [
        make_chunk(
            thinking="Open the camera.",
        ),
        make_chunk(
            tool_calls=[second_tool_call],
        ),
        make_chunk(
            content="This must not be consumed.",
            done=True,
        ),
    ]

    agent = JarvisAgent.__new__(JarvisAgent)

    agent.llm = Mock()

    agent.llm.stream.side_effect = [
        iter(first_chunks),
        iter(second_chunks),
    ]

    agent.capability_registry = Mock()
    agent.capability_registry.discover.return_value = []

    first_result = agent._run_agent_turn(
        make_context()
    )

    assert_normalized_tool_call(
        first_result,
        first_tool_call,
    )

    second_result = agent._run_agent_turn(
        make_context()
    )

    assert_normalized_tool_call(
        second_result,
        second_tool_call,
    )

    assert agent.llm.stream.call_count == 2


def test_multi_turn_conversation():
    first_tool_call = make_tool_call(
        name="open_whatsapp",
        arguments={
            "query": "WhatsApp",
        },
        call_id="call-1",
    )

    second_tool_call = make_tool_call(
        name="send_whatsapp_message",
        arguments={
            "contact": "John",
            "message": "Hello",
        },
        call_id="call-2",
    )

    first_chunks = [
        make_chunk(
            thinking="The user wants WhatsApp opened.",
        ),
        make_chunk(
            tool_calls=[first_tool_call],
        ),
        make_chunk(
            done=True,
        ),
    ]

    second_chunks = [
        make_chunk(
            thinking="Now I should send the message.",
        ),
        make_chunk(
            tool_calls=[second_tool_call],
        ),
        make_chunk(
            done=True,
        ),
    ]

    agent = JarvisAgent.__new__(JarvisAgent)

    agent.llm = Mock()

    agent.llm.stream.side_effect = [
        iter(first_chunks),
        iter(second_chunks),
    ]

    agent.capability_registry = Mock()
    agent.capability_registry.discover.return_value = []

    first_result = agent._run_agent_turn(
        make_context()
    )

    assert_normalized_tool_call(
        first_result,
        first_tool_call,
    )

    second_result = agent._run_agent_turn(
        make_context()
    )

    assert_normalized_tool_call(
        second_result,
        second_tool_call,
    )

    assert agent.llm.stream.call_count == 2
