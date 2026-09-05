"""
O1.4 — Computation Controller Integration Verification

Run from:
    backend/

Command:
    python test_computation_controller_integration.py

Purpose
-------
Verify the O1 computation layer independently of Ollama/Qwen.

This test validates:
    - INITIAL decision
    - CONTINUE
    - ESCALATE
    - DEESCALATE
    - FINISH
    - ABORT
    - mode persistence across decisions
    - terminal/aborted state
    - reasoning-step tracking
    - controller lifecycle boundaries

No LLM calls are made.
No production state, memory, knowledge, or capability services are used.
"""

from __future__ import annotations

import sys

from jarvis.computation import (
    ComputationAction,
    ComputationMode,
    ComputationPhase,
    ComputationState,
    DemandSignal,
    DemandSignalStatus,
    DemandSignals,
)
from jarvis.computation.controller import ComputationController

# ============================================================
# TEST HELPERS
# ============================================================

def available(name: str, value) -> DemandSignal:
    return DemandSignal(
        name=name,
        value=value,
        status=DemandSignalStatus.AVAILABLE,
    )


def signals(**values) -> DemandSignals:
    return DemandSignals(
        **{
            name: available(name, value)
            for name, value in values.items()
        }
    )

def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(
            f"{message}\n"
            f"Expected: {expected!r}\n"
            f"Actual:   {actual!r}"
        )


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def assert_false(value: bool, message: str) -> None:
    if value:
        raise AssertionError(message)


# ============================================================
# TEST 1 — INITIAL
# ============================================================

def test_initial_decision() -> None:
    controller = ComputationController()
    state = ComputationState()

    decision = controller.initial(
        state=state,
        signals=signals(
            goal_resolution=0.0,
            goal_progress=0.0,
            unresolved_requirements=0,
        ),
    )

    assert_equal(
        state.phase,
        ComputationPhase.INITIAL,
        "Initial evaluation must set INITIAL phase.",
    )

    assert_false(
        decision.terminal,
        "Initial non-terminal demand must not terminate.",
    )

    assert_equal(
        state.last_decision,
        decision,
        "Controller decision must be recorded in state.",
    )


# ============================================================
# TEST 2 — CONTINUE
# ============================================================

def test_continue_preserves_mode() -> None:
    controller = ComputationController()
    state = ComputationState(
        mode=ComputationMode.NORMAL
    )

    decision = controller.pre_llm(
        state=state,
        signals=signals(
            goal_progress=0.5,
            unresolved_requirements=1,
            information_sufficiency=0.8,
            evidence_sufficiency=0.5,
            intent_ambiguity=0.0,
            action_ambiguity=0.0,
            target_ambiguity=0.0,
        ),
    )

    assert_equal(
        decision.action,
        ComputationAction.CONTINUE,
        "Moderate/stable demand should continue.",
    )

    assert_equal(
        state.mode,
        ComputationMode.NORMAL,
        "CONTINUE must preserve the current computation mode.",
    )

    assert_false(
        state.terminal,
        "CONTINUE must not terminate.",
    )


# ============================================================
# TEST 3 — ESCALATE
# ============================================================

def test_escalation() -> None:
    controller = ComputationController()
    state = ComputationState(
        mode=ComputationMode.FAST
    )

    decision = controller.pre_llm(
        state=state,
        signals=signals(
            intent_ambiguity=1.0,
            action_ambiguity=1.0,
            target_ambiguity=1.0,
            information_sufficiency=0.0,
            evidence_sufficiency=0.5,
            evidence_conflict=True,
        ),
    )

    assert_equal(
        decision.action,
        ComputationAction.ESCALATE,
        "High demand from FAST must escalate.",
    )

    assert_true(
        state.mode != ComputationMode.FAST,
        "ESCALATE must change the computation mode.",
    )

    assert_true(
        state.escalation_count >= 1,
        "ESCALATE must increment escalation_count.",
    )

    assert_true(
        state.transition_count >= 1,
        "ESCALATE must record a mode transition.",
    )


# ============================================================
# TEST 4 — DEESCALATE
# ============================================================

def test_deescalation() -> None:
    controller = ComputationController()
    state = ComputationState(
        mode=ComputationMode.DEEP
    )

    decision = controller.pre_llm(
        state=state,
        signals=signals(
            goal_resolution=1.0,
            goal_progress=1.0,
            unresolved_requirements=0,
            information_sufficiency=1.0,
            evidence_sufficiency=1.0,
            intent_ambiguity=0.0,
            action_ambiguity=0.0,
            target_ambiguity=0.0,
            evidence_conflict=False,
            decision_instability=False,
        ),
    )

    assert_equal(
        decision.action,
        ComputationAction.DEESCALATE,
        "Low demand from DEEP should de-escalate.",
    )

    assert_equal(
        state.mode,
        ComputationMode.NORMAL,
        "DEESCALATE from DEEP must move to NORMAL.",
    )

    assert_true(
        state.deescalation_count >= 1,
        "DEESCALATE must increment deescalation_count.",
    )


# ============================================================
# TEST 5 — FINISH
# ============================================================

