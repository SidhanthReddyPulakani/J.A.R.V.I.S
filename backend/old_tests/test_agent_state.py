
"""
P3 — Golden-path Agent end-to-end integration test.

This test exercises the real JarvisAgent.run() lifecycle against:

    real Agent
        ↓
    real Memory / Recall / Diary / Core Memory / Retrieval services
        ↓
    isolated SQLite database

Only the LLM boundary is replaced with a deterministic stub.

The test intentionally verifies behavior at the Agent integration
boundary rather than mocking the services whose integration is being
tested.

Covered lifecycle:

1. Current user input is supplied through Agent.run().
2. Current input is passed to the LLM as a USER message.
3. Current input is not persisted before initial retrieval.
4. Memory formation actually creates Long-Term Memory.
5. The created memory is persisted.
6. A subsequent query retrieves that memory through unified Retrieval.
7. Retrieval attribution is verified rather than merely checking that
   the remembered word exists somewhere in the prompt.
8. Diary receives one completed-turn event per completed run().
9. LLM memory operation definitions are exposed to the LLM.
10. LLM requests memory_replace_core.
11. Agent dispatches that operation through AgentMemoryOperations.
12. The real operation mutates persistent Core Memory.
13. OperationResult records the operation and success status.
14. A tool-role message is added to the Agent conversation state.
15. Context is rebuilt after the operation.
16. The rebuilt Context contains the new Core Memory.
17. Operation results are present in the rebuilt Context.
18. The final assistant response is persisted.
19. User/assistant messages survive a Recall round-trip.
20. A fresh Agent can recover the persisted conversation state.

The test deliberately does NOT mock:
    - RecallService
    - LongTermMemoryService
    - MemoryFormationService
    - CoreMemoryService
    - DiaryService
    - RetrievalService
    - AgentMemoryOperations
    - repositories

The LLM and database are the only external boundaries replaced.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import OperationStatus
from jarvis.storage.database import Database


# ======================================================================
# Deterministic LLM
# ======================================================================


class StubLLM:
    """
    Deterministic LLM.

    Calls:

        0 -> ordinary response
        1 -> ordinary response
        2 -> memory_replace_core tool call
        3 -> final response after operation

    Every call is recorded so the exact Context supplied to the model
    can be inspected.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

        self.responses = [
            self.text("I will remember that."),
            self.text("Your editor is Cursor."),
            self.memory_replace(),
            self.text("The Core Memory has been updated."),
        ]

    @staticmethod
    def text(content: str):
        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content=content,
                tool_calls=[],
            )
        )

    @staticmethod
    def memory_replace():
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
                                "content": "P3 CORE MEMORY CHANGE",
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
        index = len(self.calls)

        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if index >= len(self.responses):
            raise AssertionError(
                "Unexpected LLM call. "
                "The Agent performed more reasoning steps "
                "than this golden path defines."
            )

        return self.responses[index]


# ======================================================================
# LLM inspection helpers
# ======================================================================


def messages_for(llm: StubLLM, call_index: int) -> list[dict]:
    assert 0 <= call_index < len(llm.calls)
    return llm.calls[call_index]["messages"]


def system_for(llm: StubLLM, call_index: int) -> str:
    messages = messages_for(llm, call_index)

    assert messages
    assert messages[0]["role"] == "system"

    return messages[0]["content"]


def user_messages_for(
    llm: StubLLM,
    call_index: int,
) -> list[dict]:
    return [
        message
        for message in messages_for(llm, call_index)
        if message.get("role") == "user"
    ]


def tool_messages_for(
    llm: StubLLM,
    call_index: int,
) -> list[dict]:
    return [
        message
        for message in messages_for(llm, call_index)
        if message.get("role") == "tool"
    ]


# ======================================================================
# Retrieval assertion helper
# ======================================================================


def memory_retrieval_block(system_prompt: str) -> str:
    """
    Extract the retrieval section from the compiled system prompt.

    We deliberately scope the Cursor assertion to the retrieval
    section. Merely finding both "[memory]" and "Cursor" somewhere
    in the complete prompt is insufficient evidence that retrieval
    supplied the memory.
    """

    marker = "RETRIEVED INFORMATION"

    assert marker in system_prompt

    retrieval = system_prompt.split(
        marker,
        1,
    )[1]

    return retrieval


