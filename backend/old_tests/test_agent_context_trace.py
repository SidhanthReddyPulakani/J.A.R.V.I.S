"""
R2.10C.10 — Agent Context Integration Trace

Human-readable trace of the complete Agent -> Context pipeline.

This test intentionally enters the Context system through:

    JarvisAgent._build_context()

It does not call the real LLM.

The source services are replaced with deterministic trace doubles so
that the exact information flow can be observed without depending on
external state, model availability, or existing database contents.

Pipeline traced:

    User Input
        ↓
    Agent State
        ↓
    Core Memory
        ↓
    Conversation
        ↓
    Unified Retrieval
        ↓
    Diary
        ↓
    Operation Results
        ↓
    ContextRequest
        ↓
    ContextCompiler
        ↓
    AgentContext
        ↓
    ContextWindowManager
        ↓
    LLM boundary
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import (
    OperationResult,
    OperationErrorCode,
)
from jarvis.retrieval.models import RetrievalResult
from jarvis.state.models import AgentState


# ======================================================================
# Display helpers
# ======================================================================


WIDTH = 72


def line(char: str = "─") -> None:
    print(char * WIDTH)


def section(number: str, title: str) -> None:
    print()
    print("┌" + "─" * (WIDTH - 2) + "┐")
    print(
        f"│ {number} — {title}".ljust(WIDTH - 1) + "│"
    )
    print("└" + "─" * (WIDTH - 2) + "┘")


def field(name: str, value: Any, indent: int = 2) -> None:
    prefix = " " * indent
    print(f"{prefix}{name:<20}: {value}")


def success(message: str) -> None:
    print(f"  ✓ {message}")


def arrow(message: str) -> None:
    print(f"      ↓ {message}")


def show_text(
    label: str,
    value: str,
    indent: int = 4,
) -> None:
    prefix = " " * indent
    print(f"{prefix}{label}:")
    for line_value in str(value).splitlines():
        print(f"{prefix}  {line_value}")


# ======================================================================
# Trace data
# ======================================================================


@dataclass
class TraceDiaryEvent:
    id: int
    event_type: str
    description: str
    source: str
    created_at: str = "2026-08-30T12:00:00+00:00"


class TraceCoreMemory:
    """
    Deterministic Core Memory source.

    Records exactly when the Agent requests Core Memory.
    """

    def __init__(self) -> None:
        self.blocks = [
            SimpleNamespace(
                id=1,
                agent_id="trace-agent",
                label="identity",
                content=(
                    "Jarvis is a local desktop assistant."
                ),
                capacity=2000,
                priority=100,
                writable=True,
            ),
            SimpleNamespace(
                id=2,
                agent_id="trace-agent",
                label="project",
                content=(
                    "Jarvis uses a modular State and "
                    "Knowledge architecture."
                ),
                capacity=2000,
                priority=100,
                writable=True,
            ),
        ]

        self.calls = 0

    def list_blocks(self):
        self.calls += 1
        return list(self.blocks)


class TraceRetrieval:
    """
    Deterministic Unified Retrieval boundary.

    The Agent sees only one Retrieval service.

    The provider internals are intentionally not reproduced here.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

        self.results = [
            RetrievalResult(
                source="memory",
                identifier=101,
                content=(
                    "Jarvis uses modular State and "
                    "Knowledge architecture."
                ),
                score=0.950,
                metadata={
                    "category": "project",
                    "subject": "architecture",
                    "project": "Jarvis",
                },
            ),
            RetrievalResult(
                source="knowledge",
                identifier=202,
                content=(
                    "Context is the temporary reasoning "
                    "input for the LLM."
                ),
                score=0.880,
                metadata={
                    "document_title": "Jarvis Architecture",
                },
            ),
            RetrievalResult(
                source="relationship",
                identifier=303,
                content=(
                    "Jarvis → uses → modular architecture"
                ),
                score=0.760,
                metadata={
                    "relationship_type": "uses",
                },
            ),
            RetrievalResult(
                source="recall",
                identifier=404,
                content=(
                    "We previously discussed the Context "
                    "integration architecture."
                ),
                score=0.710,
                metadata={
                    "role": "user",
                },
            ),
        ]

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ):
        self.calls.append(
            {
                "query": query,
                "limit": limit,
            }
        )

        return list(self.results)


