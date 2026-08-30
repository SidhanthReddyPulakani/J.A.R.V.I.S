"""
R2.10C.5 + R2.10C.6

Agent-level verification of:

    Unified Retrieval -> Context
    Diary -> Context

These tests verify the Agent assembly boundary without
calling the real LLM or touching the production database.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.core.agent import JarvisAgent
from jarvis.state.models import AgentState
from jarvis.retrieval import RetrievalResult


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
""".strip()


@dataclass
class FakeDiaryEvent:
    event_type: str
    description: str
    conversation_id: int | None = None


class FakeRetrieval:
    """Deterministic unified Retrieval test double."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RetrievalResult]:

        self.queries.append(query)

        return [
            RetrievalResult(
                source="memory",
                identifier=101,
                content=(
                    "Jarvis uses a modular "
                    "State and Knowledge architecture."
                ),
                score=0.95,
                metadata={
                    "category": "project",
                    "project": "Jarvis",
                },
            ),
            RetrievalResult(
                source="knowledge",
                identifier=202,
                content=(
                    "Context is the temporary "
                    "reasoning input for the LLM."
                ),
                score=0.88,
                metadata={
                    "document_title": (
                        "Jarvis Architecture"
                    ),
                },
            ),
            RetrievalResult(
                source="relationship",
                identifier=303,
                content=(
                    "Jarvis → uses → modular architecture"
                ),
                score=0.76,
                metadata={},
            ),
        ]


class FakeDiary:
    """Deterministic Diary test double."""

    def __init__(self) -> None:
        self.search_queries: list[str] = []
        self.recent_calls: list[int | None] = []

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ) -> list[FakeDiaryEvent]:

        self.search_queries.append(query)

        return [
            FakeDiaryEvent(
                event_type="development",
                description=(
                    "Completed Context integration "
                    "work for Jarvis."
                ),
                conversation_id=conversation_id,
            )
        ]

    def recent(
        self,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ) -> list[FakeDiaryEvent]:

        self.recent_calls.append(
            conversation_id
        )

        return [
            FakeDiaryEvent(
                event_type="development",
                description=(
                    "Recent Jarvis development activity."
                ),
                conversation_id=conversation_id,
            )
        ]


class FakeCoreMemory:
    """Minimal Core Memory surface."""

    def list_blocks(self):
        return []


def build_agent() -> JarvisAgent:
    """
    Build only the Agent components required for
    _build_context().
    """

    agent = object.__new__(JarvisAgent)

    agent.state = AgentState(
        agent_id="retrieval-diary-test",
        conversation_id=42,
        current_task="Testing Retrieval and Diary",
        current_goal=(
            "Verify Retrieval and Diary reach Context."
        ),
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )

    agent.messages = [
        {
            "role": "user",
            "content": (
                "Tell me about Jarvis architecture."
            ),
        }
    ]

    agent.core_memory = FakeCoreMemory()

    agent.retrieval = FakeRetrieval()

    agent.diary = FakeDiary()

    agent.context_compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    agent.context_window = ContextWindowManager()

    return agent


def test_unified_retrieval_reaches_context() -> None:
    """
    C.5

    Agent retrieval results must reach the compiled
    Context without the Context layer accessing the
    underlying information stores.
    """

    agent = build_agent()

    context = agent._build_context(
        user_input="Tell me about Jarvis architecture."
    )

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    # --------------------------------------------------
    # Retrieval actually received the user query
    # --------------------------------------------------

    assert agent.retrieval.queries == [
        "Tell me about Jarvis architecture."
    ]

    # --------------------------------------------------
    # Retrieved Memory
    # --------------------------------------------------

    assert (
        "Jarvis uses a modular State and Knowledge architecture."
        in system_content
    )

    # --------------------------------------------------
    # Retrieved Knowledge
    # --------------------------------------------------

    assert (
        "Context is the temporary reasoning input"
        in system_content
    )

    # --------------------------------------------------
    # Retrieved Relationship
    # --------------------------------------------------

    assert (
        "Jarvis → uses → modular architecture"
        in system_content
    )

    # --------------------------------------------------
    # Retrieval metadata survives compilation
    # --------------------------------------------------

    assert (
        "[memory] id=101 score=0.950"
        in system_content
    )

    assert (
        "[knowledge] id=202 score=0.880"
        in system_content
    )

    assert (
        "[relationship] id=303 score=0.760"
        in system_content
    )


def test_diary_search_reaches_context() -> None:
    """
    C.6

    A non-empty user query should cause the Agent
    to search Diary and pass the resulting events
    into Context.
    """

    agent = build_agent()

    context = agent._build_context(
        user_input="What happened with Jarvis?"
    )

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    # --------------------------------------------------
    # Diary search received the query
    # --------------------------------------------------

    assert agent.diary.search_queries == [
        "What happened with Jarvis?"
    ]

    # --------------------------------------------------
    # Diary content reaches Context
    # --------------------------------------------------

    assert (
        "Completed Context integration work for Jarvis."
        in system_content
    )


def test_empty_input_uses_recent_diary() -> None:
    """
    C.6

    When there is no current query, the Agent should
    use recent Diary events rather than performing an
    empty lexical search.
    """

    agent = build_agent()

    context = agent._build_context()

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    # --------------------------------------------------
    # No retrieval query should be issued
    # --------------------------------------------------

    assert agent.retrieval.queries == []

    # --------------------------------------------------
    # Recent Diary path should be used
    # --------------------------------------------------

    assert agent.diary.search_queries == []

    assert agent.diary.recent_calls == [42]

    # --------------------------------------------------
    # Recent Diary event reaches Context
    # --------------------------------------------------

    assert (
        "Recent Jarvis development activity."
        in system_content
    )


def test_retrieval_and_diary_are_separate_boundaries() -> None:
    """
    C.5 + C.6

    Retrieval and Diary must remain separate inputs
    to Context.

    Retrieval results are RetrievalResult objects.
    Diary results remain Diary events.
    """

    agent = build_agent()

    context = agent._build_context(
        user_input="Jarvis architecture"
    )

    messages = context.as_messages()

    system_content = messages[0]["content"]

    # Retrieval
    assert (
        "[memory] id=101 score=0.950"
        in system_content
    )

    # Diary
    assert (
        "Completed Context integration work for Jarvis."
        in system_content
    )


def test_retrieval_diary_context_is_deterministic() -> None:
    """
    C.5 + C.6

    Identical Agent state and identical source outputs
    must produce identical Context.
    """

    agent = build_agent()

    first = agent._build_context(
        user_input="Jarvis architecture"
    )

    second = agent._build_context(
        user_input="Jarvis architecture"
    )

    assert (
        first.as_messages()
        == second.as_messages()
    )


def main() -> None:
    test_unified_retrieval_reaches_context()
    test_diary_search_reaches_context()
    test_empty_input_uses_recent_diary()
    test_retrieval_and_diary_are_separate_boundaries()
    test_retrieval_diary_context_is_deterministic()

    print(
        "PASS: Unified Retrieval -> Context."
    )

    print(
        "PASS: Diary search -> Context."
    )

    print(
        "PASS: Recent Diary -> Context."
    )

    print(
        "PASS: Retrieval and Diary remain separate boundaries."
    )

    print(
        "PASS: Retrieval + Diary Context assembly is deterministic."
    )


if __name__ == "__main__":
    main()