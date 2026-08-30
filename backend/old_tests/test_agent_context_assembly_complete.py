"""
R2.10C.9

Heavy Agent-level Context Assembly tests.

These tests intentionally enter the Context system ONLY through
JarvisAgent._build_context().

They do not directly construct ContextRequest or call
ContextCompiler for the behavior under test.

The purpose is to verify that the Agent correctly assembles:

    current input
    + Agent State
    + Core Memory
    + conversation
    + unified Retrieval
    + Diary
    + Operation Results

into one deterministic AgentContext.

Lower-level source/compiler behavior is tested elsewhere.
"""

from __future__ import annotations

from types import SimpleNamespace

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
)
from jarvis.retrieval.models import RetrievalResult
from jarvis.state.models import AgentState


# ======================================================================
# Test doubles
# ======================================================================


class RecordingCoreMemory:
    """
    Controlled Core Memory source.

    The test is interested in whether Agent asks for Core Memory
    and whether the returned blocks reach Context.
    """

    def __init__(self, blocks=None) -> None:
        self.blocks = list(blocks or [])
        self.list_calls = 0

    def list_blocks(self):
        self.list_calls += 1
        return list(self.blocks)


class RecordingRetrieval:
    """
    Controlled unified Retrieval boundary.

    This deliberately represents Retrieval as one Agent-facing
    source. Individual provider internals are not re-tested here.
    """

    def __init__(self, results=None) -> None:
        self.results = list(results or [])
        self.search_calls = []

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ):
        self.search_calls.append(
            {
                "query": query,
                "limit": limit,
            }
        )

        return list(self.results)


class RecordingDiary:
    """
    Controlled Diary source.

    Both search() and recent() are recorded so the Agent's
    empty-input behavior can be verified.
    """

    def __init__(
        self,
        search_results=None,
        recent_results=None,
    ) -> None:

        self.search_results = list(
            search_results or []
        )

        self.recent_results = list(
            recent_results or []
        )

        self.search_calls = []
        self.recent_calls = []

    def search(
        self,
        query: str,
        *,
        conversation_id=None,
        limit: int = 10,
    ):

        self.search_calls.append(
            {
                "query": query,
                "conversation_id": conversation_id,
                "limit": limit,
            }
        )

        return list(
            self.search_results
        )

    def recent(
        self,
        *,
        conversation_id=None,
        limit: int = 10,
    ):

        self.recent_calls.append(
            {
                "conversation_id": conversation_id,
                "limit": limit,
            }
        )

        return list(
            self.recent_results
        )


# ======================================================================
# Fixtures
# ======================================================================


SYSTEM_PROMPT = (
    "You are Jarvis."
)


