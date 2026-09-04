from jarvis.core.reasoning_controller import (
    ReasoningController,
    ReasoningState,
)
from jarvis.core.stagnation_detector import (
    StagnationDetector,
)


def test_dummy_stagnation_triggers_intervention():
    detector = StagnationDetector(
        window_size=3
    )

    controller = ReasoningController()

    # First generation cycle
    controller.start_generation()

    observation_1 = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=True,
    )

    assert observation_1.stagnant is False

    controller.observe(
        actionable_tool_call=True
    )

    controller.continue_after_evidence(
        task_unresolved=True
    )

    # Second generation cycle
    controller.start_generation()

    observation_2 = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=False,
    )

    assert observation_2.stagnant is True
    assert observation_2.repeated_content is True
    assert observation_2.repeated_tool_intent is True
    assert observation_2.no_new_action_information is True

    # Intervention must happen before normal tool execution
    state = controller.intervene()

    assert state == ReasoningState.INTERVENE
    assert controller.intervention_count == 1

def test_dummy_second_stagnation_aborts():
    detector = StagnationDetector(
        window_size=3
    )

    controller = ReasoningController()

    # --------------------------------------------------
    # First generation
    # --------------------------------------------------

    controller.start_generation()

    detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=True,
    )

    controller.observe(
        actionable_tool_call=True
    )

    controller.continue_after_evidence(
        task_unresolved=True
    )

    # --------------------------------------------------
    # First intervention
    # --------------------------------------------------

    controller.start_generation()

    observation = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=False,
    )

    assert observation.stagnant is True

    state = controller.intervene()

    assert state == ReasoningState.INTERVENE
    assert controller.intervention_count == 1

    # --------------------------------------------------
    # Simulate the intervention being consumed.
    #
    # The controller must return to GENERATING before
    # another reasoning cycle can begin.
    # --------------------------------------------------

    controller.start_generation()

    # --------------------------------------------------
    # Second intervention attempt.
    # --------------------------------------------------

    detector.reset()

    observation = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=False,
    )

    # With a reset window, the first observation alone
    # cannot be considered stagnant.
    #
    # Add the repeated observation.
    observation = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:[('query', 'WhatsApp')]",
        ),
        new_action_information=False,
    )

    assert observation.stagnant is True

    # The one allowed intervention has already been used.
    # The second attempt must abort.
    state = controller.intervene()

    assert state == ReasoningState.ABORT
    assert controller.intervention_count == 1