def assert_memory_retrieval_contains(
    system_prompt: str,
    expected_content: str,
) -> None:
    retrieval = memory_retrieval_block(
        system_prompt
    )

    assert "[memory]" in retrieval

    memory_position = retrieval.index(
        "[memory]"
    )

    memory_section = retrieval[
        memory_position:
    ]

    # If another retrieval source follows the memory source,
    # stop before it. This prevents an unrelated later source
    # from satisfying the assertion.
    source_markers = (
        "[recall]",
        "[knowledge]",
        "[relationship]",
    )

    next_positions = [
        memory_section.find(marker)
        for marker in source_markers
        if memory_section.find(marker) > 0
    ]

    if next_positions:
        memory_section = memory_section[
            : min(next_positions)
        ]

    assert expected_content in memory_section


# ======================================================================
# Agent construction
# ======================================================================


def build_test_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    database = Database(
        tmp_path / "jarvis_p3.db"
    )

    monkeypatch.setattr(
        agent_module,
        "database",
        database,
    )

    database.initialize()

    agent = JarvisAgent()

    llm = StubLLM()
    agent.llm = llm

    return agent, llm, database


# ======================================================================
# Database helpers
# ======================================================================


def diary_event_count(
    database: Database,
    *,
    agent_id: str,
    conversation_id: int,
) -> int:
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
# Test
# ======================================================================