def build_state(
    agent_id: str = "c9-agent",
    conversation_id: int = 42,
) -> AgentState:

    return AgentState(
        agent_id=agent_id,
        conversation_id=conversation_id,
        current_task="C.9 Agent Context Assembly",
        current_goal=(
            "Verify complete Agent context assembly."
        ),
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def build_core_blocks() -> list:
    """
    Use the established MemoryBlock shape.

    The compiler only needs the real block attributes.
    """

    return [
        SimpleNamespace(
            id=1,
            agent_id="c9-agent",
            label="identity",
            content=(
                "Jarvis is a local desktop assistant."
            ),
            capacity=2000,
            priority=10,
            writable=True,
        ),
        SimpleNamespace(
            id=2,
            agent_id="c9-agent",
            label="project",
            content=(
                "Jarvis uses modular State and Knowledge architecture."
            ),
            capacity=2000,
            priority=20,
            writable=True,
        ),
    ]


def build_retrieval_results() -> list[RetrievalResult]:

    return [
        RetrievalResult(
            source="memory",
            identifier=101,
            content=(
                "Jarvis remembers the modular architecture."
            ),
            score=0.95,
            metadata={
                "category": "project",
                "subject": "architecture",
            },
        ),
        RetrievalResult(
            source="knowledge",
            identifier=202,
            content=(
                "Context is the temporary reasoning input."
            ),
            score=0.88,
            metadata={
                "topic": "context",
            },
        ),
        RetrievalResult(
            source="relationship",
            identifier=303,
            content=(
                "Jarvis → uses → modular architecture"
            ),
            score=0.76,
        ),
        RetrievalResult(
            source="recall",
            identifier=404,
            content=(
                "We previously discussed Context integration."
            ),
            score=0.71,
            metadata={
                "role": "user",
            },
        ),
    ]


def build_diary_event(
    event_id: int,
    description: str,
):

    return SimpleNamespace(
        id=event_id,
        description=description,
        event_type="test_event",
        source="c9-test",
        created_at=(
            "2026-08-30T00:00:00+00:00"
        ),
    )


def build_agent(
    *,
    retrieval_results=None,
    diary_search_results=None,
    diary_recent_results=None,
    core_blocks=None,
    conversation=None,
    operation_results=None,
):
    """
    Construct a lightweight Agent-shaped object whose context
    assembly is the real JarvisAgent._build_context() method.

    We deliberately avoid JarvisAgent.__init__ because it initializes
    the real database and LLM. C.9 is about the Agent assembly
    boundary, not database or Ollama startup.
    """

    from jarvis.core.agent import JarvisAgent

    agent = object.__new__(
        JarvisAgent
    )

    agent.state = build_state()

    agent.core_memory = (
        RecordingCoreMemory(
            core_blocks
            if core_blocks is not None
            else build_core_blocks()
        )
    )

    agent.retrieval = (
        RecordingRetrieval(
            retrieval_results
            if retrieval_results is not None
            else build_retrieval_results()
        )
    )

    agent.diary = (
        RecordingDiary(
            search_results=(
                diary_search_results
                if diary_search_results is not None
                else [
                    build_diary_event(
                        601,
                        (
                            "The Context integration "
                            "was reviewed."
                        ),
                    )
                ]
            ),
            recent_results=(
                diary_recent_results
                if diary_recent_results is not None
                else [
                    build_diary_event(
                        602,
                        (
                            "The Agent Context assembly "
                            "test was started."
                        ),
                    )
                ]
            ),
        )
    )

    agent.messages = list(
        conversation
        if conversation is not None
        else [
            {
                "role": "user",
                "content": (
                    "We are testing Agent Context."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The Agent Context assembly is being verified."
                ),
            },
        ]
    )

    agent.operation_results = list(
        operation_results
        if operation_results is not None
        else []
    )

    agent.context_compiler = (
        ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )
    )

    agent.context_window = (
        ContextWindowManager()
    )

    return agent


def system_content(context) -> str:

    messages = context.as_messages()

    assert messages

    assert (
        messages[0]["role"]
        == "system"
    )

    return messages[0]["content"]


# ======================================================================
# C.9.1 — Complete source assembly
# ======================================================================


