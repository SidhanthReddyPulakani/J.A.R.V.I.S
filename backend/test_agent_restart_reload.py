
"""
P4 — Agent Restart / Reload Persistence Test.

pytest -s test_agent_restart_reload.py

This test verifies that the complete Jarvis Agent survives process
restart through the persistent SQLite database.

Scenario:

    Agent #1
        ↓
    create state + conversation
    create Core Memory change
    create Long-Term Memory through agent.run()
    create Diary events through agent.run()
        ↓
    DISCARD
        ↓
    Agent #2 — Restart 1
        ↓
    verify State / Core Memory / LTM / Diary / Recall / Context
        ↓
    DISCARD
        ↓
    Agent #3 — Restart 2
        ↓
    verify everything again
        ↓
    DISCARD
        ↓
    Agent #4 — Restart 3
        ↓
    final verification

Only the LLM boundary is stubbed.

The real Agent initialization path, database, repositories, services,
retrieval system, memory formation, diary, and context compiler are used.

The test also prints database-backed snapshots so that persistence can
be visually inspected while the test is running.
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


class RestartStubLLM:
    """
    Minimal deterministic LLM used only for turns performed by Agent #1.

    No real Ollama connection is made.

    Every normal turn receives a deterministic assistant response.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.response_number = 0

    @staticmethod
    def _response(content: str):
        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content=content,
                tool_calls=[],
            )
        )

    def chat(
        self,
        *,
        messages: list,
        tools: list,
    ):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        self.response_number += 1

        return self._response(
            f"Restart persistence test response "
            f"{self.response_number}."
        )


# ======================================================================
# Display helpers
# ======================================================================


WIDTH = 78


def line(char: str = "─") -> None:
    print(char * WIDTH)


def section(title: str) -> None:
    print()
    print("╔" + "═" * (WIDTH - 2) + "╗")
    print(
        "║ "
        + title[: WIDTH - 4]
        .ljust(WIDTH - 4)
        + " ║"
    )
    print("╚" + "═" * (WIDTH - 2) + "╝")


def field(
    name: str,
    value,
    indent: int = 2,
) -> None:
    print(
        " " * indent
        + f"{name:<24}: {value}"
    )


def success(message: str) -> None:
    print(f"  ✓ {message}")


def failure(message: str) -> None:
    print(f"  ✗ {message}")


# ======================================================================
# Database snapshot
# ======================================================================


def fetch_state_snapshot(
    database: Database,
    agent_id: str,
) -> dict:
    """
    Read the persisted Agent State directly from SQLite.
    """

    row = database.fetch_one(
        """
        SELECT
            agent_id,
            conversation_id,
            current_task,
            current_goal,
            mode,
            active_project,
            active_operation,
            operation_status,
            updated_at
        FROM agent_state
        WHERE agent_id = ?
        """,
        (agent_id,),
    )

    assert row is not None

    return {
        "agent_id": row[0],
        "conversation_id": row[1],
        "current_task": row[2],
        "current_goal": row[3],
        "mode": row[4],
        "active_project": row[5],
        "active_operation": row[6],
        "operation_status": row[7],
        "updated_at": row[8],
    }