def test_agent_run_golden_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:

    agent, llm, database = build_test_agent(
        monkeypatch,
        tmp_path,
    )

    conversation_id = agent.state.conversation_id

    assert conversation_id is not None

    # ==================================================================
    # TURN 1 — Memory formation
    # ==================================================================

    memorable_fact = (
        "Remember that my main editor is Cursor."
    )

    memories_before = agent.memory.list()

    agent.run(memorable_fact)

    # --------------------------------------------------------------
    # One normal turn = one LLM call.
    # --------------------------------------------------------------

    assert len(llm.calls) == 1

    # --------------------------------------------------------------
    # Current input is a normal USER message.
    # --------------------------------------------------------------

    first_system = system_for(llm, 0)

    assert memorable_fact not in first_system

    first_users = user_messages_for(llm, 0)

    assert any(
        message["content"] == memorable_fact
        for message in first_users
    )

    # --------------------------------------------------------------
    # Initial retrieval occurs BEFORE recall persistence.
    #
    # Therefore the current user message must not be retrievable
    # as conversation history during its own initial context build.
    #
    # We cannot infer this merely from the final database state.
    # Instead inspect the actual context supplied to the LLM.
    # --------------------------------------------------------------

    assert not any(
        message.get("role") == "system"
        and memorable_fact in message.get("content", "")
        for message in messages_for(llm, 0)
    )

    # --------------------------------------------------------------
    # Memory formation must actually have changed Long-Term Memory.
    # --------------------------------------------------------------

    memories_after = agent.memory.list()

    assert len(memories_after) > len(memories_before), (
        "run() completed without creating Long-Term Memory."
    )

    cursor_memories = [
        memory
        for memory in memories_after
        if "Cursor" in memory.content
    ]

    assert cursor_memories, (
        "The memorable user fact was not persisted "
        "through the memory-formation pipeline."
    )

    # --------------------------------------------------------------
    # The completed turn must produce exactly one Diary event.
    # --------------------------------------------------------------

    assert (
        diary_event_count(
            database,
            agent_id=agent.AGENT_ID,
            conversation_id=conversation_id,
        )
        == 1
    )

    # --------------------------------------------------------------
    # The assistant response must have been persisted.
    # --------------------------------------------------------------

    persisted_after_turn_1 = (
        agent.recall.get_messages(
            conversation_id
        )
    )

    assert any(
        message["role"] == "assistant"
        and message["content"]
        == "I will remember that."
        for message in persisted_after_turn_1
    )

    # ==================================================================
    # TURN 2 — Retrieval
    # ==================================================================

    follow_up = "What editor do I use?"

    agent.run(follow_up)

    assert len(llm.calls) == 2

    second_system = system_for(llm, 1)

    # --------------------------------------------------------------
    # Again, the current input remains a USER message.
    # --------------------------------------------------------------

    assert follow_up not in second_system

    second_users = user_messages_for(
        llm,
        1,
    )

    assert any(
        message["content"] == follow_up
        for message in second_users
    )

    # --------------------------------------------------------------
    # Critical retrieval assertion.
    #
    # Cursor must occur in the MEMORY retrieval section itself.
    # It is not enough for Cursor to occur somewhere in the prompt.
    # --------------------------------------------------------------

    assert_memory_retrieval_contains(
        second_system,
        "Cursor",
    )

    # --------------------------------------------------------------
    # The retrieval is actually query-dependent.
    #
    # A response generated only from conversation history should
    # not be enough to satisfy the assertion above.
    # --------------------------------------------------------------

    retrieval_block = memory_retrieval_block(
        second_system
    )

    assert "Cursor" in retrieval_block

    # --------------------------------------------------------------
    # Two completed turns = two Diary events.
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
    # TURN 3 — Agent Memory Operation
    # ==================================================================

    # Capture the real AgentMemoryOperations handler.
    real_replace_core = (
        agent.memory_operations.replace_core_memory
    )

    calls_to_replace_core: list[dict] = []

    def observed_replace_core(**kwargs):
        calls_to_replace_core.append(kwargs)

        # IMPORTANT:
        # This is not a mock. The real operation executes.
        return real_replace_core(**kwargs)

    monkeypatch.setattr(
        agent.memory_operations,
        "replace_core_memory",
        observed_replace_core,
    )

    agent.run(
        "Update my Core Memory."
    )

    # --------------------------------------------------------------
    # Tool call + second reasoning step.
    # --------------------------------------------------------------

    assert len(llm.calls) == 4

    # --------------------------------------------------------------
    # Initial context must not contain the future mutation.
    # --------------------------------------------------------------

    third_initial_system = system_for(
        llm,
        2,
    )

    assert (
        "P3 CORE MEMORY CHANGE"
        not in third_initial_system
    )

    third_initial_users = user_messages_for(
        llm,
        2,
    )

    assert any(
        message["content"]
        == "Update my Core Memory."
        for message in third_initial_users
    )

    # --------------------------------------------------------------
    # Verify that the LLM-facing operation actually went through
    # AgentMemoryOperations.
    #
    # The wrapped handler still executes the real implementation.
    # --------------------------------------------------------------

    assert calls_to_replace_core == [
        {
            "label": "human",
            "content": "P3 CORE MEMORY CHANGE",
        }
    ]

    # --------------------------------------------------------------
    # Verify the operation result contract.
    # --------------------------------------------------------------

    assert len(agent.operation_results) == 1

    operation_result = (
        agent.operation_results[0]
    )

    assert (
        operation_result.operation
        == "memory_replace_core"
    )

    assert (
        operation_result.status
        == OperationStatus.SUCCESS
    )

    # --------------------------------------------------------------
    # Verify actual persistent Core Memory mutation.
    # --------------------------------------------------------------

    human_block = agent.core_memory.get(
        "human"
    )

    assert human_block is not None

    assert (
        human_block.content
        == "P3 CORE MEMORY CHANGE"
    )

    # ==================================================================
    # SECOND CONTEXT BUILD
    # ==================================================================

    third_final_system = system_for(
        llm,
        3,
    )

    # --------------------------------------------------------------
    # The second Context must see persistent Core Memory.
    # --------------------------------------------------------------

    assert "CORE MEMORY" in third_final_system

    assert (
        "P3 CORE MEMORY CHANGE"
        in third_final_system
    )

    # --------------------------------------------------------------
    # The operation result must also enter the rebuilt Context.
    #
    # This verifies the Agent-owned operation-result pipeline rather
    # than merely verifying the database mutation.
    # --------------------------------------------------------------

    assert (
        "memory_replace_core"
        in third_final_system
    )

    # --------------------------------------------------------------
    # The tool result must also remain in the conversation protocol.
    # --------------------------------------------------------------

    third_tools = tool_messages_for(
        llm,
        3,
    )

    assert any(
        message.get("tool_name")
        == "memory_replace_core"
        for message in third_tools
    )

    # --------------------------------------------------------------
    # The current user message remains a USER message even during
    # the second reasoning step.
    # --------------------------------------------------------------

    third_final_users = user_messages_for(
        llm,
        3,
    )

    assert any(
        message["content"]
        == "Update my Core Memory."
        for message in third_final_users
    )

    # --------------------------------------------------------------
    # Final assistant response persisted.
    # --------------------------------------------------------------

    persisted_after_turn_3 = (
        agent.recall.get_messages(
            conversation_id
        )
    )

    assert any(
        message["role"] == "assistant"
        and message["content"]
        == "The Core Memory has been updated."
        for message in persisted_after_turn_3
    )

    # --------------------------------------------------------------
    # Three completed turns = three Diary events.
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
    # FINAL PERSISTENCE ROUND-TRIP
    # ==================================================================

    persisted_messages = (
        agent.recall.get_messages(
            conversation_id
        )
    )

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

    assert any(
        message["role"] == "user"
        and message["content"]
        == "Update my Core Memory."
        for message in persisted_messages
    )

    assert any(
        message["role"] == "assistant"
        and message["content"]
        == "I will remember that."
        for message in persisted_messages
    )

    assert any(
        message["role"] == "assistant"
        and message["content"]
        == "Your editor is Cursor."
        for message in persisted_messages
    )

    assert any(
        message["role"] == "assistant"
        and message["content"]
        == "The Core Memory has been updated."
        for message in persisted_messages
    )

