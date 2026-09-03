import pytest

from jarvis.core.stagnation_detector import (
    StagnationDetector,
)


def test_repeated_content_is_detected():
    detector = StagnationDetector()

    detector.observe(
        content="I need to check the application."
    )

    observation = detector.observe(
        content="I need to check the application."
    )

    assert observation.repeated_content is True


def test_different_content_is_not_repetition():
    detector = StagnationDetector()

    detector.observe(
        content="I need to check the application."
    )

    observation = detector.observe(
        content="I found the application."
    )

    assert observation.repeated_content is False


def test_repeated_tool_intent_is_detected():
    detector = StagnationDetector()

    detector.observe(
        tool_intents=("apps.launch",)
    )

    observation = detector.observe(
        tool_intents=("apps.launch",)
    )

    assert observation.repeated_tool_intent is True


def test_new_action_information_is_progress():
    detector = StagnationDetector()

    observation = detector.observe(
        content="Opening WhatsApp.",
        tool_intents=("apps.launch",),
        new_action_information=True,
    )

    assert observation.no_new_action_information is False


def test_multiple_stagnation_signals_trigger_stagnation():
    detector = StagnationDetector()

    detector.observe(
        content="I need to check WhatsApp.",
        tool_intents=("apps.launch",),
        new_action_information=False,
    )

    observation = detector.observe(
        content="I need to check WhatsApp.",
        tool_intents=("apps.launch",),
        new_action_information=False,
    )

    assert observation.stagnant is True


def test_single_signal_does_not_trigger_stagnation():
    detector = StagnationDetector()

    detector.observe(
        content="Thinking about the request."
    )

    observation = detector.observe(
        content="Thinking about the request."
    )

    assert observation.repeated_content is True
    assert observation.stagnant is False


def test_reset_clears_window():
    detector = StagnationDetector()

    detector.observe(
        content="same content"
    )

    detector.reset()

    observation = detector.observe(
        content="same content"
    )

    assert observation.repeated_content is False


def test_invalid_window_size():
    with pytest.raises(ValueError):
        StagnationDetector(window_size=1)