def test_complete_agent_context_contains_all_sources() -> None:
    """
    The Agent must assemble every currently supported Context source
    through _build_context().
    """

    operation_result = (
        OperationResult.success_result(
            operation="memory_create",
            data={
                "memory_id": 501,
            },
        )
    )

    agent = build_agent(
        operation_results=[
            operation_result
        ]
    )

    context = agent._build_context(
        user_input=(
            "Tell me about Jarvis architecture."
        )
    )

    messages = context.as_messages()

    assert messages

    content = system_content(
        context
    )

    # --------------------------------------------------------------
    # State
    # --------------------------------------------------------------

    assert (
        "CURRENT AGENT STATE"
        in content
    )

    assert (
        "Agent ID: c9-agent"
        in content
    )

    assert (
        "C.9 Agent Context Assembly"
        in content
    )

    # --------------------------------------------------------------
    # Core Memory
    # --------------------------------------------------------------

    assert (
        "CORE MEMORY"
        in content
    )

    assert (
        "Jarvis is a local desktop assistant."
        in content
    )

    assert (
        "Jarvis uses modular State and Knowledge architecture."
        in content
    )

    # --------------------------------------------------------------
    # Retrieval
    # --------------------------------------------------------------

    assert (
        "RETRIEVED INFORMATION"
        in content
    )

    assert (
        "Jarvis remembers the modular architecture."
        in content
    )

    assert (
        "Context is the temporary reasoning input."
        in content
    )

    assert (
        "Jarvis → uses → modular architecture"
        in content
    )

    assert (
        "We previously discussed Context integration."
        in content
    )

    # --------------------------------------------------------------
    # Diary
    # --------------------------------------------------------------

    assert (
        "DIARY"
        in content
    )

    assert (
        "The Context integration was reviewed."
        in content
    )

    # --------------------------------------------------------------
    # Operation Result
    # --------------------------------------------------------------

    assert (
        "OPERATION RESULTS"
        in content
    )

    assert (
        "[operation=memory_create]"
        in content
    )

    assert (
        "memory_id"
        in content
    )

    assert (
        "501"
        in content
    )

    # --------------------------------------------------------------
    # Conversation
    # --------------------------------------------------------------

    assert len(messages) == 3

    assert (
        messages[1]["role"]
        == "user"
    )

    assert (
        messages[1]["content"]
        == "We are testing Agent Context."
    )

    assert (
        messages[2]["role"]
        == "assistant"
    )

    assert (
        messages[2]["content"]
        == (
            "The Agent Context assembly is being verified."
        )
    )


# ======================================================================
# C.9.2 — Retrieval boundary
# ======================================================================


def test_agent_uses_unified_retrieval_boundary() -> None:
    """
    Agent must ask the unified Retrieval service for relevant
    information rather than independently querying Memory,
    Knowledge, Relationships, or Recall.
    """

    agent = build_agent()

    agent._build_context(
        user_input="Jarvis architecture"
    )

    assert (
        agent.retrieval.search_calls
        == [
            {
                "query": "Jarvis architecture",
                "limit": 10,
            }
        ]
    )


# ======================================================================
# C.9.3 — Diary search boundary
# ======================================================================


def test_non_empty_input_searches_diary() -> None:
    """
    A non-empty query must use Diary.search().
    """

    agent = build_agent()

    agent._build_context(
        user_input="Jarvis architecture"
    )

    assert (
        len(agent.diary.search_calls)
        == 1
    )

    call = (
        agent.diary.search_calls[0]
    )

    assert (
        call["query"]
        == "Jarvis architecture"
    )

    assert (
        call["conversation_id"]
        == 42
    )

    assert (
        call["limit"]
        == 10
    )

    assert (
        agent.diary.recent_calls
        == []
    )


# ======================================================================
# C.9.4 — Empty-input semantics
# ======================================================================


def test_empty_input_uses_recent_diary_and_skips_retrieval() -> None:
    """
    Empty input must not cause an empty Retrieval search.

    The Agent should instead use recent Diary events.
    """

    agent = build_agent()

    context = agent._build_context()

    assert (
        agent.retrieval.search_calls
        == []
    )

    assert (
        agent.diary.search_calls
        == []
    )

    assert (
        len(agent.diary.recent_calls)
        == 1
    )

    call = (
        agent.diary.recent_calls[0]
    )

    assert (
        call["conversation_id"]
        == 42
    )

    assert (
        call["limit"]
        == 10
    )

    content = system_content(
        context
    )

    assert (
        "The Agent Context assembly test was started."
        in content
    )


# ======================================================================
# C.9.5 — Query normalization behavior
# ======================================================================


def test_whitespace_only_input_uses_recent_diary() -> None:
    """
    Whitespace-only input is semantically empty for the current
    Agent retrieval policy.
    """

    agent = build_agent()

    context = agent._build_context(
        user_input="   \t  \n "
    )

    assert (
        agent.retrieval.search_calls
        == []
    )

    assert (
        agent.diary.search_calls
        == []
    )

    assert (
        len(agent.diary.recent_calls)
        == 1
    )

    content = system_content(
        context
    )

    assert (
        "The Agent Context assembly test was started."
        in content
    )


