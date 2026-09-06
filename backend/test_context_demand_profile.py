"""
O2.1 — Context Demand Profile Verification

These tests verify only the model-independent context-demand
contract.

No LLM.
No Ollama.
No retrieval service.
No persistent JARVIS state.
No context compilation.
"""

from jarvis.context.demand import (
    ContextDepth,
    ContextPriority,
    ContextSource,
    ContextSourceDemand,
    ContextDemandProfile,
)


def test_profile_construction():
    profile = ContextDemandProfile(
        depth=ContextDepth.STANDARD,
        sources={
            ContextSource.CURRENT_STATE: ContextSourceDemand(
                priority=ContextPriority.REQUIRED,
            ),
            ContextSource.RETRIEVAL: ContextSourceDemand(
                priority=ContextPriority.HIGH,
                budget=1000,
            ),
        },
    )

    assert profile.depth == ContextDepth.STANDARD

    assert (
        profile.priority_for(ContextSource.CURRENT_STATE)
        == ContextPriority.REQUIRED
    )

    assert (
        profile.priority_for(ContextSource.RETRIEVAL)
        == ContextPriority.HIGH
    )

    assert (
        profile.budget_for(ContextSource.RETRIEVAL)
        == 1000
    )


def test_depth_levels():
    assert ContextDepth.MINIMAL.value == "minimal"
    assert ContextDepth.STANDARD.value == "standard"
    assert ContextDepth.EXPANDED.value == "expanded"


def test_source_priorities():
    profile = ContextDemandProfile(
        sources={
            ContextSource.CURRENT_STATE: ContextSourceDemand(
                priority=ContextPriority.REQUIRED,
            ),
            ContextSource.CONVERSATION: ContextSourceDemand(
                priority=ContextPriority.HIGH,
            ),
            ContextSource.DIARY: ContextSourceDemand(
                priority=ContextPriority.LOW,
            ),
            ContextSource.KNOWLEDGE: ContextSourceDemand(
                priority=ContextPriority.EXCLUDED,
            ),
        },
    )

    assert profile.is_required(
        ContextSource.CURRENT_STATE
    )

    assert (
        profile.priority_for(ContextSource.CONVERSATION)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.DIARY)
        == ContextPriority.LOW
    )

    assert profile.is_excluded(
        ContextSource.KNOWLEDGE
    )


def test_budget_is_desired_not_enforcement():
    profile = ContextDemandProfile(
        sources={
            ContextSource.RETRIEVAL: ContextSourceDemand(
                priority=ContextPriority.HIGH,
                budget=2048,
            ),
        },
    )

    assert profile.budget_for(
        ContextSource.RETRIEVAL
    ) == 2048


def test_unspecified_source_has_safe_default():
    profile = ContextDemandProfile()

    demand = profile.demand_for(
        ContextSource.RELATIONSHIPS
    )

    assert demand.priority == ContextPriority.MEDIUM
    assert demand.budget is None


def test_minimal_profile():
    profile = ContextDemandProfile.minimal()

    assert profile.depth == ContextDepth.MINIMAL

    assert profile.is_required(
        ContextSource.CURRENT_STATE
    )

    assert (
        profile.priority_for(ContextSource.CONVERSATION)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.RETRIEVAL)
        == ContextPriority.HIGH
    )

    assert profile.is_excluded(
        ContextSource.MEMORY
    )

    assert profile.is_excluded(
        ContextSource.KNOWLEDGE
    )

    assert profile.is_excluded(
        ContextSource.DIARY
    )


def test_standard_profile():
    profile = ContextDemandProfile.standard()

    assert profile.depth == ContextDepth.STANDARD

    assert profile.is_required(
        ContextSource.CURRENT_STATE
    )

    assert (
        profile.priority_for(ContextSource.CORE_MEMORY)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.RETRIEVAL)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.OPERATION_RESULTS)
        == ContextPriority.HIGH
    )


def test_expanded_profile():
    profile = ContextDemandProfile.expanded()

    assert profile.depth == ContextDepth.EXPANDED

    assert profile.is_required(
        ContextSource.CURRENT_STATE
    )

    assert (
        profile.priority_for(ContextSource.MEMORY)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.KNOWLEDGE)
        == ContextPriority.HIGH
    )

    assert (
        profile.priority_for(ContextSource.RETRIEVAL)
        == ContextPriority.HIGH
    )


def test_profiles_are_independent():
    minimal = ContextDemandProfile.minimal()
    standard = ContextDemandProfile.standard()

    assert minimal.depth != standard.depth

    minimal_updated = minimal.with_source(
        ContextSource.DIARY,
        ContextSourceDemand(
            priority=ContextPriority.HIGH,
        ),
    )

    assert minimal.is_excluded(
        ContextSource.DIARY
    )

    assert (
        minimal_updated.priority_for(ContextSource.DIARY)
        == ContextPriority.HIGH
    )

    assert standard.priority_for(
        ContextSource.DIARY
    ) == ContextPriority.MEDIUM


def test_profile_is_immutable():
    profile = ContextDemandProfile.standard()

    try:
        profile.depth = ContextDepth.MINIMAL
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "ContextDemandProfile must be immutable."
        )


def test_negative_budget_rejected():
    try:
        ContextSourceDemand(
            priority=ContextPriority.HIGH,
            budget=-1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Negative context budgets must be rejected."
        )


def test_excluded_source_cannot_have_positive_budget():
    try:
        ContextSourceDemand(
            priority=ContextPriority.EXCLUDED,
            budget=100,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Excluded sources cannot have positive budgets."
        )


def test_no_runtime_dependency():
    """
    This test is intentionally simple: importing and constructing
    the profile must not require Ollama, an LLM, or external services.
    """

    profile = ContextDemandProfile.minimal()

    assert profile is not None