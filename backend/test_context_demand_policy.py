from jarvis.computation import (
    ComputationState,
    DemandSignal,
    DemandSignalStatus,
    DemandSignals,
)

from jarvis.context import (
    ContextDemandPolicy,
    ContextDepth,
)


def available(name, value):
    return DemandSignal(
        name=name,
        value=value,
        status=DemandSignalStatus.AVAILABLE,
    )


def test_fast_mode_selects_minimal_context():
    state = ComputationState()
    state.mode = state.mode.__class__.FAST
    signals = DemandSignals()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.MINIMAL


def test_normal_mode_selects_standard_context():
    state = ComputationState()
    state.mode = state.mode.__class__.NORMAL

    signals = DemandSignals()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.STANDARD


def test_deep_mode_selects_expanded_context():
    state = ComputationState()
    state.mode = state.mode.__class__.DEEP

    signals = DemandSignals()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED


def test_high_information_demand_expands_context():
    state = ComputationState()

    signals = DemandSignals(
        missing_information=available("missing_information", 0.9),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED


def test_low_information_sufficiency_expands_context():
    state = ComputationState()

    signals = DemandSignals(
        information_sufficiency=available(
            "information_sufficiency",
            0.1,
        )
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED


def test_evidence_conflict_expands_context():
    state = ComputationState()

    signals = DemandSignals(
        evidence_conflict=available("evidence_conflict", 0.9),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED


def test_ambiguity_expands_context():
    state = ComputationState()

    signals = DemandSignals(
        intent_ambiguity=available("intent_ambiguity", 0.9),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED


def test_reasoning_repetition_requests_standard_context():
    state = ComputationState()

    signals = DemandSignals(    
    reasoning_repetition=available("reasoning_repetition", 0.9),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.STANDARD


def test_unknown_signals_do_not_force_expansion():
    state = ComputationState()
    state.mode = state.mode.__class__.FAST
    signals = DemandSignals()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.MINIMAL


def test_terminal_state_uses_minimal_context():
    state = ComputationState()
    state.terminal = True

    signals = DemandSignals(
        missing_information=available("missing_information", 1.0),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.MINIMAL


def test_aborted_state_uses_minimal_context():
    state = ComputationState()
    state.aborted = True

    signals = DemandSignals(
        missing_information=available("missing_information", 1.0),
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.MINIMAL


def test_decision_contains_reason():
    state = ComputationState()
    signals = DemandSignals()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert isinstance(decision.reason, str)
    assert decision.reason