from __future__ import annotations

from types import SimpleNamespace

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.core.agent import JarvisAgent
from jarvis.state import AgentState


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Your priorities:
1. Be concise and conversational.
2. Use tools when the user's request requires a desktop action.
3. Never claim an action was completed unless the tool result confirms it.
4. Do not explain your internal reasoning.
5. For simple commands, respond briefly.
""".strip()


# ======================================================================
# Test doubles
# ======================================================================


class RecordingLLM:
    """
    Records the exact context supplied by JarvisAgent.run().
    """

    def __init__(self):
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append(
            {
                "messages": list(messages),
                "kwargs": dict(kwargs),
            }
        )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Test response.",
                tool_calls=[],
            )
        )


class EmptyRetrieval:
    """
    Retrieval is outside the scope of this test.

    Returning no results isolates the Context Window integration.
    """

    def search(self, query, *, limit=10):
        return []


class EmptyDiary:
    """
    Diary is outside the scope of this test.

    Both read and write paths used by run() are stubbed.
    """

    def __init__(self):
        self.recorded_events = []

    def search(
        self,
        query,
        *,
        conversation_id=None,
        limit=10,
    ):
        return []

    def recent(
        self,
        *,
        conversation_id=None,
        limit=10,
    ):
        return []

    def record(
        self,
        *,
        event_type,
        description,
        conversation_id=None,
        source=None,
    ):
        self.recorded_events.append(
            {
                "event_type": event_type,
                "description": description,
                "conversation_id": conversation_id,
                "source": source,
            }
        )


class EmptyCoreMemory:
    """
    Core Memory is not under test here.
    """

    def list_blocks(self):
        return []


class EmptyMemoryExtractor:
    """
    Long-Term Memory formation is not under test here.
    """

    def extract(self, *, text, source):
        return []


class EmptyMemoryFormation:
    """
    No memory candidates are produced by this test.
    """

    def form(self, candidate):
        return None


class RecordingRecall:
    """
    Recall persistence stub.

    run() writes the user and assistant messages to Recall.
    """

    def __init__(self):
        self.added_messages = []

    def add_message(
        self,
        conversation_id,
        role,
        content,
    ):
        self.added_messages.append(
            {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            }
        )


class RecordingStateRepository:
    """
    State persistence stub used by _persist_state().
    """

    def __init__(self):
        self.saved_states = []

    def save(self, state):
        self.saved_states.append(state)


# ======================================================================
# Agent construction
# ======================================================================


def make_agent() -> JarvisAgent:
    """
    Build a lightweight JarvisAgent test instance.

    __init__ is intentionally bypassed so that this test does not
    initialize the real database, Ollama, or other production
    infrastructure.

    The real JarvisAgent.run(), _build_context(), ContextCompiler,
    and ContextWindowManager are still exercised.
    """

    agent = object.__new__(JarvisAgent)

    # --------------------------------------------------
    # Basic runtime state
    # --------------------------------------------------

    agent.enabled = True

    agent.state = AgentState(
        agent_id="p5-agent-integration-test",
        conversation_id=42,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )

    # --------------------------------------------------
    # Persistence dependencies
    # --------------------------------------------------

    agent.recall = RecordingRecall()
    agent.state_repository = RecordingStateRepository()

    # --------------------------------------------------
    # Context information sources
    # --------------------------------------------------

    agent.core_memory = EmptyCoreMemory()
    agent.retrieval = EmptyRetrieval()
    agent.diary = EmptyDiary()

    # --------------------------------------------------
    # Long-Term Memory formation
    # --------------------------------------------------

    agent.memory_extractor = EmptyMemoryExtractor()
    agent.memory_formation = EmptyMemoryFormation()

    # --------------------------------------------------
    # Context pipeline
    # --------------------------------------------------

    agent.context_compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    agent.context_window = ContextWindowManager(
        context_budget=500
    )

    # --------------------------------------------------
    # Runtime conversation
    # --------------------------------------------------

    agent.messages = []
    agent.operation_results = []

    # --------------------------------------------------
    # LLM
    # --------------------------------------------------

    agent.llm = RecordingLLM()

    return agent


# ======================================================================
# P5 Agent Integration
# ======================================================================


def test_agent_run_sends_prepared_context_to_llm():
    """
    Verify that the real JarvisAgent.run() path uses the Context
    Window Manager before sending context to the LLM.

    The conversation deliberately exceeds the configured token
    budget. The LLM must therefore receive the prepared context,
    not the raw unbounded conversation.
    """

    agent = make_agent()

    old_message = (
        "OLD CONTEXT MESSAGE "
        * 200
    )

    middle_message = (
        "MIDDLE CONTEXT MESSAGE "
        * 200
    )

    newest_message = (
        "NEWEST CONTEXT MESSAGE"
    )

    agent.messages = [
        {
            "role": "system",
            "content": "System",
        },
        {
            "role": "user",
            "content": old_message,
        },
        {
            "role": "assistant",
            "content": middle_message,
        },
        {
            "role": "user",
            "content": newest_message,
        },
    ]

    agent.run(
        "What do you remember?"
    )

    assert len(agent.llm.calls) == 1

    sent_messages = (
        agent.llm.calls[0]["messages"]
    )

    contents = [
        message.get(
            "content",
            "",
        )
        for message in sent_messages
    ]

    # System context survives.
    assert sent_messages[0]["role"] == "system"
    assert SYSTEM_PROMPT in sent_messages[0]["content"]
    # Newest conversation content survives.
    assert newest_message in contents

    # Old oversized messages were evicted from the active
    # context before reaching the LLM.
    assert not any(
        old_message in content
        for content in contents
    )

    assert not any(
        middle_message in content
        for content in contents
    )


def test_agent_run_uses_token_aware_eviction():
    """
    Verify that Agent.run() is using token-aware eviction rather
    than a fixed maximum-message count.

    There are only four pre-existing messages, so a message-count
    limit would not explain eviction. The large historical message
    must be removed because of token pressure.
    """

    agent = make_agent()

    huge_old_message = (
        "HISTORICAL TOKEN PRESSURE MESSAGE "
        * 500
    )

    recent_response = (
        "Recent response."
    )

    recent_question = (
        "Recent question."
    )

    agent.messages = [
        {
            "role": "system",
            "content": "System",
        },
        {
            "role": "user",
            "content": huge_old_message,
        },
        {
            "role": "assistant",
            "content": recent_response,
        },
        {
            "role": "user",
            "content": recent_question,
        },
    ]

    agent.run(
        "Continue."
    )

    assert len(agent.llm.calls) == 1

    sent_messages = (
        agent.llm.calls[0]["messages"]
    )

    contents = [
        message.get(
            "content",
            "",
        )
        for message in sent_messages
    ]
    assert sent_messages[0]["role"] == "system"
    assert SYSTEM_PROMPT in sent_messages[0]["content"]
    assert recent_response in contents
    assert recent_question in contents

    assert not any(
        huge_old_message in content
        for content in contents
    )


def test_agent_run_does_not_delete_evicted_runtime_messages():
    """
    Verify the safety boundary between the active model context
    and the Agent's underlying conversation.

    Context Window eviction may remove a message from the context
    sent to the LLM, but it must not destructively remove that
    message from agent.messages.
    """

    agent = make_agent()

    historical_message = (
        "This historical message should be evicted "
        "from the active model context."
    )

    agent.messages = [
        {
            "role": "system",
            "content": "System",
        },
        {
            "role": "user",
            "content": historical_message,
        },
        {
            "role": "assistant",
            "content": "A" * 3000,
        },
        {
            "role": "user",
            "content": "Newest message.",
        },
    ]

    original_messages = [
        dict(message)
        for message in agent.messages
    ]

    agent.run(
        "Continue."
    )

    # --------------------------------------------------
    # Active context sent to LLM
    # --------------------------------------------------

    assert len(agent.llm.calls) == 1

    sent_messages = (
        agent.llm.calls[0]["messages"]
    )

    sent_contents = [
        message.get(
            "content",
            "",
        )
        for message in sent_messages
    ]

    assert not any(
        historical_message in content
        for content in sent_contents
    )

    # --------------------------------------------------
    # Underlying runtime conversation
    # --------------------------------------------------

    # run() legitimately appends the current user message
    # and assistant response, so only compare the original
    # prefix that existed before run().
    assert (
        agent.messages[
            :len(original_messages)
        ]
        == original_messages
    )

    assert any(
        message.get("content")
        == historical_message
        for message in agent.messages
    )