# ======================================================================
# C.9.6 — Core Memory access
# ======================================================================


def test_agent_reads_core_memory_once_per_build() -> None:
    """
    Core Memory should be read as part of every context build.
    """

    agent = build_agent()

    agent._build_context(
        user_input="test"
    )

    assert (
        agent.core_memory.list_calls
        == 1
    )


def test_core_memory_changes_are_visible_on_rebuild() -> None:
    """
    A rebuilt Context must observe changed Core Memory.
    """

    agent = build_agent(
        core_blocks=[
            SimpleNamespace(
                id=1,
                agent_id="c9-agent",
                label="project",
                content="OLD CORE MEMORY",
                capacity=2000,
                priority=10,
                writable=True,
            )
        ]
    )

    first = agent._build_context(
        user_input="test"
    )

    first_content = system_content(
        first
    )

    assert (
        "OLD CORE MEMORY"
        in first_content
    )

    agent.core_memory.blocks = [
        SimpleNamespace(
            id=1,
            agent_id="c9-agent",
            label="project",
            content="NEW CORE MEMORY",
            capacity=2000,
            priority=10,
            writable=True,
        )
    ]

    second = agent._build_context(
        user_input="test"
    )

    second_content = system_content(
        second
    )

    assert (
        "NEW CORE MEMORY"
        in second_content
    )

    assert (
        "OLD CORE MEMORY"
        not in second_content
    )


# ======================================================================
# C.9.7 — Conversation snapshot
# ======================================================================


def test_conversation_is_copied_into_context() -> None:
    """
    _build_context() must snapshot the Agent's current conversation.
    """

    conversation = [
        {
            "role": "user",
            "content": "ORIGINAL MESSAGE",
        }
    ]

    agent = build_agent(
        conversation=conversation
    )

    context = agent._build_context(
        user_input="test"
    )

    # Mutate the Agent after Context creation.
    agent.messages.append(
        {
            "role": "assistant",
            "content": "LATER MESSAGE",
        }
    )

    messages = context.as_messages()

    assert len(messages) == 2

    assert (
        messages[1]["content"]
        == "ORIGINAL MESSAGE"
    )

    assert all(
        message["content"]
        != "LATER MESSAGE"
        for message in messages
    )


# ======================================================================
# C.9.8 — Operation Result assembly
# ======================================================================


def test_agent_stored_operation_results_reach_context() -> None:
    """
    Agent-owned operation results must reach Context when no explicit
    result list is supplied.
    """

    result = (
        OperationResult.success_result(
            operation="knowledge_search",
            data={
                "result_id": 202,
                "topic": "architecture",
            },
        )
    )

    agent = build_agent(
        operation_results=[result]
    )

    context = agent._build_context(
        user_input="test"
    )

    content = system_content(
        context
    )

    assert (
        "knowledge_search"
        in content
    )

    assert (
        "result_id"
        in content
    )

    assert (
        "202"
        in content
    )


def test_explicit_operation_results_override_agent_results() -> None:
    """
    Explicit results belong to the current build and override the
    Agent's stored ephemeral result set.
    """

    stored = (
        OperationResult.success_result(
            operation="stored_operation",
            data={
                "value": "stored",
            },
        )
    )

    explicit = (
        OperationResult.success_result(
            operation="explicit_operation",
            data={
                "value": "explicit",
            },
        )
    )

    agent = build_agent(
        operation_results=[stored]
    )

    context = agent._build_context(
        user_input="test",
        operation_results=[explicit],
    )

    content = system_content(
        context
    )

    assert (
        "explicit_operation"
        in content
    )

    assert (
        "stored_operation"
        not in content
    )


