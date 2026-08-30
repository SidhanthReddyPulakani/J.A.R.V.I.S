"""
R2.10B State + Core Memory context integration tests.

These tests verify that:

- Agent State reaches the Context Compiler.
- Core Memory reaches the Context Compiler.
- Core Memory remains Agent-scoped.
- The compiled system context contains both sources.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.memory import (
    CoreMemoryService,
)
from jarvis.state.models import AgentState
from jarvis.storage.database import Database
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)


SYSTEM_PROMPT = (
    "You are Jarvis."
)


def build_state(
    agent_id: str,
) -> AgentState:
    """
    Build deterministic Agent State for testing.
    """

    return AgentState(
        agent_id=agent_id,
        conversation_id=42,
        current_task="R2.10 context integration",
        current_goal="Integrate State and Core Memory",
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def test_state_reaches_context() -> None:
    """
    Agent State must be represented in compiled context.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    state = build_state(
        "agent-state-test"
    )

    request = ContextRequest(
        user_input="test",
        state=state,
    )

    context = compiler.compile(
        request
    )

    messages = context.as_messages()

    assert messages

    system_message = messages[0]

    assert system_message["role"] == "system"

    content = system_message["content"]

    assert "CURRENT AGENT STATE" in content
    assert "Agent ID: agent-state-test" in content
    assert "Current task: R2.10 context integration" in content
    assert "Current goal: Integrate State and Core Memory" in content
    assert "Active project: Jarvis" in content


def test_core_memory_reaches_context() -> None:
    """
    Core Memory blocks must be represented in compiled context.
    """

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "context_core_memory.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        # Core Memory belongs to an Agent State.
        database.execute(
            """
            INSERT INTO agent_state (
                agent_id,
                mode,
                operation_status,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "agent-memory-test",
                "testing",
                "idle",
                "2026-08-29T00:00:00+00:00",
            ),
        )

        service = CoreMemoryService(
            CoreMemoryRepository(
                database
            ),
            agent_id="agent-memory-test",
        )

        service.create_block(
            label="human",
            content="Preferred editor: Cursor",
            capacity=2000,
            priority=10,
            writable=True,
        )

        blocks = service.list_blocks()

        compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        request = ContextRequest(
            user_input="test",
            state=build_state(
                "agent-memory-test"
            ),
            core_memory=blocks,
        )

        context = compiler.compile(
            request
        )

        messages = context.as_messages()

        assert messages

        system_message = messages[0]

        content = system_message["content"]

        assert "CORE MEMORY" in content
        assert "[human]" in content
        assert "Preferred editor: Cursor" in content


def test_core_memory_is_agent_scoped_in_context() -> None:
    """
    Core Memory belonging to another Agent must not enter
    the current Agent's Context.
    """

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "context_isolation.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        database.execute(
            """
            INSERT INTO agent_state (
                agent_id,
                mode,
                operation_status,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "agent-a",
                "testing",
                "idle",
                "2026-08-29T00:00:00+00:00",
            ),
        )

        database.execute(
            """
            INSERT INTO agent_state (
                agent_id,
                mode,
                operation_status,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "agent-b",
                "testing",
                "idle",
                "2026-08-29T00:00:00+00:00",
            ),
        )

        repository = CoreMemoryRepository(
            database
        )

        agent_a_memory = CoreMemoryService(
            repository,
            agent_id="agent-a",
        )

        agent_b_memory = CoreMemoryService(
            repository,
            agent_id="agent-b",
        )

        agent_a_memory.create_block(
            label="human",
            content="Only Agent A should see this.",
            capacity=2000,
            priority=10,
            writable=True,
        )

        agent_b_memory.create_block(
            label="human",
            content="Only Agent B should see this.",
            capacity=2000,
            priority=10,
            writable=True,
        )

        compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        agent_a_context = compiler.compile(
            ContextRequest(
                user_input="test",
                state=build_state("agent-a"),
                core_memory=agent_a_memory.list_blocks(),
            )
        )

        agent_b_context = compiler.compile(
            ContextRequest(
                user_input="test",
                state=build_state("agent-b"),
                core_memory=agent_b_memory.list_blocks(),
            )
        )

        agent_a_content = (
            agent_a_context
            .as_messages()[0]["content"]
        )

        agent_b_content = (
            agent_b_context
            .as_messages()[0]["content"]
        )

        assert (
            "Only Agent A should see this."
            in agent_a_content
        )

        assert (
            "Only Agent B should see this."
            not in agent_a_content
        )

        assert (
            "Only Agent B should see this."
            in agent_b_content
        )

        assert (
            "Only Agent A should see this."
            not in agent_b_content
        )


def main() -> None:
    test_state_reaches_context()
    test_core_memory_reaches_context()
    test_core_memory_is_agent_scoped_in_context()

    print(
        "R2.10B.1 + R2.10B.2 "
        "State/Core Memory context tests passed."
    )


if __name__ == "__main__":
    main()