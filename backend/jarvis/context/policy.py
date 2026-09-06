"""
Adaptive context policy.

Maps the current computation state and demand signals to a
ContextDemandProfile.

This policy does not:
    - retrieve information
    - compile context
    - tokenize context
    - enforce context-window limits
    - mutate persistent state
    - call the LLM
"""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.computation import (
    ComputationMode,
    ComputationPhase,
    ComputationState,
    DemandSignalStatus,
    DemandSignals,
)

from jarvis.context.demand import ContextDemandProfile


@dataclass(frozen=True)
class ContextPolicyDecision:
    """
    Result of an adaptive context policy evaluation.
    """

    profile: ContextDemandProfile
    reason: str


class ContextDemandPolicy:
    """
    Model-independent policy for selecting contextual demand.

    Baseline mapping:

        FAST   -> MINIMAL
        NORMAL -> STANDARD
        DEEP   -> EXPANDED

    Demand signals may increase the contextual requirement
    beyond the computation mode's baseline.
    """

    def decide(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ContextPolicyDecision:
        """
        Select the contextual demand profile for the current
        reasoning boundary.
        """

        # Terminal states require no additional contextual expansion.
        if state.terminal or state.aborted:
            return ContextPolicyDecision(
                profile=ContextDemandProfile.minimal(),
                reason="terminal computation state",
            )

        # A completely fresh request has not yet accumulated
        # enough evidence to justify standard/expanded context.
        #
        # This is intentionally independent of ComputationState's
        # default mode, which is NORMAL.
        if state.phase == ComputationPhase.INITIAL:
            if self._requires_expanded_context(signals):
                return ContextPolicyDecision(
                    profile=ContextDemandProfile.expanded(),
                    reason="high contextual demand detected at initialization",
                )

            if self._requires_standard_context(signals):
                return ContextPolicyDecision(
                    profile=ContextDemandProfile.standard(),
                    reason="standard contextual demand detected at initialization",
                )

            if state.mode == ComputationMode.DEEP:
                return ContextPolicyDecision(
                    profile=ContextDemandProfile.expanded(),
                    reason="deep computation mode",
                )

            if state.mode == ComputationMode.NORMAL:
                return ContextPolicyDecision(
                    profile=ContextDemandProfile.standard(),
                    reason="normal computation mode",
                )

            return ContextPolicyDecision(
                profile=ContextDemandProfile.minimal(),
                reason="fast computation mode",
            )
        # During an active computation cycle, explicit demand signals
        # may override the mode's normal contextual baseline.
        if self._requires_expanded_context(signals):
            return ContextPolicyDecision(
                profile=ContextDemandProfile.expanded(),
                reason="high contextual demand detected",
            )

        if self._requires_standard_context(signals):
            return ContextPolicyDecision(
                profile=ContextDemandProfile.standard(),
                reason="standard contextual demand detected",
            )

        # Mode-based baseline.
        if state.mode == ComputationMode.DEEP:
            return ContextPolicyDecision(
                profile=ContextDemandProfile.expanded(),
                reason="deep computation mode",
            )

        if state.mode == ComputationMode.NORMAL:
            return ContextPolicyDecision(
                profile=ContextDemandProfile.standard(),
                reason="normal computation mode",
            )

        return ContextPolicyDecision(
            profile=ContextDemandProfile.minimal(),
            reason="fast computation mode",
        )

    # ==========================================================
    # EXPANDED CONTEXT
    # ==========================================================

    @staticmethod
    def _requires_expanded_context(
        signals: DemandSignals,
    ) -> bool:
        """
        Return True when strong evidence indicates that broad
        contextual coverage is required.
        """

        if ContextDemandPolicy._is_high(
            signals,
            "information_sufficiency",
            inverse=True,
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "missing_information",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "evidence_conflict",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "intent_ambiguity",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "action_ambiguity",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "target_ambiguity",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "decision_instability",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "tool_failure_count",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "tool_dependency_depth",
        ):
            return True

        return False

    # ==========================================================
    # STANDARD CONTEXT
    # ==========================================================

    @staticmethod
    def _requires_standard_context(
        signals: DemandSignals,
    ) -> bool:
        """
        Return True when minimal context is insufficient but
        expanded context is not clearly justified.
        """

        if ContextDemandPolicy._is_high(
            signals,
            "unresolved_requirements",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "reasoning_step",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "reasoning_progress",
            inverse=True,
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "reasoning_repetition",
        ):
            return True

        if ContextDemandPolicy._is_high(
            signals,
            "operation_repetition",
        ):
            return True

        return False

    # ==========================================================
    # SIGNAL INTERPRETATION
    # ==========================================================

    @staticmethod
    def _is_high(
        signals: DemandSignals,
        field_name: str,
        *,
        inverse: bool = False,
    ) -> bool:
        """
        Safely evaluate a numeric demand signal.

        Normal signal:
            >= 0.7 means high demand.

        Inverse signal:
            <= 0.3 means high demand.

        Signals that are UNKNOWN, NOT_APPLICABLE, missing,
        or non-numeric are ignored.
        """

        signal = signals.get(field_name)

        if signal is None:
            return False

        if signal.status != DemandSignalStatus.AVAILABLE:
            return False

        value = signal.value

        if not isinstance(value, (int, float)):
            return False

        if inverse:
            return value <= 0.3

        return value >= 0.7