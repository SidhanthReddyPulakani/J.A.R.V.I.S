from jarvis.core.reasoning_observer import (
    ReasoningObserver,
)


def test_empty_reasoning_is_not_ready():
    observer = ReasoningObserver()

    result = observer.observe(
        thinking="",
        elapsed_ms=10.0,
    )

    assert result.total_chars == 0
    assert result.new_chars == 0
    assert result.commit_readiness is False


def test_actionable_reasoning_becomes_ready():
    observer = ReasoningObserver(
        min_reasoning_chars=50,
    )

    result = observer.observe(
        thinking=(
            "The user wants me to open WhatsApp. "
            "I should use the apps.launch tool "
            "with WhatsApp as the query."
        ),
        elapsed_ms=2500.0,
    )

    assert result.action_signal > 0.0
    assert result.commit_readiness is True


def test_uncertainty_blocks_readiness():
    observer = ReasoningObserver(
        min_reasoning_chars=50,
    )

    result = observer.observe(
        thinking=(
            "The user wants me to open WhatsApp. "
            "Maybe WhatsApp is installed, but "
            "I need to make sure before deciding "
            "which application to launch."
        ),
        elapsed_ms=2500.0,
    )

    assert result.action_signal > 0.0
    assert result.uncertainty_signal > 0.0
    assert result.commit_readiness is False


def test_incremental_reasoning_tracks_new_text():
    observer = ReasoningObserver(
        min_reasoning_chars=10,
    )

    first = observer.observe(
        thinking="The user wants to open WhatsApp.",
        elapsed_ms=1000.0,
    )

    second = observer.observe(
        thinking=(
            "The user wants to open WhatsApp. "
            "I should use the launch tool."
        ),
        elapsed_ms=1500.0,
    )

    assert first.new_chars == first.total_chars
    assert second.new_chars > 0
    assert second.total_chars > first.total_chars


def test_reset_clears_previous_reasoning():
    observer = ReasoningObserver()

    observer.observe(
        thinking="The user wants to open WhatsApp.",
        elapsed_ms=1000.0,
    )

    observer.reset()

    result = observer.observe(
        thinking="Use the launch tool.",
        elapsed_ms=2000.0,
    )

    assert result.new_chars == result.total_chars