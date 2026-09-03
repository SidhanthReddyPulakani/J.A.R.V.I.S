
"""
P3 — Golden-path Agent end-to-end test.

This test exercises the real JarvisAgent.run() lifecycle against
an isolated SQLite database and a deterministic stub LLM.

The test deliberately does NOT mock Jarvis memory, diary, retrieval,
or Core Memory services. Only the LLM boundary is stubbed.

Covered behavior:

1. A memorable fact is supplied through agent.run().
2. Long-Term Memory is actually formed and persisted.
3. A follow-up turn retrieves that Long-Term Memory.
4. The retrieved fact is specifically attributable to the Memory
   retrieval source rather than merely appearing in conversation.
5. A Diary event is persisted after each completed turn.
6. The LLM requests memory_replace_core.
7. The operation executes through AgentMemoryOperations.
8. OperationResult is populated.
9. A second Context is built after the operation.
10. The modified Core Memory is visible in that second Context.
11. The current user message is NOT expected inside the system prompt;
    it remains a normal user message in the LLM conversation boundary.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.storage.database import Database


# ======================================================================
# Deterministic LLM
# ======================================================================


class StubLLM:
    """
    Deterministic LLM replacement.

    The responses deliberately model the minimum reasoning behavior
    required by the P3 golden path:

        turn 1 -> normal answer
        turn 2 -> normal answer
        turn 3 -> request Core Memory replacement
        turn 3 reasoning step 2 -> final answer

    Every call is recorded so the exact Context supplied to the LLM
    can be inspected by the test.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

        self._responses = [
            self._text_response(
                "I will remember that."
            ),
            self._text_response(
                "Your editor is Cursor."
            ),
            self._memory_replace_response(),
            self._text_response(
                "The Core Memory has been updated."
            ),
        ]

    @staticmethod
    def _text_response(
        content: str,
    ):
        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content=content,
                tool_calls=[],
            )
        )

    @staticmethod
    def _memory_replace_response():
        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content=None,
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(
                            name="memory_replace_core",
                            arguments={
                                "label": "human",
                                "content": (
                                    "P3 CORE MEMORY CHANGE"
                                ),
                            },
                        )
                    )
                ],
            )
        )

    def chat(
        self,
        *,
        messages: list,
        tools: list,
    ):
        call_index = len(self.calls)

        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if call_index >= len(self._responses):
            raise AssertionError(
                "StubLLM received more calls than "
                "the P3 scenario defines."
            )

        return self._responses[
            call_index
        ]


# ======================================================================
# LLM inspection helpers
# ======================================================================


def llm_messages(
    llm: StubLLM,
    call_index: int,
) -> list:
    """
    Return the exact messages supplied to one LLM call.
    """

    assert 0 <= call_index < len(
        llm.calls
    )

    return llm.calls[
        call_index
    ]["messages"]


def system_content(
    llm: StubLLM,
    call_index: int,
) -> str:
    """
    Return the system message supplied to one LLM call.
    """

    messages = llm_messages(
        llm,
        call_index,
    )

    assert messages

    assert (
        messages[0]["role"]
        == "system"
    )

    return messages[0]["content"]


def user_messages(
    llm: StubLLM,
    call_index: int,
) -> list[dict]:
    """
    Return user-role messages supplied to one LLM call.
    """

    return [
        message
        for message in llm_messages(
            llm,
            call_index,
        )
        if message.get("role")
        == "user"
    ]


# ======================================================================
# Agent construction
# ======================================================================


def build_test_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """
    Construct a real JarvisAgent using an isolated temporary database.

    The production Agent initialization path remains intact.

    Only the application database boundary and LLM boundary are
    replaced so this test never touches the user's real Jarvis database
    or Ollama instance.
    """

    test_database = Database(
        tmp_path / "jarvis_p3.db"
    )

    # JarvisAgent imports the application database object directly.
    # Replace that reference before constructing the Agent.
    monkeypatch.setattr(
        agent_module,
        "database",
        test_database,
    )

    test_database.initialize()

    agent = JarvisAgent()

    stub_llm = StubLLM()

    agent.llm = stub_llm

    return (
        agent,
        stub_llm,
        test_database,
    )


# ======================================================================
# Database verification helpers
# ======================================================================


def diary_event_count(
    database: Database,
    *,
    agent_id: str,
    conversation_id: int,
) -> int:
    """
    Return the number of Diary events persisted for the conversation.
    """

    row = database.fetch_one(
        """
        SELECT COUNT(*)
        FROM diary_events
        WHERE agent_id = ?
          AND conversation_id = ?
        """,
        (
            agent_id,
            conversation_id,
        ),
    )

    assert row is not None

    return int(row[0])


# ======================================================================
# P3 — Golden Path
# ======================================================================