def test_failed_operation_result_reaches_context() -> None:
    """
    Failure results must retain their structured failure information.
    """

    result = (
        OperationResult.failure_result(
            operation="memory_get",
            error_code=(
                OperationErrorCode.NOT_FOUND
            ),
            error_message=(
                "Requested memory was not found."
            ),
        )
    )

    agent = build_agent(
        operation_results=[result]
    )

    context = agent._build_context(
        user_input="test"
    )

    content = system_content(
        context
    )

    assert (
        "memory_get"
        in content
    )

    assert (
        "status=failure"
        in content
    )

    assert (
        "not_found"
        in content
    )

    assert (
        "Requested memory was not found."
        in content
    )


# ======================================================================
# C.9.9 — Operation Result snapshot isolation
# ======================================================================


def test_operation_results_are_snapshotted() -> None:
    """
    Context must not retain the live Agent operation-result list.
    """

    result = (
        OperationResult.success_result(
            operation="temporary_operation",
            data={
                "value": "temporary",
            },
        )
    )

    agent = build_agent()

    context = agent._build_context(
        user_input="test",
        operation_results=[result],
    )

    # Change the supplied list after the build.
    supplied = [result]

    context = agent._build_context(
        user_input="test",
        operation_results=supplied,
    )

    supplied.clear()

    content = system_content(
        context
    )

    assert (
        "temporary_operation"
        in content
    )


# ======================================================================
# C.9.10 — Retrieval rebuild behavior
# ======================================================================


def test_retrieval_changes_are_visible_on_rebuild() -> None:
    """
    Context must be rebuilt from the current Retrieval output.
    """

    first_result = RetrievalResult(
        source="memory",
        identifier=111,
        content="FIRST RETRIEVAL RESULT",
        score=0.90,
    )

    second_result = RetrievalResult(
        source="knowledge",
        identifier=222,
        content="SECOND RETRIEVAL RESULT",
        score=0.90,
    )

    agent = build_agent(
        retrieval_results=[first_result]
    )

    first = agent._build_context(
        user_input="test"
    )

    assert (
        "FIRST RETRIEVAL RESULT"
        in system_content(first)
    )

    agent.retrieval.results = [
        second_result
    ]

    second = agent._build_context(
        user_input="test"
    )

    second_content = system_content(
        second
    )

    assert (
        "SECOND RETRIEVAL RESULT"
        in second_content
    )

    assert (
        "FIRST RETRIEVAL RESULT"
        not in second_content
    )


# ======================================================================
# C.9.11 — Diary rebuild behavior
# ======================================================================


def test_diary_changes_are_visible_on_rebuild() -> None:
    """
    Context must be rebuilt from the current Diary search output.
    """

    agent = build_agent(
        diary_search_results=[
            build_diary_event(
                701,
                "FIRST DIARY RESULT",
            )
        ]
    )

    first = agent._build_context(
        user_input="test"
    )

    assert (
        "FIRST DIARY RESULT"
        in system_content(first)
    )

    agent.diary.search_results = [
        build_diary_event(
            702,
            "SECOND DIARY RESULT",
        )
    ]

    second = agent._build_context(
        user_input="test"
    )

    content = system_content(
        second
    )

    assert (
        "SECOND DIARY RESULT"
        in content
    )

    assert (
        "FIRST DIARY RESULT"
        not in content
    )


# ======================================================================
# C.9.12 — State rebuild behavior
# ======================================================================


def test_state_changes_are_visible_on_rebuild() -> None:
    """
    Context is a snapshot of current Agent State at build time.
    """

    agent = build_agent()

    first = agent._build_context(
        user_input="test"
    )

    assert (
        "C.9 Agent Context Assembly"
        in system_content(first)
    )

    agent.state.current_task = (
        "UPDATED AGENT TASK"
    )

    second = agent._build_context(
        user_input="test"
    )

    content = system_content(
        second
    )

    assert (
        "UPDATED AGENT TASK"
        in content
    )

    assert (
        "C.9 Agent Context Assembly"
        not in content
    )


# ======================================================================
# C.9.13 — Determinism
# ======================================================================


