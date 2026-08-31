"""
P6 — Failure-injection tests for the live Agent loop.

These tests lock the current failure semantics at the Agent boundary:

1. An LLM failure after the user turn is persisted leaves the accepted
   user input present, but does not fabricate an assistant turn or Diary
   completion event.
2. An application-tool exception is normalized into OperationResult and
   the Agent continues to its next reasoning step.
3. Malformed Agent Memory Operation arguments are normalized into
   OperationResult and do not escape run().

Only the LLM boundary and, for the tool test, one deterministic tool are
stubbed. The Agent's persistence and information services remain real.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationStatus,
)
from jarvis.storage.database import Database


class RaisingLLM:
    """LLM boundary that fails on its first call."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    def chat(self, *, messages: list, tools: list):
        self.calls += 1
        raise self.exc


class ToolFailureLLM:
    """Requests one failing application tool, then returns normally."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, *, messages: list, tools: list):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if len(self.calls) == 1:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="p6_failing_tool",
                                arguments={},
                            )
                        )
                    ],
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Recovered after the tool failure.",
                tool_calls=[],
            )
        )


class MalformedMemoryOperationLLM:
    """Requests a memory operation with an invalid argument type."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, *, messages: list, tools: list):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if len(self.calls) == 1:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="memory_replace_core",
                                arguments={
                                    "label": 123,
                                    "content": "invalid label type",
                                },
                            )
                        )
                    ],
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Malformed operation was handled.",
                tool_calls=[],
            )
        )


def build_test_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    database_name: str,
) -> tuple[JarvisAgent, Database]:
    """Construct a real Agent against an isolated SQLite database."""

    test_database = Database(
        tmp_path / database_name
    )

    monkeypatch.setattr(
        agent_module,
        "database",
        test_database,
    )

    test_database.initialize()

    return JarvisAgent(), test_database


def conversation_messages(
    database: Database,
    conversation_id: int,
) -> list[dict]:
    """Read the persisted conversation messages."""

    rows = database.fetch_all(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id
        """,
        (conversation_id,),
    )

    return [
        {
            "role": row[0],
            "content": row[1],
        }
        for row in rows
    ]


def diary_event_count(
    database: Database,
    conversation_id: int,
) -> int:
    """Count completed conversation-turn Diary events."""

    row = database.fetch_one(
        """
        SELECT COUNT(*)
        FROM diary_events
        WHERE agent_id = ?
          AND conversation_id = ?
          AND event_type = 'conversation_turn'
        """,
        (
            JarvisAgent.AGENT_ID,
            conversation_id,
        ),
    )

    assert row is not None
    return int(row[0])


def test_llm_failure_mid_turn_preserves_accepted_user_input_without_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A failed LLM call does not fabricate an assistant response or a
    completed Diary event, while the already accepted user input remains
    consistent in memory and Recall persistence.
    """

    agent, database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p6_llm_failure.db",
    )

    agent.llm = RaisingLLM(
        RuntimeError("Injected LLM failure")
    )

    user_input = "Please do something that does not create a memory."

    with pytest.raises(RuntimeError, match="Injected LLM failure"):
        agent.run(user_input)

    # The Agent accepted the user message before entering the LLM boundary.
    assert agent.messages == [
        {
            "role": "user",
            "content": user_input,
        }
    ]

    persisted = conversation_messages(
        database,
        agent.state.conversation_id,
    )

    assert persisted == [
        {
            "role": "user",
            "content": user_input,
        }
    ]

    # No assistant response or successful-turn Diary event was fabricated.
    assert diary_event_count(
        database,
        agent.state.conversation_id,
    ) == 0


def test_tool_exception_becomes_operation_result_and_run_continues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    An uncaught application-tool exception is normalized and supplied to
    the next reasoning step instead of escaping run().
    """

    def failing_tool() -> str:
        raise RuntimeError("Injected tool failure")

    monkeypatch.setitem(
        agent_module.AVAILABLE_TOOLS,
        "p6_failing_tool",
        failing_tool,
    )

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p6_tool_failure.db",
    )

    llm = ToolFailureLLM()
    agent.llm = llm

    result = agent.run(
        "Run the failing test tool."
    )

    assert result == "Recovered after the tool failure."
    assert len(llm.calls) == 2

    assert len(agent.operation_results) == 1

    operation_result = agent.operation_results[0]

    assert operation_result.status == OperationStatus.FAILURE
    assert operation_result.error_code == OperationErrorCode.SERVICE_ERROR
    assert operation_result.error_message == "Injected tool failure"

    second_context = llm.calls[1]["messages"]

    assert any(
        message.get("role") == "tool"
        and message.get("tool_name") == "p6_failing_tool"
        and "Tool execution failed: Injected tool failure"
        in message.get("content", "")
        for message in second_context
    )


def test_malformed_memory_operation_arguments_become_operation_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Invalid Agent Memory Operation argument types are normalized into a
    validation failure and never escape the live Agent run().
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p6_malformed_memory_operation.db",
    )

    llm = MalformedMemoryOperationLLM()
    agent.llm = llm

    result = agent.run(
        "Replace the core memory using these malformed arguments."
    )

    assert result == "Malformed operation was handled."
    assert len(llm.calls) == 2

    assert len(agent.operation_results) == 1

    operation_result = agent.operation_results[0]

    assert operation_result.operation == "memory_replace_core"
    assert operation_result.status == OperationStatus.FAILURE
    assert operation_result.error_code == OperationErrorCode.VALIDATION_ERROR
    assert (
        operation_result.error_message
        == "Memory block label must be a string."
    )