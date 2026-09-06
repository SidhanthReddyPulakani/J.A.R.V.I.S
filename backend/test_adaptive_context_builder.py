"""
O2.4 — Adaptive Context Runtime Verification

Verifies that the adaptive context runtime actually applies
the ContextDemandPolicy decision through AdaptiveContextBuilder.

No LLM.
No Ollama.
No retrieval service.
No persistent Agent state.
"""

from dataclasses import dataclass

from jarvis.context import (
    ContextCompiler,
    ContextDemandPolicy,
    ContextRequest,
    ContextWindowManager,
    ContextDepth,
    ContextSource,
)

from jarvis.context.selector import (
    AdaptiveContextBuilder,
)


@dataclass
class FakeState:
    value: str = "test-state"


def build_request():
    return ContextRequest(
        user_input="test request",
        state=FakeState(),
        conversation=[
            {
                "role": "user",
                "content": "previous conversation",
            }
        ],
        core_memory=[
            "core memory",
        ],
        retrieval_results=[
            "retrieved information",
        ],
        diary=[
            "diary event",
        ],
        knowledge=[
            "knowledge item",
        ],
        relationships=[
            "relationship item",
        ],
        operation_results=[
            "operation result",
        ],
        capability_information=[
            "capability information",
        ],
    )


def build_builder():
    return AdaptiveContextBuilder(
        compiler=ContextCompiler(
            system_prompt="Test system prompt."
        ),
        window_manager=ContextWindowManager(),
    )


def test_fast_profile_is_applied_at_runtime():
    state = type(
        "State",
        (),
        {
            "mode": type(
                "Mode",
                (),
                {"value": "fast"},
            )(),
            "phase": type(
                "Phase",
                (),
                {"value": "initial"},
            )(),
            "terminal": False,
            "aborted": False,
        },
    )()

    from jarvis.computation import ComputationMode

    state.mode = ComputationMode.FAST

    signals = type(
        "Signals",
        (),
        {
            "get": lambda self, name: None,
        },
    )()

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.MINIMAL

    context = build_builder().build(
        request=build_request(),
        profile=decision.profile,
    )

    assert context is not None
    assert isinstance(context.messages, list)

    compiled_text = str(context.messages)

    assert "previous conversation" in compiled_text
    assert "retrieved information" in compiled_text
    assert "knowledge item" not in compiled_text
    assert "diary event" not in compiled_text
    assert "relationship item" not in compiled_text


def test_standard_profile_is_applied_at_runtime():
    from jarvis.computation import (
        ComputationMode,
        ComputationState,
        DemandSignals,
    )

    state = ComputationState()
    state.mode = ComputationMode.NORMAL

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=DemandSignals(),
    )

    assert decision.profile.depth == ContextDepth.STANDARD

    context = build_builder().build(
        request=build_request(),
        profile=decision.profile,
    )

    assert context is not None

    compiled_text = str(context.messages)

    assert "previous conversation" in compiled_text
    assert "retrieved information" in compiled_text
    assert "core memory" in compiled_text
    assert "diary event" in compiled_text
    assert "operation result" in compiled_text


def test_expanded_profile_is_applied_at_runtime():
    from jarvis.computation import (
        ComputationMode,
        ComputationState,
        DemandSignal,
        DemandSignalStatus,
        DemandSignals,
    )

    state = ComputationState()
    state.mode = ComputationMode.NORMAL

    signals = DemandSignals(
        missing_information=DemandSignal(
            name="missing_information",
            value=0.9,
            status=DemandSignalStatus.AVAILABLE,
        )
    )

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=signals,
    )

    assert decision.profile.depth == ContextDepth.EXPANDED

    context = build_builder().build(
        request=build_request(),
        profile=decision.profile,
    )

    assert context is not None

    compiled_text = str(context.messages)

    assert "previous conversation" in compiled_text
    assert "retrieved information" in compiled_text
    assert "core memory" in compiled_text
    assert "diary event" in compiled_text
    assert "knowledge item" in compiled_text
    assert "relationship item" in compiled_text
    assert "operation result" in compiled_text
    assert "capability information" in compiled_text


def test_runtime_selection_changes_with_demand():
    from jarvis.computation import (
        ComputationMode,
        ComputationState,
        DemandSignal,
        DemandSignalStatus,
        DemandSignals,
    )

    builder = build_builder()

    state = ComputationState()
    state.mode = ComputationMode.FAST

    low_demand = DemandSignals()

    low_decision = ContextDemandPolicy().decide(
        state=state,
        signals=low_demand,
    )

    low_context = builder.build(
        request=build_request(),
        profile=low_decision.profile,
    )

    state.mode = ComputationMode.NORMAL

    high_demand = DemandSignals(
        missing_information=DemandSignal(
            name="missing_information",
            value=0.9,
            status=DemandSignalStatus.AVAILABLE,
        )
    )

    high_decision = ContextDemandPolicy().decide(
        state=state,
        signals=high_demand,
    )

    high_context = builder.build(
        request=build_request(),
        profile=high_decision.profile,
    )

    assert low_decision.profile.depth == ContextDepth.MINIMAL
    assert high_decision.profile.depth == ContextDepth.EXPANDED

    low_text = str(low_context.messages)
    high_text = str(high_context.messages)

    assert "knowledge item" not in low_text
    assert "knowledge item" in high_text

    assert "relationship item" not in low_text
    assert "relationship item" in high_text


def test_context_window_is_still_applied_after_selection():
    from jarvis.computation import (
        ComputationMode,
        ComputationState,
        DemandSignals,
    )

    state = ComputationState()
    state.mode = ComputationMode.NORMAL

    decision = ContextDemandPolicy().decide(
        state=state,
        signals=DemandSignals(),
    )

    builder = build_builder()

    context = builder.build(
        request=build_request(),
        profile=decision.profile,
    )

    assert context is not None
    assert context.messages