def test_complete_agent_context_is_deterministic() -> None:
    """
    Identical Agent state and identical source outputs must produce
    identical LLM-facing Context.
    """

    operation_result = (
        OperationResult.success_result(
            operation="memory_create",
            data={
                "memory_id": 501,
            },
        )
    )

    agent = build_agent(
        operation_results=[
            operation_result
        ]
    )

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


# ======================================================================
# C.9.14 — Build isolation
# ======================================================================


def test_two_agent_builds_are_distinct_context_objects() -> None:
    """
    Every build must produce a new AgentContext snapshot.
    """

    agent = build_agent()

    first = agent._build_context(
        user_input="test"
    )

    second = agent._build_context(
        user_input="test"
    )

    assert (
        first is not second
    )

    assert (
        first.as_messages()
        == second.as_messages()
    )


# ======================================================================
# C.9.15 — Empty optional sources
# ======================================================================


def test_all_optional_agent_sources_can_be_empty() -> None:
    """
    Agent context assembly must remain valid when all optional
    information sources return nothing.
    """

    agent = build_agent(
        retrieval_results=[],
        diary_search_results=[],
        diary_recent_results=[],
        core_blocks=[],
        conversation=[],
        operation_results=[],
    )

    context = agent._build_context(
        user_input="test"
    )

    messages = context.as_messages()

    assert messages

    content = system_content(
        context
    )

    assert (
        "CURRENT AGENT STATE"
        in content
    )

    assert (
        "CORE MEMORY"
        in content
    )

    assert (
        "RETRIEVED INFORMATION"
        not in content
    )

    assert (
        "DIARY"
        not in content
    )

    assert (
        "OPERATION RESULTS"
        not in content
    )


# ======================================================================
# C.9.16 — Source separation
# ======================================================================


def test_retrieval_and_diary_remain_separate() -> None:
    """
    RetrievalResult objects and Diary events must remain distinct
    source categories even though both reach the same Context.
    """

    retrieval = RetrievalResult(
        source="memory",
        identifier=801,
        content="RETRIEVAL ONLY",
        score=0.91,
    )

    diary = build_diary_event(
        802,
        "DIARY ONLY",
    )

    agent = build_agent(
        retrieval_results=[retrieval],
        diary_search_results=[diary],
    )

    context = agent._build_context(
        user_input="test"
    )

    content = system_content(
        context
    )

    assert (
        "RETRIEVED INFORMATION"
        in content
    )

    assert (
        "RETRIEVAL ONLY"
        in content
    )

    assert (
        "DIARY"
        in content
    )

    assert (
        "DIARY ONLY"
        in content
    )


# ======================================================================
# C.9.17 — Retrieval source metadata preservation
# ======================================================================


def test_retrieval_metadata_survives_agent_assembly() -> None:
    """
    Agent assembly must not strip RetrievalResult identity or score.
    """

    result = RetrievalResult(
        source="knowledge",
        identifier=901,
        content="Metadata must survive Agent assembly.",
        score=0.873,
        metadata={
            "topic": "agent-context",
            "category": "architecture",
        },
    )

    agent = build_agent(
        retrieval_results=[result]
    )

    context = agent._build_context(
        user_input="metadata"
    )

    content = system_content(
        context
    )

    assert (
        "[knowledge]"
        in content
    )

    assert (
        "id=901"
        in content
    )

    assert (
        "score=0.873"
        in content
    )

    assert (
        "Metadata must survive Agent assembly."
        in content
    )


# ======================================================================
# C.9.18 — Window boundary
# ======================================================================


def test_agent_context_passes_through_window_manager() -> None:
    """
    _build_context() must return the result of the Context Window
    preparation stage, not bypass it.
    """

    class RecordingWindow:
        def __init__(self):
            self.calls = []

        def prepare(self, context):
            self.calls.append(context)

            return context

    agent = build_agent()

    window = RecordingWindow()

    agent.context_window = window

    context = agent._build_context(
        user_input="test"
    )

    assert (
        len(window.calls)
        == 1
    )

    assert (
        window.calls[0]
        is context
    )