def test_finish_is_terminal() -> None:
    controller = ComputationController()
    state = ComputationState()

    decision = controller.post_llm(
        state=state,
        signals=signals(
            goal_resolution=True,
            goal_progress=1.0,
            unresolved_requirements=0,
        ),
    )

    assert_equal(
        decision.action,
        ComputationAction.FINISH,
        "Resolved goal must produce FINISH.",
    )

    assert_true(
        decision.terminal,
        "FINISH must be terminal.",
    )

    assert_true(
        state.terminal,
        "FINISH must mark ComputationState terminal.",
    )

    assert_false(
        state.aborted,
        "FINISH must not mark the computation aborted.",
    )


# ============================================================
# TEST 6 — ABORT
# ============================================================

def test_abort_is_terminal_and_aborted() -> None:
    controller = ComputationController()
    state = ComputationState()

    # Force the hard safety condition through reasoning_step.
    # O1.4 verifies that the controller recognizes the safety
    # boundary rather than requiring an LLM/runtime call.
    state.reasoning_step = 10

    decision = controller.pre_llm(
        state=state,
        signals=signals(
            goal_progress=0.0,
            unresolved_requirements=5,
            information_sufficiency=0.0,
        ),
    )

    assert_equal(
        decision.action,
        ComputationAction.ABORT,
        "Hard reasoning boundary must produce ABORT.",
    )

    assert_true(
        decision.terminal,
        "ABORT must be terminal.",
    )

    assert_true(
        state.terminal,
        "ABORT must mark state terminal.",
    )

    assert_true(
        state.aborted,
        "ABORT must mark state aborted.",
    )


# ============================================================
# TEST 7 — MODE PERSISTENCE
# ============================================================

def test_mode_persists_across_boundaries() -> None:
    controller = ComputationController()
    state = ComputationState(
        mode=ComputationMode.FAST
    )

    first = controller.pre_llm(
        state=state,
        signals=signals(
            intent_ambiguity=1.0,
            action_ambiguity=1.0,
            target_ambiguity=1.0,
            evidence_conflict=True,
        ),
    )

    assert_equal(
        first.action,
        ComputationAction.ESCALATE,
        "First boundary should escalate.",
    )

    escalated_mode = state.mode

    second = controller.post_llm(
        state=state,
        signals=signals(
            goal_progress=0.5,
            unresolved_requirements=1,
            information_sufficiency=0.7,
            intent_ambiguity=0.0,
            action_ambiguity=0.0,
            target_ambiguity=0.0,
        ),
    )

    assert_false(
        second.terminal,
        "A continuing cycle must remain non-terminal.",
    )

    assert_equal(
        state.mode,
        ComputationMode.NORMAL,
        "Low demand after escalation should de-escalate DEEP to NORMAL.",
    )


# ============================================================
# TEST 8 — REASONING STEP TRACKING
# ============================================================

def test_reasoning_step_tracking() -> None:
    state = ComputationState()

    assert_equal(
        state.reasoning_step,
        0,
        "Reasoning must start at step zero.",
    )

    state.advance_reasoning_step()
    state.advance_reasoning_step()

    assert_equal(
        state.reasoning_step,
        2,
        "Reasoning-step counter must advance deterministically.",
    )


# ============================================================
# TEST 9 — PHASE LIFECYCLE
# ============================================================

def test_phase_lifecycle() -> None:
    controller = ComputationController()
    state = ComputationState()

    controller.initial(
        state=state,
        signals=signals(
            goal_progress=0.0,
            unresolved_requirements=1,
        ),
    )
    assert_equal(
        state.phase,
        ComputationPhase.INITIAL,
        "Initial boundary must record INITIAL.",
    )

    controller.pre_llm(
        state=state,
        signals=signals(
            goal_progress=0.2,
            unresolved_requirements=1,
        ),
    )
    assert_equal(
        state.phase,
        ComputationPhase.PRE_LLM,
        "Pre-LLM boundary must record PRE_LLM.",
    )

    controller.post_llm(
        state=state,
        signals=signals(
            goal_progress=0.5,
            unresolved_requirements=1,
        ),
    )
    assert_equal(
        state.phase,
        ComputationPhase.POST_LLM,
        "Post-LLM boundary must record POST_LLM.",
    )


# ============================================================
# RUNNER
# ============================================================

TESTS = [
    test_initial_decision,
    test_continue_preserves_mode,
    test_escalation,
    test_deescalation,
    test_finish_is_terminal,
    test_abort_is_terminal_and_aborted,
    test_mode_persists_across_boundaries,
    test_reasoning_step_tracking,
    test_phase_lifecycle,
]


def main() -> None:
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print("=" * 72)
    print("JARVIS — O1.4 COMPUTATION CONTROLLER VERIFICATION")
    print("=" * 72)
    print()
    print("No Ollama calls.")
    print("No Qwen calls.")
    print("No external services.")
    print()

    passed = 0

    for test in TESTS:
        name = test.__name__

        try:
            test()
        except Exception as exc:
            print(f"[FAIL] {name}")
            print(f"       {type(exc).__name__}: {exc}")
            raise

        print(f"[PASS] {name}")
        passed += 1

    print()
    print("=" * 72)
    print("O1.4 VERIFICATION COMPLETE")
    print("=" * 72)
    print(f"Passed: {passed}/{len(TESTS)}")
    print()
    print("Computation controller lifecycle is verified independently")
    print("of the LLM/runtime layer.")


if __name__ == "__main__":
    main()
