from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)

from jarvis.memory import (
    CoreMemoryService,
)

from jarvis.state.models import (
    AgentState,
)

from jarvis.storage.database import (
    Database,
)

from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
""".strip()


def main() -> None:

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "core_memory_context.db"
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
                "test-jarvis",
                "testing",
                "idle",
                "2026-08-27T00:00:00+00:00",
            ),
        )

        repository = CoreMemoryRepository(
            database
        )

        memory = CoreMemoryService(
            repository,
            agent_id="test-jarvis",
        )

        memory.create_block(
            label="human",
            content="Name: Sidhanth",
            capacity=2000,
            priority=10,
            writable=True,
        )

        state = AgentState(
            agent_id="test-jarvis",
            conversation_id=42,
            current_task="Testing context",
            current_goal="Verify Core Memory injection",
            mode="testing",
            active_project="Jarvis",
            active_operation=None,
            operation_status="idle",
        )

        compiler = ContextCompiler(
            SYSTEM_PROMPT
        )

        # --------------------------------------------------
        # First compilation.
        # --------------------------------------------------

        core_memory = (
            memory.list_blocks()
        )

        request = ContextRequest(
            user_input="Who am I?",
            state=state,
            conversation=[
                {
                    "role": "user",
                    "content": "Who am I?",
                }
            ],
            core_memory=core_memory,
        )

        context = compiler.compile(
            request
        )

        messages = context.as_messages()

        assert len(messages) == 2

        system_content = (
            messages[0]["content"]
        )

        assert "CORE MEMORY" in system_content
        assert "Name: Sidhanth" in system_content
        assert "CURRENT AGENT STATE" in system_content
        assert "Testing context" in system_content

        # --------------------------------------------------
        # Modify persistent memory.
        # --------------------------------------------------

        memory.replace(
            "human",
            "Name: Sidhanth\n"
            "Editor: Cursor",
        )

        # --------------------------------------------------
        # Rebuild context.
        # --------------------------------------------------

        refreshed_memory = (
            memory.list_blocks()
        )

        refreshed_request = ContextRequest(
            user_input="Who am I?",
            state=state,
            conversation=[
                {
                    "role": "user",
                    "content": "Who am I?",
                }
            ],
            core_memory=refreshed_memory,
        )

        refreshed_context = compiler.compile(
            refreshed_request
        )

        refreshed_messages = (
            refreshed_context.as_messages()
        )

        refreshed_system = (
            refreshed_messages[0]["content"]
        )

        assert "Editor: Cursor" in refreshed_system

        # Old content must not contain stale
        # information that was replaced.
        assert (
            "Name: Sidhanth\n"
            "Editor: Cursor"
            in refreshed_system
        )

        print(
            "COMPILED CORE MEMORY CONTEXT:"
        )

        print()

        print(
            refreshed_system
        )

        print()

        print(
            "PASS: Core Memory is injected "
            "into Context."
        )

        print(
            "PASS: Context reflects updated "
            "persistent Core Memory."
        )


if __name__ == "__main__":
    main()