import pytest

from jarvis.core.reasoning_controller import (
    ReasoningController,
    ReasoningState,
)


def test_start_enters_generating():
    controller = ReasoningController()

    assert controller.state is None

    state = controller.start_generation()

    assert state == ReasoningState.GENERATING
    assert controller.state == ReasoningState.GENERATING


def test_actionable_tool_call_commits():
    controller = ReasoningController()

    controller.start_generation()

    state = controller.observe(
        actionable_tool_call=True
    )

    assert state == ReasoningState.COMMIT
    assert controller.state == ReasoningState.COMMIT


def test_final_answer_completes():
    controller = ReasoningController()

    controller.start_generation()

    state = controller.observe(
        final_answer=True
    )

    assert state == ReasoningState.COMPLETE
    assert controller.state == ReasoningState.COMPLETE


def test_ceiling_aborts():
    controller = ReasoningController()

    controller.start_generation()

    state = controller.observe(
        ceiling_reached=True
    )

    assert state == ReasoningState.ABORT
    assert controller.state == ReasoningState.ABORT


def test_commit_can_start_next_generation():
    controller = ReasoningController()

    controller.start_generation()
    controller.observe(
        actionable_tool_call=True
    )

    assert controller.state == ReasoningState.COMMIT

    state = controller.start_generation()

    assert state == ReasoningState.GENERATING


def test_actionable_tool_call_has_priority_over_final_answer():
    controller = ReasoningController()

    controller.start_generation()

    state = controller.observe(
        actionable_tool_call=True,
        final_answer=True,
    )

    assert state == ReasoningState.COMMIT


def test_cannot_observe_before_generation():
    controller = ReasoningController()

    with pytest.raises(RuntimeError):
        controller.observe(
            final_answer=True
        )


def test_cannot_start_generation_after_completion():
    controller = ReasoningController()

    controller.start_generation()
    controller.observe(
        final_answer=True
    )

    with pytest.raises(RuntimeError):
        controller.start_generation()


def test_cannot_start_generation_after_abort():
    controller = ReasoningController()

    controller.start_generation()
    controller.observe(
        ceiling_reached=True
    )

    with pytest.raises(RuntimeError):
        controller.start_generation()


def test_no_transition_is_not_silently_accepted():
    controller = ReasoningController()

    controller.start_generation()

    with pytest.raises(RuntimeError):
        controller.observe()

def test_commit_continues_when_task_is_unresolved():
    controller = ReasoningController()

    controller.start_generation()

    controller.observe(
        actionable_tool_call=True
    )

    state = controller.continue_after_evidence(
        task_unresolved=True
    )

    assert state == ReasoningState.CONTINUE
    assert controller.state == ReasoningState.CONTINUE


def test_commit_completes_when_task_is_resolved():
    controller = ReasoningController()

    controller.start_generation()

    controller.observe(
        actionable_tool_call=True
    )

    state = controller.continue_after_evidence(
        task_unresolved=False
    )

    assert state == ReasoningState.COMPLETE
    assert controller.state == ReasoningState.COMPLETE


def test_continue_allows_next_generation():
    controller = ReasoningController()

    controller.start_generation()

    controller.observe(
        actionable_tool_call=True
    )

    controller.continue_after_evidence(
        task_unresolved=True
    )

    assert controller.state == ReasoningState.CONTINUE

    state = controller.start_generation()

    assert state == ReasoningState.GENERATING


def test_continue_requires_commit():
    controller = ReasoningController()

    controller.start_generation()

    with pytest.raises(RuntimeError):
        controller.continue_after_evidence(
            task_unresolved=True
        )