def fetch_core_memory_snapshot(
    database: Database,
    agent_id: str,
) -> list[dict]:
    """
    Read all persisted Core Memory blocks directly from SQLite.
    """

    rows = database.fetch_all(
        """
        SELECT
            id,
            agent_id,
            label,
            content,
            capacity,
            priority,
            writable,
            created_at,
            updated_at
        FROM core_memory_blocks
        WHERE agent_id = ?
        ORDER BY priority ASC, id ASC
        """,
        (agent_id,),
    )

    return [
        {
            "id": row[0],
            "agent_id": row[1],
            "label": row[2],
            "content": row[3],
            "capacity": row[4],
            "priority": row[5],
            "writable": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
        for row in rows
    ]


def fetch_memory_snapshot(
    database: Database,
    agent_id: str,
) -> list[dict]:
    """
    Read persisted Long-Term Memory directly from SQLite.
    """

    rows = database.fetch_all(
        """
        SELECT
            id,
            agent_id,
            content,
            category,
            subject,
            project,
            importance,
            confidence,
            status,
            superseded_by_id,
            created_at,
            updated_at
        FROM memories
        WHERE agent_id = ?
        ORDER BY id ASC
        """,
        (agent_id,),
    )

    return [
        {
            "id": row[0],
            "agent_id": row[1],
            "content": row[2],
            "category": row[3],
            "subject": row[4],
            "project": row[5],
            "importance": row[6],
            "confidence": row[7],
            "status": row[8],
            "superseded_by_id": row[9],
            "created_at": row[10],
            "updated_at": row[11],
        }
        for row in rows
    ]


def fetch_diary_snapshot(
    database: Database,
    agent_id: str,
) -> list[dict]:
    """
    Read persisted Diary events directly from SQLite.
    """

    rows = database.fetch_all(
        """
        SELECT
            id,
            agent_id,
            conversation_id,
            event_type,
            description,
            source,
            metadata,
            created_at
        FROM diary_events
        WHERE agent_id = ?
        ORDER BY id ASC
        """,
        (agent_id,),
    )

    return [
        {
            "id": row[0],
            "agent_id": row[1],
            "conversation_id": row[2],
            "event_type": row[3],
            "description": row[4],
            "source": row[5],
            "metadata": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def fetch_message_snapshot(
    database: Database,
    conversation_id: int,
) -> list[dict]:
    """
    Read persisted conversation messages directly from SQLite.
    """

    rows = database.fetch_all(
        """
        SELECT
            id,
            conversation_id,
            role,
            content,
            created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,),
    )

    return [
        {
            "id": row[0],
            "conversation_id": row[1],
            "role": row[2],
            "content": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def print_database_snapshot(
    database: Database,
    agent: JarvisAgent,
    label: str,
) -> None:
    """
    Print the actual persisted structures that P4 is testing.
    """

    section(
        f"P4 DATABASE SNAPSHOT — {label}"
    )

    state = fetch_state_snapshot(
        database,
        agent.AGENT_ID,
    )

    core_memory = fetch_core_memory_snapshot(
        database,
        agent.AGENT_ID,
    )

    memories = fetch_memory_snapshot(
        database,
        agent.AGENT_ID,
    )

    diary = fetch_diary_snapshot(
        database,
        agent.AGENT_ID,
    )

    conversation_id = state[
        "conversation_id"
    ]

    messages = fetch_message_snapshot(
        database,
        conversation_id,
    )

    print()
    print("  STATE")
    field(
        "agent_id",
        state["agent_id"],
        indent=4,
    )
    field(
        "conversation_id",
        state["conversation_id"],
        indent=4,
    )
    field(
        "mode",
        state["mode"],
        indent=4,
    )
    field(
        "current_task",
        state["current_task"],
        indent=4,
    )
    field(
        "current_goal",
        state["current_goal"],
        indent=4,
    )
    field(
        "active_project",
        state["active_project"],
        indent=4,
    )
    field(
        "operation_status",
        state["operation_status"],
        indent=4,
    )

    print()
    print(
        f"  CORE MEMORY "
        f"({len(core_memory)} blocks)"
    )

    for block in core_memory:
        print(
            f"    [{block['label']}] "
            f"id={block['id']} "
            f"priority={block['priority']}"
        )

        for content_line in (
            block["content"] or ""
        ).splitlines():

            print(
                f"        {content_line}"
            )

    print()
    print(
        f"  LONG-TERM MEMORY "
        f"({len(memories)} records)"
    )

    for memory in memories:
        print(
            f"    #{memory['id']} "
            f"[{memory['status']}] "
            f"importance={memory['importance']}"
        )
        print(
            f"        {memory['content']}"
        )

    print()
    print(
        f"  DIARY "
        f"({len(diary)} events)"
    )

    for event in diary:
        print(
            f"    #{event['id']} "
            f"[{event['event_type']}]"
        )
        print(
            f"        {event['description']}"
        )

    print()
    print(
        f"  RECALL / MESSAGES "
        f"({len(messages)} records)"
    )

    for message in messages:
        print(
            f"    #{message['id']} "
            f"[{message['role']}]"
        )
        print(
            f"        {message['content']}"
        )

    line()


# ======================================================================
# Test Agent construction
# ======================================================================


def build_isolated_database(
    tmp_path: Path,
) -> Database:
    """
    Create the isolated P4 database.
    """

    return Database(
        tmp_path / "jarvis_p4_restart.db"
    )


def build_agent(
    database: Database,
) -> JarvisAgent:
    """
    Construct a real JarvisAgent against the supplied database.

    JarvisAgent currently imports the application database object
    directly, so the test replaces that module-level reference before
    construction.
    """

    agent_module.database = database

    return JarvisAgent()


# ======================================================================
# Persistence assertions
# ======================================================================


def assert_agent_persistence(
    agent: JarvisAgent,
    database: Database,
    *,
    expected_conversation_id: int,
    expected_core_content: str,
    expected_memory_content: str,
    expected_diary_count: int,
    expected_message_count: int,
) -> None:
    """
    Verify both the Agent's reconstructed state and the underlying
    database state.
    """

    # --------------------------------------------------------------
    # State
    # --------------------------------------------------------------

    assert agent.state.agent_id == (
        agent.AGENT_ID
    )

    assert agent.state.conversation_id == (
        expected_conversation_id
    )

    persisted_state = fetch_state_snapshot(
        database,
        agent.AGENT_ID,
    )

    assert (
        persisted_state["conversation_id"]
        == expected_conversation_id
    )

    # --------------------------------------------------------------
    # Core Memory
    # --------------------------------------------------------------

    blocks = (
        agent.core_memory.list_blocks()
    )

    matching_blocks = [
        block
        for block in blocks
        if expected_core_content
        in (block.content or "")
    ]

    assert matching_blocks, (
        "Expected Core Memory content was not "
        "reconstructed by the new Agent."
    )

    persisted_blocks = (
        fetch_core_memory_snapshot(
            database,
            agent.AGENT_ID,
        )
    )

    assert any(
        expected_core_content
        in (block["content"] or "")
        for block in persisted_blocks
    )

    # --------------------------------------------------------------
    # Long-Term Memory
    # --------------------------------------------------------------

    memories = agent.memory.list()

    assert any(
        expected_memory_content
        in (memory.content or "")
        for memory in memories
    ), (
        "Expected Long-Term Memory was not "
        "reconstructed by the new Agent."
    )

    persisted_memories = (
        fetch_memory_snapshot(
            database,
            agent.AGENT_ID,
        )
    )

    assert any(
        expected_memory_content
        in (memory["content"] or "")
        for memory in persisted_memories
    )

    # --------------------------------------------------------------
    # Diary
    # --------------------------------------------------------------

    diary_events = (
        fetch_diary_snapshot(
            database,
            agent.AGENT_ID,
        )
    )

    assert len(diary_events) == (
        expected_diary_count
    )

    assert all(
        event["conversation_id"]
        == expected_conversation_id
        for event in diary_events
    )

    # --------------------------------------------------------------
    # Recall / conversation reconstruction
    # --------------------------------------------------------------

    messages = fetch_message_snapshot(
        database,
        expected_conversation_id,
    )

    assert len(messages) == (
        expected_message_count
    )

    assert len(agent.messages) == (
        expected_message_count
    )

    # --------------------------------------------------------------
    # First post-restart context
    # --------------------------------------------------------------

    context = agent._build_context()

    system_message = context.as_messages()[0]

    assert (
        system_message["role"]
        == "system"
    )

    system_content = (
        system_message["content"]
    )

    assert expected_core_content in (
        system_content
    )

    assert expected_memory_content in (
        system_content
    )

    assert "DIARY" in system_content

    # The persisted conversation should also be
    # represented by the new Agent.
    assert any(
        message.get("content")
        == messages[0]["content"]
        for message in agent.messages
    )


# ======================================================================
# P4 — Restart / Reload
# ======================================================================


def test_agent_survives_three_restarts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Verify complete Agent persistence across three restarts.

    The same SQLite database is used for all four Agent instances.
    """

    database = build_isolated_database(
        tmp_path
    )

    monkeypatch.setattr(
        agent_module,
        "database",
        database,
    )

    database.initialize()

    # ==================================================================
    # AGENT #1 — INITIAL SESSION
    # ==================================================================

    section(
        "P4 — AGENT #1 / INITIAL SESSION"
    )

    agent1 = JarvisAgent()

    conversation_id = (
        agent1.state.conversation_id
    )

    assert conversation_id is not None

    # --------------------------------------------------------------
    # Establish a meaningful Agent State.
    # --------------------------------------------------------------

    agent1.state.current_task = (
        "P4 restart persistence"
    )

    agent1.state.current_goal = (
        "Verify the complete Agent state "
        "survives repeated restarts."
    )

    agent1.state.mode = "testing"

    agent1.state.active_project = (
        "Jarvis"
    )

    agent1._persist_state()

    # --------------------------------------------------------------
    # Establish a Core Memory change.
    #
    # Use the real Core Memory service so the test verifies
    # persistence through the normal service/repository boundary.
    # --------------------------------------------------------------

    core_content = (
        "P4 persistent Core Memory: "
        "Jarvis restart testing is active."
    )

    human_block = next(
        (
            block
            for block
            in agent1.core_memory.list_blocks()
            if block.label == "human"
        ),
        None,
    )

    assert human_block is not None

    agent1.core_memory.replace(
        "human",
        core_content,
    )

    # --------------------------------------------------------------
    # Turn 1 — establishes Long-Term Memory and Diary.
    # --------------------------------------------------------------

    memorable_fact = (
        "Remember that my primary development "
        "environment for this persistence test "
        "is Windows."
    )

    agent1.llm = RestartStubLLM()

    agent1.run(
        memorable_fact
    )

    # --------------------------------------------------------------
    # Turn 2 — produces another Diary event and Recall message.
    # --------------------------------------------------------------

    agent1.run(
        "This is the second turn before "
        "the first restart."
    )

    expected_memory_content = (
        "Windows"
    )

    memories = agent1.memory.list()

    assert any(
        expected_memory_content
        in (memory.content or "")
        for memory in memories
    ), (
        "Initial Agent failed to form the expected "
        "Long-Term Memory."
    )

    expected_diary_count = 2
    expected_message_count = 4

    print_database_snapshot(
        database,
        agent1,
        "BEFORE RESTART 1",
    )

    # Save exact persisted structures that future
    # Agents must reproduce.
    state_before_restart = (
        fetch_state_snapshot(
            database,
            agent1.AGENT_ID,
        )
    )

    core_before_restart = (
        fetch_core_memory_snapshot(
            database,
            agent1.AGENT_ID,
        )
    )

    memories_before_restart = (
        fetch_memory_snapshot(
            database,
            agent1.AGENT_ID,
        )
    )

    diary_before_restart = (
        fetch_diary_snapshot(
            database,
            agent1.AGENT_ID,
        )
    )

    messages_before_restart = (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
    )

    # --------------------------------------------------------------
    # Restart 1
    # --------------------------------------------------------------

    del agent1

    print()
    print(
        "  ↓ DISCARDING AGENT #1"
    )
    print(
        "  ↓ RECONSTRUCTING AGENT #2"
    )

    agent2 = JarvisAgent()

    print_database_snapshot(
        database,
        agent2,
        "AFTER RESTART 1 / AGENT #2",
    )

    # --------------------------------------------------------------
    # Compare persisted structures exactly.
    # --------------------------------------------------------------

    assert (
        fetch_state_snapshot(
            database,
            agent2.AGENT_ID,
        )
        == state_before_restart
    )

    assert (
        fetch_core_memory_snapshot(
            database,
            agent2.AGENT_ID,
        )
        == core_before_restart
    )

    assert (
        fetch_memory_snapshot(
            database,
            agent2.AGENT_ID,
        )
        == memories_before_restart
    )

    assert (
        fetch_diary_snapshot(
            database,
            agent2.AGENT_ID,
        )
        == diary_before_restart
    )

    assert (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
        == messages_before_restart
    )

    assert_agent_persistence(
        agent2,
        database,
        expected_conversation_id=conversation_id,
        expected_core_content=core_content,
        expected_memory_content=expected_memory_content,
        expected_diary_count=expected_diary_count,
        expected_message_count=expected_message_count,
    )

    success(
        "Restart 1 retained State, Core Memory, "
        "Long-Term Memory, Diary, Recall, and Context."
    )

    # --------------------------------------------------------------
    # Add another persisted Diary event through Agent #2.
    # --------------------------------------------------------------

    agent2.llm = RestartStubLLM()

    agent2.run(
        "Add another persistence checkpoint."
    )

    expected_diary_count = 3
    expected_message_count = 6

    print_database_snapshot(
        database,
        agent2,
        "BEFORE RESTART 2",
    )

    state_before_restart = (
        fetch_state_snapshot(
            database,
            agent2.AGENT_ID,
        )
    )

    core_before_restart = (
        fetch_core_memory_snapshot(
            database,
            agent2.AGENT_ID,
        )
    )

    memories_before_restart = (
        fetch_memory_snapshot(
            database,
            agent2.AGENT_ID,
        )
    )

    diary_before_restart = (
        fetch_diary_snapshot(
            database,
            agent2.AGENT_ID,
        )
    )

    messages_before_restart = (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
    )

    # ==================================================================
    # RESTART 2
    # ==================================================================

    del agent2

    print()
    print(
        "  ↓ DISCARDING AGENT #2"
    )
    print(
        "  ↓ RECONSTRUCTING AGENT #3"
    )

    agent3 = JarvisAgent()

    print_database_snapshot(
        database,
        agent3,
        "AFTER RESTART 2 / AGENT #3",
    )

    assert (
        fetch_state_snapshot(
            database,
            agent3.AGENT_ID,
        )
        == state_before_restart
    )

    assert (
        fetch_core_memory_snapshot(
            database,
            agent3.AGENT_ID,
        )
        == core_before_restart
    )

    assert (
        fetch_memory_snapshot(
            database,
            agent3.AGENT_ID,
        )
        == memories_before_restart
    )

    assert (
        fetch_diary_snapshot(
            database,
            agent3.AGENT_ID,
        )
        == diary_before_restart
    )

    assert (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
        == messages_before_restart
    )

    assert_agent_persistence(
        agent3,
        database,
        expected_conversation_id=conversation_id,
        expected_core_content=core_content,
        expected_memory_content=expected_memory_content,
        expected_diary_count=expected_diary_count,
        expected_message_count=expected_message_count,
    )

    success(
        "Restart 2 retained all previously persisted Agent state."
    )

    # --------------------------------------------------------------
    # Add another Diary event through Agent #3.
    # --------------------------------------------------------------

    agent3.llm = RestartStubLLM()

    agent3.run(
        "Add the final persistence checkpoint."
    )

    expected_diary_count = 4
    expected_message_count = 8

    print_database_snapshot(
        database,
        agent3,
        "BEFORE RESTART 3",
    )

    state_before_restart = (
        fetch_state_snapshot(
            database,
            agent3.AGENT_ID,
        )
    )

    core_before_restart = (
        fetch_core_memory_snapshot(
            database,
            agent3.AGENT_ID,
        )
    )

    memories_before_restart = (
        fetch_memory_snapshot(
            database,
            agent3.AGENT_ID,
        )
    )

    diary_before_restart = (
        fetch_diary_snapshot(
            database,
            agent3.AGENT_ID,
        )
    )

    messages_before_restart = (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
    )

    # ==================================================================
    # RESTART 3
    # ==================================================================

    del agent3

    print()
    print(
        "  ↓ DISCARDING AGENT #3"
    )
    print(
        "  ↓ RECONSTRUCTING AGENT #4"
    )

    agent4 = JarvisAgent()

    print_database_snapshot(
        database,
        agent4,
        "AFTER RESTART 3 / AGENT #4",
    )

    # --------------------------------------------------------------
    # Final exact persistence comparison.
    # --------------------------------------------------------------

    assert (
        fetch_state_snapshot(
            database,
            agent4.AGENT_ID,
        )
        == state_before_restart
    )

    assert (
        fetch_core_memory_snapshot(
            database,
            agent4.AGENT_ID,
        )
        == core_before_restart
    )

    assert (
        fetch_memory_snapshot(
            database,
            agent4.AGENT_ID,
        )
        == memories_before_restart
    )

    assert (
        fetch_diary_snapshot(
            database,
            agent4.AGENT_ID,
        )
        == diary_before_restart
    )

    assert (
        fetch_message_snapshot(
            database,
            conversation_id,
        )
        == messages_before_restart
    )

    # --------------------------------------------------------------
    # Final Agent-level verification.
    # --------------------------------------------------------------

    assert_agent_persistence(
        agent4,
        database,
        expected_conversation_id=conversation_id,
        expected_core_content=core_content,
        expected_memory_content=expected_memory_content,
        expected_diary_count=expected_diary_count,
        expected_message_count=expected_message_count,
    )

    # --------------------------------------------------------------
    # Final visual snapshot.
    # --------------------------------------------------------------

    print_database_snapshot(
        database,
        agent4,
        "FINAL — AFTER THREE RESTARTS",
    )

    section(
        "P4 — THREE RESTARTS PASSED"
    )

    success(
        "State retained."
    )

    success(
        "Core Memory retained."
    )

    success(
        "Long-Term Memory retained."
    )

    success(
        "Diary retained."
    )

    success(
        "Recall / conversation retained."
    )

    success(
        "First post-restart Context reconstructed persisted information."
    )

    print()
    print(
        "  ✓ P4 AGENT RESTART / RELOAD TEST PASSED"
    )

