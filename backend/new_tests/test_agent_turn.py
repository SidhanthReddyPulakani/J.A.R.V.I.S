from jarvis.core.agent_turn import (
    AgentToolCall,
    AgentTurnResult,
)


def test_agent_turn_without_tools_is_complete():
    turn = AgentTurnResult(
        assistant_message={
            "role": "assistant",
            "content": "Hello.",
        },
        tool_calls=(),
    )

    assert turn.completed is True
    assert turn.tool_calls == ()


def test_agent_turn_with_tools_is_not_complete():
    call = AgentToolCall(
        id="call-1",
        name="memory_search",
        arguments={
            "query": "project",
        },
    )

    turn = AgentTurnResult(
        assistant_message={
            "role": "assistant",
            "content": "",
        },
        tool_calls=(call,),
    )

    assert turn.completed is False
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "memory_search"
    assert turn.tool_calls[0].arguments == {
        "query": "project",
    }


def test_agent_turn_preserves_tool_call_identity():
    call = AgentToolCall(
        id="call-42",
        name="knowledge_search",
        arguments={
            "query": "JARVIS",
            "limit": 5,
        },
    )

    turn = AgentTurnResult(
        assistant_message={
            "role": "assistant",
            "content": "",
        },
        tool_calls=(call,),
    )

    assert turn.tool_calls[0].id == "call-42"