# ======================================================================
# C.9.19 — Call ordering
# ======================================================================


def test_agent_collects_sources_before_window_preparation() -> None:
    """
    Source collection must occur before the compiled Context reaches
    the Window Manager.
    """

    events = []

    class OrderedCore:
        def list_blocks(self):
            events.append("core_memory")

            return []

    class OrderedRetrieval:
        def search(self, query, *, limit=10):
            events.append("retrieval")

            return []

    class OrderedDiary:
        def search(
            self,
            query,
            *,
            conversation_id=None,
            limit=10,
        ):
            events.append("diary")

            return []

        def recent(
            self,
            *,
            conversation_id=None,
            limit=10,
        ):
            events.append("diary_recent")

            return []

    class OrderedWindow:
        def prepare(self, context):
            events.append("window")

            return context

    agent = build_agent()

    agent.core_memory = OrderedCore()
    agent.retrieval = OrderedRetrieval()
    agent.diary = OrderedDiary()
    agent.context_window = OrderedWindow()

    agent._build_context(
        user_input="test"
    )

    assert (
        events[-1]
        == "window"
    )

    assert (
        "retrieval"
        in events
    )

    assert (
        "diary"
        in events
    )

    assert (
        "core_memory"
        in events
    )


# ======================================================================
# C.9.20 — No direct persistence dependency in assembly
# ======================================================================


def test_context_assembly_uses_agent_owned_sources_only() -> None:
    """
    The Agent assembly test substitutes all information sources with
    controlled Agent-owned objects.

    This verifies the assembly path does not require Context to reach
    into repositories directly.
    """

    agent = build_agent()

    context = agent._build_context(
        user_input="test"
    )

    assert context is not None

    assert (
        agent.core_memory.list_calls
        == 1
    )

    assert (
        len(agent.retrieval.search_calls)
        == 1
    )

    assert (
        len(agent.diary.search_calls)
        == 1
    )


# ======================================================================
# Main
# ======================================================================


def main() -> None:

    test_complete_agent_context_contains_all_sources()

    test_agent_uses_unified_retrieval_boundary()

    test_non_empty_input_searches_diary()

    test_empty_input_uses_recent_diary_and_skips_retrieval()

    test_whitespace_only_input_uses_recent_diary()

    test_agent_reads_core_memory_once_per_build()

    test_core_memory_changes_are_visible_on_rebuild()

    test_conversation_is_copied_into_context()

    test_agent_stored_operation_results_reach_context()

    test_explicit_operation_results_override_agent_results()

    test_failed_operation_result_reaches_context()

    test_operation_results_are_snapshotted()

    test_retrieval_changes_are_visible_on_rebuild()

    test_diary_changes_are_visible_on_rebuild()

    test_state_changes_are_visible_on_rebuild()

    test_complete_agent_context_is_deterministic()

    test_two_agent_builds_are_distinct_context_objects()

    test_all_optional_agent_sources_can_be_empty()

    test_retrieval_and_diary_remain_separate()

    test_retrieval_metadata_survives_agent_assembly()

    test_agent_context_passes_through_window_manager()

    test_agent_collects_sources_before_window_preparation()

    test_context_assembly_uses_agent_owned_sources_only()

    print(
        "PASS: C.9 complete Agent Context assembly."
    )

    print(
        "PASS: State + Core Memory + conversation assembled."
    )

    print(
        "PASS: unified Retrieval assembled."
    )

    print(
        "PASS: Diary search/recent semantics verified."
    )

    print(
        "PASS: Operation Result assembly verified."
    )

    print(
        "PASS: rebuild and snapshot semantics verified."
    )

    print(
        "PASS: deterministic Agent Context verified."
    )

    print(
        "PASS: Window Manager boundary verified."
    )

    print(
        "PASS: persistence boundary preserved."
    )


if __name__ == "__main__":
    main()