class TraceDiary:
    """
    Deterministic Diary boundary.
    """

    def __init__(self) -> None:
        self.search_calls: list[dict[str, Any]] = []
        self.recent_calls: list[dict[str, Any]] = []

        self.search_results = [
            TraceDiaryEvent(
                id=501,
                event_type="development",
                source="trace",
                description=(
                    "Context integration was completed "
                    "and the Agent assembly path was tested."
                ),
            ),
        ]

        self.recent_results = [
            TraceDiaryEvent(
                id=502,
                event_type="development",
                source="trace",
                description=(
                    "Recent development activity involved "
                    "the Context integration layer."
                ),
            ),
        ]

    def search(
        self,
        query: str,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ):
        self.search_calls.append(
            {
                "query": query,
                "conversation_id": conversation_id,
                "limit": limit,
            }
        )

        return list(self.search_results)

    def recent(
        self,
        *,
        conversation_id: int | None = None,
        limit: int = 10,
    ):
        self.recent_calls.append(
            {
                "conversation_id": conversation_id,
                "limit": limit,
            }
        )

        return list(self.recent_results)


class TraceWindowManager(ContextWindowManager):
    """
    Recording Context Window boundary.

    R2.11 will make this layer much more sophisticated.
    For C.10 we only need to demonstrate that the compiled
    AgentContext reaches it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.prepared_contexts = []

    def prepare(self, context):
        self.prepared_contexts.append(context)
        return super().prepare(context)


# ======================================================================
# Agent construction
# ======================================================================


def build_trace_agent() -> JarvisAgent:
    """
    Construct only the Agent pieces required by _build_context().

    JarvisAgent.__init__ is intentionally bypassed.

    This means:

        - no production database initialization
        - no Ollama call
        - no real tool execution
        - no dependency on existing persistent data

    The actual Agent method under test remains:

        JarvisAgent._build_context()
    """

    agent = object.__new__(JarvisAgent)

    agent.state = AgentState(
        agent_id="trace-agent",
        conversation_id=42,
        current_task="C.10 Context Integration Trace",
        current_goal=(
            "Trace information from Agent-owned sources "
            "through Context to the LLM boundary."
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
                "What are we testing in the Context layer?"
            ),
        },
        {
            "role": "assistant",
            "content": (
                "We are testing the complete Agent "
                "Context assembly pipeline."
            ),
        },
    ]

    agent.core_memory = TraceCoreMemory()
    agent.retrieval = TraceRetrieval()
    agent.diary = TraceDiary()

    agent.operation_results = []

    agent.context_compiler = ContextCompiler(
        system_prompt=(
            "You are Jarvis, a fast local desktop assistant."
        )
    )

    agent.context_window = TraceWindowManager()

    return agent


# ======================================================================
# Trace stages
# ======================================================================


def print_input(
    user_input: str,
) -> None:
    section("01", "CURRENT USER INPUT")

    show_text(
        "Input",
        user_input,
    )

    arrow("Agent._build_context()")


def print_state(
    agent: JarvisAgent,
) -> None:
    section("02", "AGENT STATE")

    state = agent.state

    field("agent_id", state.agent_id)
    field("conversation_id", state.conversation_id)
    field("mode", state.mode)
    field("current_task", state.current_task)
    field("current_goal", state.current_goal)
    field("active_project", state.active_project)
    field("active_operation", state.active_operation)
    field("operation_status", state.operation_status)

    success("Current Agent State available to Context.")


def print_core_memory(
    agent: JarvisAgent,
) -> None:
    section("03", "CORE MEMORY")

    blocks = agent.core_memory.list_blocks()

    field(
        "service call count",
        agent.core_memory.calls,
    )

    print()

    for block in blocks:
        print(
            f"  [{block.label}] "
            f"id={block.id} "
            f"capacity={block.capacity}"
        )

        for content_line in block.content.splitlines():
            print(f"      {content_line}")

        print()

    success(
        f"{len(blocks)} Core Memory blocks collected."
    )


def print_conversation(
    agent: JarvisAgent,
) -> None:
    section("04", "CURRENT CONVERSATION")

    for index, message in enumerate(
        agent.messages,
        start=1,
    ):
        print(
            f"  MESSAGE #{index}"
        )
        field(
            "role",
            message.get("role"),
            indent=6,
        )
        field(
            "content",
            message.get("content"),
            indent=6,
        )
        print()

    success(
        f"{len(agent.messages)} conversation messages available."
    )


def print_retrieval(
    agent: JarvisAgent,
    user_input: str,
) -> None:
    section("05", "UNIFIED RETRIEVAL")

    print("  REQUEST")
    field(
        "query",
        user_input,
        indent=6,
    )
    field(
        "limit",
        10,
        indent=6,
    )

    arrow(
        "RetrievalService.search()"
    )

    results = agent.retrieval.results

    print()
    print(
        f"  RESULTS ({len(results)})"
    )
    print()

    for index, result in enumerate(
        results,
        start=1,
    ):
        print(
            f"  RESULT #{index}"
        )
        field(
            "source",
            result.source,
            indent=6,
        )
        field(
            "identifier",
            result.identifier,
            indent=6,
        )
        field(
            "score",
            f"{result.score:.3f}",
            indent=6,
        )

        if result.metadata:
            field(
                "metadata",
                result.metadata,
                indent=6,
            )

        show_text(
            "content",
            result.content,
            indent=6,
        )

        print()

    call = agent.retrieval.calls[-1]

    success(
        "Agent issued exactly one unified Retrieval request."
    )

    field(
        "actual query",
        call["query"],
        indent=4,
    )
    field(
        "actual limit",
        call["limit"],
        indent=4,
    )


def print_diary(
    agent: JarvisAgent,
) -> None:
    section("06", "DIARY")

    print("  SEARCH REQUEST")

    call = agent.diary.search_calls[-1]

    field(
        "query",
        call["query"],
        indent=6,
    )
    field(
        "conversation_id",
        call["conversation_id"],
        indent=6,
    )
    field(
        "limit",
        call["limit"],
        indent=6,
    )

    print()

    print("  RESULTS")

    for event in agent.diary.search_results:
        print(
            f"  [diary] "
            f"id={event.id} "
            f"type={event.event_type} "
            f"source={event.source}"
        )

        print(
            f"      {event.description}"
        )

    success(
        "Diary remains a separate Agent-owned information source."
    )


def print_operation_results(
    operation_results,
) -> None:
    section("07", "OPERATION RESULTS")

    if not operation_results:
        print("  No operation results supplied.")
        print()
        success(
            "Empty operation-result set is valid."
        )
        return

    for result in operation_results:
        print(
            f"  [operation={result.operation}]"
        )
        print(
            f"      status={result.status}"
        )
        print(
            f"      success={result.success}"
        )
        print(
            f"      data={result.data}"
        )


def print_context_request_projection(
    agent: JarvisAgent,
    user_input: str,
    operation_results,
) -> None:
    """
    Print the data that _build_context() assembles into ContextRequest.

    We do not intercept the actual local variable inside the Agent
    method. Instead, this displays the same source data that the
    current implementation passes to ContextRequest.
    """

    section("08", "CONTEXT REQUEST ASSEMBLY")

    print("  ContextRequest fields")
    print()

    field(
        "user_input",
        user_input,
    )
    field(
        "state",
        type(agent.state).__name__,
    )
    field(
        "conversation",
        f"{len(agent.messages)} messages",
    )
    field(
        "core_memory",
        f"{len(agent.core_memory.blocks)} blocks",
    )
    field(
        "diary",
        f"{len(agent.diary.search_results)} events",
    )
    field(
        "retrieval_results",
        f"{len(agent.retrieval.results)} results",
    )
    field(
        "operation_results",
        f"{len(operation_results)} results",
    )

    print()
    success(
        "All collected information is ready for Context compilation."
    )

    arrow("ContextCompiler.compile()")


def print_compiled_context(
    context,
) -> None:
    section("09", "COMPILED AGENT CONTEXT")

    messages = context.as_messages()

    field(
        "message count",
        len(messages),
    )

    print()

    for index, message in enumerate(
        messages,
        start=1,
    ):
        print(
            f"  MESSAGE #{index}"
        )

        field(
            "role",
            message.get("role"),
            indent=6,
        )

        content = message.get(
            "content",
            "",
        )

        print(
            "      ┌" + "─" * 58
        )

        for content_line in content.splitlines():
            print(
                f"      │ {content_line}"
            )

        print(
            "      └" + "─" * 58
        )

        print()

    success(
        "ContextCompiler produced an AgentContext."
    )


def print_window_boundary(
    agent: JarvisAgent,
    context,
) -> None:
    section("10", "CONTEXT WINDOW BOUNDARY")

    field(
        "prepare() calls",
        len(
            agent.context_window.prepared_contexts
        ),
    )

    prepared = (
        agent.context_window.prepared_contexts[-1]
    )

    field(
        "input AgentContext",
        type(prepared).__name__,
    )

    field(
        "message count",
        len(prepared.as_messages()),
    )

    print()

    print(
        "  AgentContext"
    )
    print(
        "       ↓"
    )
    print(
        "  ContextWindowManager.prepare()"
    )
    print(
        "       ↓"
    )
    print(
        "  LLM-ready context"
    )

    success(
        "Compiled context reached the Window Manager."
    )


def print_llm_boundary(
    context,
) -> None:
    section("11", "LLM BOUNDARY")

    print(
        "  The Context pipeline has reached the point"
    )
    print(
        "  where the LLM would receive the prepared messages."
    )

    print()

    field(
        "LLM invoked",
        "NO",
    )
    field(
        "reason",
        "C.10 traces the boundary without model inference.",
    )

    print()
    success(
        "LLM boundary reached without invoking Ollama."
    )


# ======================================================================
# Assertions
# ======================================================================


def assert_trace(
    agent: JarvisAgent,
    context,
    user_input: str,
) -> None:
    """
    Assertions accompanying the visual trace.

    The output explains what happened; these assertions ensure
    the observed pipeline is actually correct.
    """

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
        "Agent ID: trace-agent"
        in system_content
    )

    assert (
        "Current task: C.10 Context Integration Trace"
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
        "Jarvis is a local desktop assistant."
        in system_content
    )

    assert (
        "Jarvis uses a modular State and Knowledge architecture."
        in system_content
    )

    assert agent.core_memory.calls >= 1

    # --------------------------------------------------
    # Conversation
    # --------------------------------------------------

    assert len(messages) == 3

    assert (
        messages[1]["role"]
        == "user"
    )

    assert (
        messages[2]["role"]
        == "assistant"
    )

    assert (
        "What are we testing in the Context layer?"
        == messages[1]["content"]
    )

    # --------------------------------------------------
    # Retrieval
    # --------------------------------------------------

    assert len(agent.retrieval.calls) == 1

    assert (
        agent.retrieval.calls[0]["query"]
        == user_input
    )

    assert (
        agent.retrieval.calls[0]["limit"]
        == 10
    )

    assert (
        "Jarvis uses modular State and Knowledge architecture."
        in system_content
    )

    assert (
        "Context is the temporary reasoning input"
        in system_content
    )

    assert (
        "Jarvis → uses → modular architecture"
        in system_content
    )

    assert (
        "We previously discussed the Context integration architecture."
        in system_content
    )

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

    assert (
        "[recall] id=404 score=0.710"
        in system_content
    )

    # --------------------------------------------------
    # Diary
    # --------------------------------------------------

    assert len(
        agent.diary.search_calls
    ) == 1

    diary_call = (
        agent.diary.search_calls[0]
    )

    assert (
        diary_call["query"]
        == user_input
    )

    assert (
        diary_call["conversation_id"]
        == 42
    )

    assert (
        "Context integration was completed"
        in system_content
    )

    # --------------------------------------------------
    # Window Manager
    # --------------------------------------------------

    assert len(
        agent.context_window.prepared_contexts
    ) == 1

    assert (
        agent.context_window.prepared_contexts[0]
        is context
    )


# ======================================================================
# Main
# ======================================================================


def main() -> None:
    print()
    print(
        "╔" + "═" * (WIDTH - 2) + "╗"
    )
    print(
        "║"
        + " R2.10C.10 — JARVIS AGENT → CONTEXT TRACE ".center(
            WIDTH - 2
        )
        + "║"
    )
    print(
        "╚" + "═" * (WIDTH - 2) + "╝"
    )

    user_input = (
        "Tell me about the Jarvis architecture."
    )

    # --------------------------------------------------
    # Build controlled Agent
    # --------------------------------------------------

    agent = build_trace_agent()

    print()
    print(
        "Agent created using the current "
        "JarvisAgent._build_context() implementation."
    )

    print(
        "The real LLM is NOT invoked."
    )

    # --------------------------------------------------
    # Display the information that will flow
    # --------------------------------------------------

    print_input(
        user_input
    )

    print_state(
        agent
    )

    print_core_memory(
        agent
    )

    print_conversation(
        agent
    )

    # --------------------------------------------------
    # Execute the actual Agent assembly operation
    # --------------------------------------------------

    context = agent._build_context(
        user_input=user_input,
        operation_results=[],
    )

    # --------------------------------------------------
    # Display what the Agent actually requested
    # --------------------------------------------------

    print_retrieval(
        agent,
        user_input,
    )

    print_diary(
        agent
    )

    print_operation_results(
        []
    )

    print_context_request_projection(
        agent,
        user_input,
        [],
    )

    print_compiled_context(
        context
    )

    print_window_boundary(
        agent,
        context,
    )

    print_llm_boundary(
        context
    )

    # --------------------------------------------------
    # Validate everything shown
    # --------------------------------------------------

    assert_trace(
        agent,
        context,
        user_input,
    )

    # --------------------------------------------------
    # Final result
    # --------------------------------------------------

    print()
    line("═")

    print(
        "  ✓ TRACE ASSERTIONS PASSED"
    )

    print(
        "  ✓ State reached Context"
    )

    print(
        "  ✓ Core Memory reached Context"
    )

    print(
        "  ✓ Conversation reached Context"
    )

    print(
        "  ✓ Unified Retrieval reached Context"
    )

    print(
        "  ✓ Diary reached Context"
    )

    print(
        "  ✓ Operation-result boundary remained valid"
    )

    print(
        "  ✓ Context reached Window Manager"
    )

    print(
        "  ✓ LLM was not invoked"
    )

    line("═")

    print()
    print(
        "C.10 visual integration trace completed successfully."
    )
    print()


if __name__ == "__main__":
    main()