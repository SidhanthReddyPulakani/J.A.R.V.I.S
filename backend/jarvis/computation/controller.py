from __future__ import annotations

from jarvis.computation.decision import ComputationDecision
from jarvis.computation.policy import ComputationPolicy
from jarvis.computation.signals import DemandSignals
from jarvis.computation.state import (
    ComputationPhase,
    ComputationState,
)


class ComputationController:
    """
    Closed-loop adaptive computation controller.

    The controller coordinates transient computation state,
    demand observations, and deterministic policy decisions.

    It deliberately contains no LLM/runtime-specific logic.
    """

    def __init__(
        self,
        policy: ComputationPolicy | None = None,
    ) -> None:

        self.policy = (
            policy
            if policy is not None
            else ComputationPolicy()
        )

    def evaluate(
        self,
        state: ComputationState,
        signals: DemandSignals,
        phase: ComputationPhase | None = None,
    ) -> ComputationDecision:
        """
        Evaluate computation at a decision boundary.
        """

        if phase is not None:
            state.phase = phase

        state.last_signals = signals

        decision = self.policy.evaluate(
            state=state,
            signals=signals,
        )

        state.apply_decision(
            decision
        )

        return decision

    def initial(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        return self.evaluate(
            state=state,
            signals=signals,
            phase=ComputationPhase.INITIAL,
        )

    def pre_llm(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        return self.evaluate(
            state=state,
            signals=signals,
            phase=ComputationPhase.PRE_LLM,
        )

    def post_llm(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        return self.evaluate(
            state=state,
            signals=signals,
            phase=ComputationPhase.POST_LLM,
        )

    def post_execution(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        return self.evaluate(
            state=state,
            signals=signals,
            phase=ComputationPhase.POST_EXECUTION,
        )

    def completion(
        self,
        state: ComputationState,
        signals: DemandSignals,
    ) -> ComputationDecision:

        return self.evaluate(
            state=state,
            signals=signals,
            phase=ComputationPhase.COMPLETION,
        )