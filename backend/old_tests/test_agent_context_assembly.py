"""
R2.10C.3 + R2.10C.4

Agent-level tests for:

- State -> ContextRequest
- Core Memory -> ContextRequest
- Conversation -> ContextRequest
- Recall-restored conversation representation -> Context

These tests deliberately exercise JarvisAgent._build_context()
without invoking the real LLM, database, or tool execution path.

The purpose is to verify the Agent assembly boundary itself.
"""

from __future__ import annotations

from types import SimpleNamespace

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.core.agent import (
    JarvisAgent,
)
from jarvis.state.models import (
    AgentState,
)


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
""".strip()


class FakeCoreMemory:
    """Minimal Core Memory service for Agent assembly testing."""

    def __init__(self) -> None:
        self.blocks = [
            SimpleNamespace(
                label="human",
                content=(
                    "Name: Sidhanth\n"
                    "Editor: Cursor"
                ),
                capacity=2000,
                priority=10,
                writable=True,
            ),
            SimpleNamespace(
                label="persona",
                content=(
                    "Jarvis is a local desktop assistant."
                ),
                capacity=2000,
                priority=10,
                writable=True,
            ),
        ]

    def list_blocks(self):
        return list(self.blocks)


class FakeRetrieval:
    """
    Retrieval is deliberately empty here.

    C.3/C.4 are testing the direct State,
    Core Memory, and conversation assembly
    boundaries, not Retrieval.
    """

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ):
        return []


class FakeDiary:
    """Minimal Diary service for context assembly testing."""

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ):
        return []

    def recent(
        self,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ):
        return []


def build_agent_for_context_test() -> JarvisAgent:
    """
    Construct only the Agent pieces required by _build_context().

    We intentionally bypass JarvisAgent.__init__ so the test does not
    initialize the production database, LLM client, or tool system.
    """

    agent = object.__new__(JarvisAgent)

    agent.state = AgentState(
        agent_id="context-assembly-test",
        conversation_id=42,
        current_task="Testing Agent Context",
        current_goal=(
            "Verify State, Core Memory, and "
            "conversation reach Context."
        ),
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )

    agent.core_memory = FakeCoreMemory()
    agent.retrieval = FakeRetrieval()
    agent.diary = FakeDiary()

    agent.context_compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    agent.context_window = ContextWindowManager()

    agent.messages = [
        {
            "role": "user",
            "content": "What are we testing?",
        },
        {
            "role": "assistant",
            "content": (
                "We are testing the Agent Context "
                "assembly boundary."
            ),
        },
    ]

    return agent


def test_state_and_core_memory_reach_context() -> None:
    """
    C.3

    State and Core Memory owned by the Agent must be
    passed into Context and become visible in the
    compiled system context.
    """

    agent = build_agent_for_context_test()

    context = agent._build_context(
        user_input="What are we testing?"
    )

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    # --------------------------------------------------
    # State
    # --------------------------------------------------

    assert (
        "CURRENT AGENT STATE"
        in system_content
    )

    assert (
        "Agent ID: context-assembly-test"
        in system_content
    )

    assert (
        "Current task: Testing Agent Context"
        in system_content
    )

    assert (
        "Current goal: Verify State, Core Memory, "
        "and conversation reach Context."
        in system_content
    )

    # --------------------------------------------------
    # Core Memory
    # --------------------------------------------------

    assert (
        "CORE MEMORY"
        in system_content
    )

    assert (
        "Name: Sidhanth"
        in system_content
    )

    assert (
        "Editor: Cursor"
        in system_content
    )

    assert (
        "Jarvis is a local desktop assistant."
        in system_content
    )


def test_conversation_reaches_context() -> None:
    """
    C.4

    The Agent's current conversation representation
    must become the conversation portion of the compiled
    Context.
    """

    agent = build_agent_for_context_test()

    context = agent._build_context(
        user_input="What are we testing?"
    )

    messages = context.as_messages()

    assert len(messages) == 3

    # --------------------------------------------------
    # System context
    # --------------------------------------------------

    assert (
        messages[0]["role"]
        == "system"
    )

    # --------------------------------------------------
    # Restored/current conversation
    # --------------------------------------------------

    assert (
        messages[1]["role"]
        == "user"
    )

    assert (
        messages[1]["content"]
        == "What are we testing?"
    )

    assert (
        messages[2]["role"]
        == "assistant"
    )

    assert (
        messages[2]["content"]
        == (
            "We are testing the Agent Context "
            "assembly boundary."
        )
    )


def test_context_assembly_is_deterministic() -> None:
    """
    C.3 + C.4

    Identical Agent state, Core Memory, and conversation
    must produce identical compiled context.
    """

    agent = build_agent_for_context_test()

    first = agent._build_context(
        user_input="What are we testing?"
    )

    second = agent._build_context(
        user_input="What are we testing?"
    )

    assert (
        first.as_messages()
        == second.as_messages()
    )


def main() -> None:
    test_state_and_core_memory_reach_context()
    test_conversation_reaches_context()
    test_context_assembly_is_deterministic()

    print(
        "PASS: State -> Agent Context assembly."
    )

    print(
        "PASS: Core Memory -> Agent Context assembly."
    )

    print(
        "PASS: Conversation -> Agent Context assembly."
    )

    print(
        "PASS: Agent context assembly is deterministic."
    )


if __name__ == "__main__":
    main()