def test_agent_run_golden_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Verify the complete foundation lifecycle through agent.run().

    This intentionally uses the real Agent services and persistence
    boundaries rather than mocking their behavior.
    """

    agent, llm, database = (
        build_test_agent(
            monkeypatch,
            tmp_path,
        )
    )

    conversation_id = (
        agent.state.conversation_id
    )

    assert conversation_id is not None

    # ==================================================================
    # TURN 1
    # ==================================================================

    memorable_fact = (
        "Remember that my main editor is Cursor."
    )

    agent.run(
        memorable_fact
    )

    # One ordinary turn should produce exactly one LLM call.
    assert len(llm.calls) == 1

    # --------------------------------------------------------------
    # The current user message must remain a normal USER message.
    #
    # It should NOT be expected inside the system prompt.
    # --------------------------------------------------------------

    first_system = system_content(
        llm,
        0,
    )

    assert (
        memorable_fact
        not in first_system
    )

    first_user_messages = (
        user_messages(
            llm,
            0,
        )
    )

    assert first_user_messages

    assert any(
        message["content"]
        == memorable_fact
        for message in first_user_messages
    )

    # --------------------------------------------------------------
    # Long-Term Memory must actually have been formed.
    # --------------------------------------------------------------

    memories = agent.memory.list()

    assert memories, (
        "Turn 1 completed, but Memory Formation "
        "created no Long-Term Memory."
    )

    cursor_memories = [
        memory
        for memory in memories
        if "Cursor" in memory.content
    ]

    assert cursor_memories, (
        "The memorable fact was not persisted as "
        "Long-Term Memory."
    )

    # --------------------------------------------------------------
    # Diary must have recorded the completed turn.
    # --------------------------------------------------------------

    assert (
        diary_event_count(
            database,
            agent_id=agent.AGENT_ID,
            conversation_id=conversation_id,
        )
        == 1
    )

    # ==================================================================
    # TURN 2
    # ==================================================================

    follow_up = (
        "What editor do I use?"
    )

    agent.run(
        follow_up
    )

    assert len(llm.calls) == 2

    second_system = system_content(
        llm,
        1,
    )

    # --------------------------------------------------------------
    # The follow-up itself must again be a user message, not something
    # we expect to find in the system prompt.
    # --------------------------------------------------------------

    assert (
        follow_up
        not in second_system
    )

    second_user_messages = (
        user_messages(
            llm,
            1,
        )
    )

    assert second_user_messages

    assert any(
        message["content"]
        == follow_up
        for message in second_user_messages
    )

    # --------------------------------------------------------------
    # CRITICAL P3 assertion:
    #
    # The fact must appear under the retrieval section and specifically
    # identify the MEMORY source.
    #
    # This prevents a false positive where "Cursor" is merely present
    # because turn 1 is still in conversation history.
    # --------------------------------------------------------------

    assert (
        "RETRIEVED INFORMATION"
        in second_system
    )

    assert (
        "[memory]"
        in second_system
    )

    assert (
        "Cursor"
        in second_system
    )

    # --------------------------------------------------------------
    # Diary must contain both completed turns.
    # --------------------------------------------------------------

    assert (
        diary_event_count(
            database,
            agent_id=agent.AGENT_ID,
            conversation_id=conversation_id,
        )
        == 2
    )

    # ==================================================================
    # TURN 3 — Core Memory operation
    # ==================================================================

    agent.run(
        "Update my Core Memory."
    )

    # Turn 3 must perform two reasoning calls:
    #
    #   call 2 -> LLM requests memory_replace_core
    #   call 3 -> fresh context after operation
    #
    assert len(llm.calls) == 4

    # --------------------------------------------------------------
    # Initial context before the operation.
    # --------------------------------------------------------------

    third_initial_system = (
        system_content(
            llm,
            2,
        )
    )

    assert (
        "P3 CORE MEMORY CHANGE"
        not in third_initial_system
    )

    # --------------------------------------------------------------
    # The operation must have produced a structured OperationResult.
    # --------------------------------------------------------------

    assert (
        len(agent.operation_results)
        == 1
    )

    operation_result = (
        agent.operation_results[0]
    )

    assert (
        operation_result.operation
        == "memory_replace_core"
    )

    # --------------------------------------------------------------
    # Verify the actual Core Memory persistence.
    # --------------------------------------------------------------

    human_block = (
        agent.core_memory.get(
            "human"
        )
    )

    assert human_block is not None

    assert (
        human_block.content
        == "P3 CORE MEMORY CHANGE"
    )

    # --------------------------------------------------------------
    # SECOND CONTEXT BUILD — this is the important part.
    #
    # The operation changed persistent Core Memory, then Agent.run()
    # rebuilt Context before asking the LLM to reason again.
    # --------------------------------------------------------------

    third_final_system = (
        system_content(
            llm,
            3,
        )
    )

    assert (
        "CORE MEMORY"
        in third_final_system
    )

    assert (
        "P3 CORE MEMORY CHANGE"
        in third_final_system
    )

    # --------------------------------------------------------------
    # The third turn's final response is still a normal assistant
    # message, and the turn must be recorded in Diary.
    # --------------------------------------------------------------

    assert (
        diary_event_count(
            database,
            agent_id=agent.AGENT_ID,
            conversation_id=conversation_id,
        )
        == 3
    )

    # ==================================================================
    # Final persistence sanity checks
    # ==================================================================

    persisted_messages = (
        agent.recall.get_messages(
            conversation_id
        )
    )

    assert persisted_messages

    assert any(
        message["role"] == "user"
        and message["content"]
        == memorable_fact
        for message in persisted_messages
    )

    assert any(
        message["role"] == "user"
        and message["content"]
        == follow_up
        for message in persisted_messages
    )

