"""
R2.10B.10

Final Context compilation integration tests.

These tests validate the existing Context contract as a whole.

Important:
    This test suite must use the project's established object contracts.
    It must not redefine production contracts merely to satisfy tests.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.memory import CoreMemoryService
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
)
from jarvis.retrieval.models import RetrievalResult
from jarvis.state.models import AgentState
from jarvis.storage.database import Database
from jarvis.storage.repositories.core_memory import (
    CoreMemoryRepository,
)


SYSTEM_PROMPT = "You are Jarvis."


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def build_state() -> AgentState:
    """
    Build deterministic Agent State for Context compilation tests.
    """

    return AgentState(
        agent_id="context-compilation-test",
        conversation_id=42,
        current_task="Testing Context",
        current_goal="Verify complete Context compilation",
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


# ---------------------------------------------------------------------------
# Core Memory
# ---------------------------------------------------------------------------

def build_core_memory() -> list:
    """
    Build actual Core Memory blocks through the established
    CoreMemoryService -> Repository path.

    This deliberately avoids constructing fake dictionaries.
    """

    with TemporaryDirectory() as temp_dir:

        database_path = (
            Path(temp_dir)
            / "context_compilation_core_memory.db"
        )

        database = Database(
            database_path
        )

        database.initialize()

        # Core Memory rows are agent-scoped through Agent State.
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
                "context-compilation-test",
                "testing",
                "idle",
                "2026-08-29T00:00:00+00:00",
            ),
        )

        service = CoreMemoryService(
            CoreMemoryRepository(
                database
            ),
            agent_id="context-compilation-test",
        )

        service.create_block(
            label="identity",
            content="Jarvis is a local desktop assistant.",
            capacity=2000,
            priority=10,
            writable=True,
        )

        service.create_block(
            label="project",
            content="The project uses modular architecture.",
            capacity=2000,
            priority=20,
            writable=True,
        )

        return service.list_blocks()


# ---------------------------------------------------------------------------
# Context source fixtures
# ---------------------------------------------------------------------------

def build_diary_event():
    """
    Construct the minimal diary object shape consumed by the
    existing Context compiler.

    The compiler reads:
        description
        event_type
        source
        created_at
        id
    """

    return SimpleNamespace(
        id=601,
        description=(
            "The State and Knowledge architecture was reviewed."
        ),
        event_type="architecture_discussion",
        source="test",
        created_at="2026-08-29T00:00:00+00:00",
    )


def build_relationship():
    """
    Construct the minimal relationship object shape consumed by
    the existing Context compiler.

    The compiler reads:
        source
        target_type
        target
        id
        confidence
    """

    return SimpleNamespace(
        id=701,
        source="Jarvis",
        target_type="uses",
        target="modular architecture",
        confidence=0.91,
    )


def build_retrieval_results() -> list[RetrievalResult]:
    """
    Build unified RetrievalResult objects.

    Retrieval is the controlled information boundary between
    information sources and Context.
    """

    return [
        RetrievalResult(
            source="memory",
            identifier=101,
            content=(
                "Jarvis uses modular State "
                "and Knowledge architecture."
            ),
            score=0.95,
            metadata={
                "category": "project",
            },
        ),
        RetrievalResult(
            source="knowledge",
            identifier=202,
            content=(
                "Context is the temporary "
                "reasoning input."
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
    ]


def build_request() -> ContextRequest:
    """
    Construct a complete ContextRequest using the current
    Context contracts.
    """

    diary_event = build_diary_event()
    relationship = build_relationship()

    return ContextRequest(
        user_input=(
            "What does Jarvis know about this project?"
        ),

        state=build_state(),

        # Conversation is intentionally separate from the system
        # context. ContextCompiler normalizes these into LLM messages.
        conversation=[
            {
                "role": "user",
                "content": (
                    "We are testing the Context layer."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The Context layer is being verified."
                ),
            },
        ],

        core_memory=build_core_memory(),

        retrieval_results=build_retrieval_results(),

        diary=[
            diary_event,
        ],

        knowledge=[
            RetrievalResult(
                source="knowledge",
                identifier=801,
                content=(
                    "State and Knowledge are separate "
                    "information domains."
                ),
                score=0.84,
                metadata={
                    "topic": "architecture",
                },
            ),
        ],

        relationships=[
            relationship,
        ],

        operation_results=[
            OperationResult.success_result(
                operation="memory_create",
                data={
                    "memory_id": 501,
                },
            ),
        ],

        capability_information=[
            "The active project is Jarvis.",
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_all_context_sources_compile() -> None:
    """
    All Context sources must survive compilation simultaneously.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    context = compiler.compile(
        build_request()
    )

    messages = context.as_messages()

    assert messages

    system_message = messages[0]

    assert system_message["role"] == "system"

    system_content = system_message["content"]

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    assert (
        "You are Jarvis."
        in system_content
    )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    assert (
        "CURRENT AGENT STATE"
        in system_content
    )

    assert (
        "context-compilation-test"
        in system_content
    )

    assert (
        "Current task: Testing Context"
        in system_content
    )

    # ------------------------------------------------------------------
    # Core Memory
    # ------------------------------------------------------------------

    assert (
        "CORE MEMORY"
        in system_content
    )

    assert (
        "[identity]"
        in system_content
    )

    assert (
        "Jarvis is a local desktop assistant."
        in system_content
    )

    assert (
        "[project]"
        in system_content
    )

    assert (
        "The project uses modular architecture."
        in system_content
    )

    # ------------------------------------------------------------------
    # Diary
    # ------------------------------------------------------------------

    assert (
        "DIARY"
        in system_content
    )

    assert (
        "[diary] id=601"
        in system_content
    )

    assert (
        "type=architecture_discussion"
        in system_content
    )

    assert (
        "The State and Knowledge "
        "architecture was reviewed."
        in system_content
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    assert (
        "RELATIONSHIPS"
        in system_content
    )

    assert (
        "[relationship] id=701"
        in system_content
    )

    assert (
        "Jarvis → uses: modular architecture"
        in system_content
    )

    # ------------------------------------------------------------------
    # Capability information
    # ------------------------------------------------------------------

    assert (
        "CAPABILITY INFORMATION"
        in system_content
    )

    assert (
        "The active project is Jarvis."
        in system_content
    )

    # ------------------------------------------------------------------
    # Operation results
    # ------------------------------------------------------------------

    assert (
        "OPERATION RESULTS"
        in system_content
    )

    assert (
        "[operation=memory_create]"
        in system_content
    )

    assert (
        "status=success"
        in system_content
    )

    assert (
        "memory_id"
        in system_content
    )

    # ------------------------------------------------------------------
    # Unified Retrieval
    # ------------------------------------------------------------------

    assert (
        "RETRIEVED INFORMATION"
        in system_content
    )

    assert (
        "[memory] id=101 score=0.950"
        in system_content
    )

    assert (
        "Jarvis uses modular State "
        "and Knowledge architecture."
        in system_content
    )

    assert (
        "[knowledge] id=202 score=0.880"
        in system_content
    )

    assert (
        "Context is the temporary "
        "reasoning input."
        in system_content
    )

    assert (
        "[relationship] id=303 score=0.760"
        in system_content
    )

    assert (
        "Jarvis → uses → modular architecture"
        in system_content
    )


def test_conversation_is_preserved_as_llm_messages() -> None:
    """
    Conversation must survive compilation as normalized LLM
    messages rather than being incorrectly expected inside the
    system message.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    context = compiler.compile(
        build_request()
    )

    messages = context.as_messages()

    assert len(messages) == 3

    assert messages[0]["role"] == "system"

    assert messages[1]["role"] == "user"
    assert (
        messages[1]["content"]
        == "We are testing the Context layer."
    )

    assert messages[2]["role"] == "assistant"
    assert (
        messages[2]["content"]
        == "The Context layer is being verified."
    )


def test_context_compilation_is_deterministic() -> None:
    """
    Identical ContextRequests must produce identical
    LLM-facing representations.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    first = compiler.compile(
        build_request()
    )

    second = compiler.compile(
        build_request()
    )

    assert (
        first.as_messages()
        == second.as_messages()
    )


def test_empty_optional_sources_do_not_create_sections() -> None:
    """
    Empty optional sources must not create misleading sections.

    State and Core Memory remain part of the base Context contract.
    """

    request = ContextRequest(
        user_input="Hello",
        state=build_state(),
        conversation=[],
        core_memory=[],
        retrieval_results=[],
        diary=[],
        knowledge=[],
        relationships=[],
        operation_results=[],
        capability_information=[],
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    # Base sections.
    assert (
        "CURRENT AGENT STATE"
        in system_content
    )

    assert (
        "CORE MEMORY"
        in system_content
    )

    assert (
        "No Core Memory blocks."
        in system_content
    )

    # Optional sections must be absent.
    assert (
        "DIARY"
        not in system_content
    )

    assert (
        "RELATIONSHIPS"
        not in system_content
    )

    assert (
        "CAPABILITY INFORMATION"
        not in system_content
    )

    assert (
        "OPERATION RESULTS"
        not in system_content
    )

    assert (
        "RETRIEVED INFORMATION"
        not in system_content
    )


def test_retrieval_metadata_survives_compilation() -> None:
    """
    Retrieval source, identifier, score, and content must
    remain visible after compilation.
    """

    request = ContextRequest(
        user_input="What was found?",
        state=build_state(),
        retrieval_results=[
            RetrievalResult(
                source="memory",
                identifier=777,
                content=(
                    "Important project information."
                ),
                score=0.913,
                metadata={
                    "category": "project",
                    "subject": "architecture",
                },
            )
        ],
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "RETRIEVED INFORMATION"
        in system_content
    )

    assert (
        "[memory]"
        in system_content
    )

    assert (
        "id=777"
        in system_content
    )

    assert (
        "score=0.913"
        in system_content
    )

    assert (
        "Important project information."
        in system_content
    )


def test_failed_operation_result_survives_compilation() -> None:
    """
    Failed operation results must remain visible to the
    LLM-facing Context.
    """

    request = ContextRequest(
        user_input="What failed?",
        state=build_state(),
        operation_results=[
            OperationResult.failure_result(
                operation="memory_get",
                error_code=OperationErrorCode.NOT_FOUND,
                error_message=(
                    "Memory does not exist."
                ),
            )
        ],
    )

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    context = compiler.compile(
        request
    )

    system_content = (
        context
        .as_messages()[0]["content"]
    )

    assert (
        "OPERATION RESULTS"
        in system_content
    )

    assert (
        "[operation=memory_get]"
        in system_content
    )

    assert (
        "status=failure"
        in system_content
    )

    assert (
        "Memory does not exist."
        in system_content
    )


def main() -> None:
    test_all_context_sources_compile()
    test_conversation_is_preserved_as_llm_messages()
    test_context_compilation_is_deterministic()
    test_empty_optional_sources_do_not_create_sections()
    test_retrieval_metadata_survives_compilation()
    test_failed_operation_result_survives_compilation()

    print(
        "R2.10B.10 Context compilation tests passed."
    )


if __name__ == "__main__":
    main()