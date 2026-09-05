from __future__ import annotations

from jarvis.computation.decision import (
    ComputationAction,
    ComputationDecision,
)
from jarvis.computation.profile import ComputationMode
from jarvis.computation.signals import (
    DemandSignalStatus,
    DemandSignals,
)
from jarvis.computation.state import ComputationPhase, ComputationState


class ComputationPolicy:
    """
    Deterministic policy for adaptive computation.

    The policy observes the current computation state and
    demand signals, then decides how computation should
    proceed.

    It does not execute LLM calls, tools, capabilities,
    retrieval, or context assembly.
    """

    # Signals strong enough to justify escalation by themselves.
    STRONG_ESCALATION_SIGNALS = frozenset(
        {
            "evidence_conflict",
            "decision_instability",
            "tool_execution_status",
        }
    )

    # Moderate signals that become meaningful in combination.
    MODERATE_ESCALATION_SIGNALS = frozenset(
        {
            "intent_ambiguity",
            "action_ambiguity",
            "target_ambiguity",
            "missing_information",
            "evidence_sufficiency",
            "tool_failure_count",
            "operation_repetition",
            "tool_dependency_depth",
            "reasoning_repetition",
            "reasoning_progress",
        }
    )

    def evaluate(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:
        """
        Evaluate the current computation boundary.

        The returned decision describes what should happen next.
        """

        if state.terminal:
            return self._finish(
                state,
                reason="Computation is already terminal.",
            )

        if self._hard_abort_required(
            state,
            signals,
        ):
            return self._abort(
                state,
                reason="A hard computation boundary requires termination.",
            )

        if self._goal_resolved(signals):
            return self._finish(
                state,
                reason="The current goal is resolved.",
            )

        if state.phase == ComputationPhase.COMPLETION:
            return self._finish(
                state,
                reason="Computation reached the completion boundary.",
            )

        if state.phase == ComputationPhase.INITIAL:
            return self._initial_decision(
                state,
                signals,
            )

        if state.mode == ComputationMode.FAST:
            return self._evaluate_fast(
                state,
                signals,
            )

        if state.mode == ComputationMode.NORMAL:
            return self._evaluate_normal(
                state,
                signals,
            )

        return self._evaluate_deep(
            state,
            signals,
        )

    # ==========================================================
    # INITIAL
    # ==========================================================

    def _initial_decision(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        demand = self._demand_level(signals)

        if demand == "high":
            return ComputationDecision(
                action=ComputationAction.CONTINUE,
                current_mode=state.mode,
                next_mode=ComputationMode.DEEP,
                reason="Initial demand is high.",
                signals_used=self._available_signal_names(
                    signals
                ),
            )

        if demand == "moderate":
            return ComputationDecision(
                action=ComputationAction.CONTINUE,
                current_mode=state.mode,
                next_mode=ComputationMode.NORMAL,
                reason="Initial demand is moderate.",
                signals_used=self._available_signal_names(
                    signals
                ),
            )

        return ComputationDecision(
            action=ComputationAction.CONTINUE,
            current_mode=state.mode,
            next_mode=ComputationMode.FAST,
            reason="Initial demand appears low.",
            signals_used=self._available_signal_names(
                signals
            ),
        )

    # ==========================================================
    # FAST
    # ==========================================================

    def _evaluate_fast(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        if self._high_demand(signals):
            return self._escalate(
                state,
                ComputationMode.DEEP,
                signals,
                "High demand detected while operating in FAST mode.",
            )

        if self._moderate_demand(signals):
            return self._escalate(
                state,
                ComputationMode.NORMAL,
                signals,
                "Moderate demand detected while operating in FAST mode.",
            )

        return self._continue(
            state,
            ComputationMode.FAST,
            signals,
            "Demand remains low.",
        )

    # ==========================================================
    # NORMAL
    # ==========================================================

    def _evaluate_normal(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        if self._high_demand(signals):
            return self._escalate(
                state,
                ComputationMode.DEEP,
                signals,
                "High demand detected while operating in NORMAL mode.",
            )

        if self._low_demand(signals):
            return self._deescalate(
                state,
                ComputationMode.FAST,
                signals,
                "Demand has decreased sufficiently for FAST mode.",
            )

        return self._continue(
            state,
            ComputationMode.NORMAL,
            signals,
            "Demand remains appropriate for NORMAL mode.",
        )

    # ==========================================================
    # DEEP
    # ==========================================================

    def _evaluate_deep(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        if self._low_demand(signals):
            return self._deescalate(
                state,
                ComputationMode.NORMAL,
                signals,
                "Demand has decreased sufficiently for NORMAL mode.",
            )

        return self._continue(
            state,
            ComputationMode.DEEP,
            signals,
            "Demand still justifies DEEP mode.",
        )

    # ==========================================================
    # Demand evaluation
    # ==========================================================

    def _demand_level(
        self,
        signals: DemandSignals,
    ) -> str:
        """
        Classify observed demand into low, moderate, or high.

        This is deliberately deterministic and inexpensive.
        """

        if self._high_demand(signals):
            return "high"

        if self._moderate_demand(signals):
            return "moderate"

        return "low"

    def _high_demand(
        self,
        signals: DemandSignals,
    ) -> bool:

        strong_count = 0
        moderate_count = 0

        for name, signal in signals.available().items():

            if self._signal_indicates_high(
                name,
                signal.value,
            ):
                if name in self.STRONG_ESCALATION_SIGNALS:
                    strong_count += 1
                else:
                    moderate_count += 1

        # One genuinely strong signal is enough.
        if strong_count >= 1:
            return True

        # Multiple moderate signals together justify DEEP.
        return moderate_count >= 3

    def _moderate_demand(
        self,
        signals: DemandSignals,
    ) -> bool:

        count = 0

        for name, signal in signals.available().items():

            if self._signal_indicates_moderate(
                name,
                signal.value,
            ):
                count += 1

        return count >= 1

    def _low_demand(
        self,
        signals: DemandSignals,
    ) -> bool:

        available = signals.available()

        if not available:
            return False

        if self._high_demand(signals):
            return False

        if self._moderate_demand(signals):
            return False

        return True

    # ==========================================================
    # Signal interpretation
    # ==========================================================

    @staticmethod
    def _signal_indicates_high(
        name: str,
        value: object,
    ) -> bool:

        if name == "evidence_conflict":
            return bool(value)

        if name == "decision_instability":
            return bool(value)

        if name == "tool_execution_status":
            return value in {
                "failed",
                "error",
                "blocked",
                "unknown",
            }

        if name in {
            "intent_ambiguity",
            "action_ambiguity",
            "target_ambiguity",
            "missing_information",
        }:
            return isinstance(value, (int, float)) and value >= 0.8

        if name in {
            "tool_failure_count",
            "operation_repetition",
            "reasoning_repetition",
        }:
            return isinstance(value, (int, float)) and value >= 3

        if name == "tool_dependency_depth":
            return isinstance(value, (int, float)) and value >= 3

        if name == "reasoning_progress":
            return isinstance(value, (int, float)) and value <= 0.0

        return False

    @staticmethod
    def _signal_indicates_moderate(
        name: str,
        value: object,
    ) -> bool:

        if name in {
            "intent_ambiguity",
            "action_ambiguity",
            "target_ambiguity",
        }:
            return (
                isinstance(value, (int, float))
                and value >= 0.5
            )

        if name == "missing_information":
            return bool(value)

        if name == "evidence_sufficiency":
            return (
                isinstance(value, (int, float))
                and value < 0.7
            )

        if name == "tool_failure_count":
            return (
                isinstance(value, (int, float))
                and value >= 1
            )

        if name == "operation_repetition":
            return (
                isinstance(value, (int, float))
                and value >= 1
            )

        if name == "tool_dependency_depth":
            return (
                isinstance(value, (int, float))
                and value >= 2
            )

        if name == "reasoning_repetition":
            return (
                isinstance(value, (int, float))
                and value >= 1
            )

        if name == "decision_instability":
            return bool(value)

        return False

    # ==========================================================
    # Goal / safety
    # ==========================================================

    @staticmethod
    def _goal_resolved(
        signals: DemandSignals,
    ) -> bool:

        signal = signals.goal_resolution

        if signal.status != DemandSignalStatus.AVAILABLE:
            return False

        return signal.value is True

    @staticmethod
    def _hard_abort_required(
        state: ComputationState,
        signals: DemandSignals,
    ) -> bool:

        # The Agent's MAX_REASONING_STEPS remains the authoritative
        # hard safety boundary. The controller only observes the
        # state here; it does not define or replace that constant.

        if state.reasoning_step >= 10:
            return True

        budget = signals.budget_remaining

        if (
            budget.status == DemandSignalStatus.AVAILABLE
            and isinstance(budget.value, (int, float))
            and budget.value <= 0
        ):
            return True

        return False

    # ==========================================================
    # Decision helpers
    # ==========================================================

    @staticmethod
    def _continue(
        state: ComputationState,
        mode: ComputationMode,
        signals: DemandSignals,
        reason: str,
    ) -> ComputationDecision:

        return ComputationDecision(
            action=ComputationAction.CONTINUE,
            current_mode=state.mode,
            next_mode=mode,
            reason=reason,
            signals_used=tuple(
                signals.available().keys()
            ),
        )

    @staticmethod
    def _escalate(
        state: ComputationState,
        mode: ComputationMode,
        signals: DemandSignals,
        reason: str,
    ) -> ComputationDecision:

        return ComputationDecision(
            action=ComputationAction.ESCALATE,
            current_mode=state.mode,
            next_mode=mode,
            reason=reason,
            signals_used=tuple(
                signals.available().keys()
            ),
        )

    @staticmethod
    def _deescalate(
        state: ComputationState,
        mode: ComputationMode,
        signals: DemandSignals,
        reason: str,
    ) -> ComputationDecision:

        return ComputationDecision(
            action=ComputationAction.DEESCALATE,
            current_mode=state.mode,
            next_mode=mode,
            reason=reason,
            signals_used=tuple(
                signals.available().keys()
            ),
        )

    @staticmethod
    def _finish(
        state: ComputationState,
        reason: str,
    ) -> ComputationDecision:

        return ComputationDecision(
            action=ComputationAction.FINISH,
            current_mode=state.mode,
            next_mode=state.mode,
            reason=reason,
        )

    @staticmethod
    def _abort(
        state: ComputationState,
        reason: str,
    ) -> ComputationDecision:

        return ComputationDecision(
            action=ComputationAction.ABORT,
            current_mode=state.mode,
            next_mode=state.mode,
            reason=reason,
        )

    @staticmethod
    def _available_signal_names(
        signals: DemandSignals,
    ) -> tuple[str, ...]:

        return tuple(
            signals.available().keys()
        )