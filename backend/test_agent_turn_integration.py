from types import SimpleNamespace

from jarvis.core.agent import JarvisAgent
from jarvis.core.agent_turn import AgentTurnResult


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )
        return self.response


def make_agent():
    agent = object.__new__(JarvisAgent)
    agent.llm = None

    agent._get_llm_tools = lambda: []

    return agent


def test_run_agent_turn_normalizes_final_response():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="Hello.",
            tool_calls=[],
        )
    )

    agent = make_agent()
    agent.llm = FakeLLM(response)

    context = SimpleNamespace(
        as_messages=lambda: [
            {
                "role": "user",
                "content": "Hello",
            }
        ]
    )

    turn = agent._run_agent_turn(context)

    assert isinstance(
        turn,
        AgentTurnResult,
    )

    assert turn.assistant_message == {
        "role": "assistant",
        "content": "Hello.",
    }

    assert turn.tool_calls == ()
    assert turn.completed is True


def test_run_agent_turn_normalizes_tool_call():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="I will search.",
            tool_calls=[
                SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(
                        name="memory_search",
                        arguments={
                            "query": "JARVIS",
                        },
                    ),
                )
            ],
        )
    )

    agent = make_agent()
    agent.llm = FakeLLM(response)

    context = SimpleNamespace(
        as_messages=lambda: []
    )

    turn = agent._run_agent_turn(context)

    assert turn.assistant_message == {
        "role": "assistant",
        "content": "I will search.",
    }

    assert len(turn.tool_calls) == 1

    call = turn.tool_calls[0]

    assert call.id == "call-1"
    assert call.name == "memory_search"
    assert call.arguments == {
        "query": "JARVIS",
    }

    assert turn.completed is False


def test_run_agent_turn_preserves_multiple_tool_calls():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="I need two pieces of information.",
            tool_calls=[
                SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(
                        name="memory_search",
                        arguments={
                            "query": "first",
                        },
                    ),
                ),
                SimpleNamespace(
                    id="call-2",
                    function=SimpleNamespace(
                        name="knowledge_search",
                        arguments={
                            "query": "second",
                        },
                    ),
                ),
            ],
        )
    )

    agent = make_agent()
    agent.llm = FakeLLM(response)

    context = SimpleNamespace(
        as_messages=lambda: []
    )

    turn = agent._run_agent_turn(context)

    assert len(turn.tool_calls) == 2

    assert turn.tool_calls[0].name == "memory_search"
    assert turn.tool_calls[1].name == "knowledge_search"

    assert turn.completed is False