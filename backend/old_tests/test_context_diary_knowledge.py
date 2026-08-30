"""
R2.10B.5 + R2.10B.6

Diary and Knowledge -> Context integration tests.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.storage.repositories.agent_state import (
    AgentStateRepository,
)

from jarvis.context import (
    ContextCompiler,
    ContextRequest,
)
from jarvis.diary.service import (
    DiaryService,
)
from jarvis.knowledge import (
    KnowledgeService,
)
from jarvis.retrieval import (
    KnowledgeProvider,
    RetrievalService,
    RetrievalResult,
)
from jarvis.state.models import (
    AgentState,
)
from jarvis.storage.database import (
    Database,
)
from jarvis.storage.repositories.diary import (
    DiaryRepository,
)
from jarvis.storage.repositories.knowledge import (
    KnowledgeRepository,
)


SYSTEM_PROMPT = "You are Jarvis."


def _build_state(
    agent_id: str,
) -> AgentState:

    return AgentState(
        agent_id=agent_id,
        conversation_id=None,
        current_task=None,
        current_goal=None,
        mode="testing",
        active_project="Jarvis",
        active_operation=None,
        operation_status="idle",
    )


def test_diary_reaches_context() -> None:
    """
    Diary events supplied through ContextRequest.diary
    must appear in compiled context.
    """

    with TemporaryDirectory() as temp_dir:

        database = Database(
            Path(temp_dir)
            / "diary_context.db"
        )

        database.initialize()
        state = _build_state(
            "agent-diary"
        )

        AgentStateRepository(
            database
        ).save(state)

        diary = DiaryService(
            DiaryRepository(
                database
            ),
            agent_id="agent-diary",
        )

        event = diary.record(
            event_type="interaction",
            description=(
                "User asked Jarvis to preserve "
                "the current architecture."
            ),
            source="test",
        )

        assert event.id is not None

        compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        request = ContextRequest(
            user_input="architecture",
            state=_build_state(
                "agent-diary"
            ),
            diary=[event],
        )

        context = compiler.compile(
            request
        )

        content = (
            context
            .as_messages()[0]["content"]
        )

        assert "DIARY" in content

        assert (
            "User asked Jarvis to preserve"
            in content
        )

        assert (
            "[diary]"
            in content
        )

        assert (
            f"id={event.id}"
            in content
        )


def test_diary_is_optional() -> None:
    """
    Empty Diary must not create a Diary section.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    request = ContextRequest(
        user_input="hello",
        state=_build_state(
            "agent-diary-empty"
        ),
        diary=[],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "DIARY" not in content


def test_knowledge_reaches_context_through_retrieval() -> None:
    """
    Knowledge retrieved through KnowledgeProvider must
    reach Context through the unified retrieval surface.
    """

    with TemporaryDirectory() as temp_dir:

        database = Database(
            Path(temp_dir)
            / "knowledge_context.db"
        )

        database.initialize()

        knowledge = KnowledgeService(
            KnowledgeRepository(
                database
            )
        )

        source = knowledge.create_source(
            name="R2.10 test source",
            source_type="manual",
            origin="test",
        )

        document = knowledge.create_document(
            source_id=source.id,
            title="Jarvis Architecture",
        )

        passage = knowledge.create_passage(
            document_id=document.id,
            sequence=0,
            content=(
                "Jarvis separates State, Memory, "
                "Knowledge, Retrieval, and Context."
            ),
        )

        assert passage.id is not None

        retrieval = RetrievalService(
            providers=[
                KnowledgeProvider(
                    knowledge_service=knowledge,
                )
            ]
        )

        results = retrieval.search(
            "State Memory Knowledge Context",
            sources=["knowledge"],
            limit=10,
        )

        assert results

        assert all(
            result.source == "knowledge"
            for result in results
        )

        compiler = ContextCompiler(
            system_prompt=SYSTEM_PROMPT
        )

        request = ContextRequest(
            user_input=(
                "Explain the architecture."
            ),
            state=_build_state(
                "agent-knowledge"
            ),
            retrieval_results=results,
        )

        context = compiler.compile(
            request
        )

        content = (
            context
            .as_messages()[0]["content"]
        )

        assert (
            "RETRIEVED INFORMATION"
            in content
        )

        assert (
            "[knowledge]"
            in content
        )

        assert (
            f"id={passage.id}"
            in content
        )

        assert (
            "Jarvis separates State, Memory"
            in content
        )


def test_diary_and_knowledge_remain_distinct() -> None:
    """
    Diary is rendered through its explicit Context slot,
    while retrieved Knowledge remains part of unified
    Retrieval results.
    """

    compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    diary_event = type(
        "DiaryEvent",
        (),
        {
            "id": 7,
            "event_type": "interaction",
            "description": (
                "Jarvis discussed the architecture."
            ),
            "source": "test",
            "created_at": (
                "2026-08-29T00:00:00+00:00"
            ),
        },
    )()

    knowledge_result = RetrievalResult(
        source="knowledge",
        identifier=11,
        content=(
            "The architecture separates "
            "State and Knowledge."
        ),
        score=0.91,
    )

    request = ContextRequest(
        user_input="architecture",
        state=_build_state(
            "agent-distinction"
        ),
        diary=[diary_event],
        retrieval_results=[
            knowledge_result
        ],
    )

    context = compiler.compile(
        request
    )

    content = (
        context
        .as_messages()[0]["content"]
    )

    assert "DIARY" in content
    assert "Jarvis discussed the architecture." in content

    assert "RETRIEVED INFORMATION" in content
    assert (
        "The architecture separates State and Knowledge."
        in content
    )

    assert "[diary]" in content
    assert "[knowledge]" in content


def main() -> None:

    test_diary_reaches_context()
    test_diary_is_optional()
    test_knowledge_reaches_context_through_retrieval()
    test_diary_and_knowledge_remain_distinct()

    print(
        "R2.10B.5 + R2.10B.6 "
        "Diary/Knowledge context tests passed."
    )


if __name__ == "__main__":
    main()