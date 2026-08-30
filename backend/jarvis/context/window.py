"""
Context window management.

Responsible for measuring, budgeting, and bounding the
temporary context presented to the LLM.

P5.1:
    Lightweight token estimation.

P5.2:
    Token budget and pressure measurement.

P5.3:
    Pressure signalling and token-aware eviction.

Important architectural rule:

    Context eviction only removes information from the
    temporary AgentContext.

    It NEVER deletes or modifies Recall, Memory, Diary,
    Core Memory, Knowledge, or any other persistent store.

Recursive summarization is intentionally NOT implemented.
"""

from __future__ import annotations

from enum import Enum

from jarvis.context.models import AgentContext
from jarvis.core.config import settings
from jarvis.retrieval.models import RetrievalResult

class ContextPressure(str, Enum):
    """
    Current pressure state of the compiled context.
    """

    NORMAL = "normal"
    PRESSURE = "pressure"
    OVER_BUDGET = "over_budget"


class ContextWindowManager:
    """
    Manages the bounded context supplied to the LLM.

    P5.1
        Lightweight token estimation.

    P5.2
        Configurable token budget and pressure detection.

    P5.3
        Pressure signalling and token-aware eviction.

    The manager deliberately operates only on AgentContext.
    It has no persistence responsibility.
    """

    DEFAULT_PRESSURE_THRESHOLD = 0.70

    PRESSURE_MESSAGE = (
        "[CONTEXT PRESSURE] "
        "The active context is approaching its token budget. "
        "Older conversation history may be omitted from the "
        "active context. Historical information remains "
        "available through Recall."
    )

    OVER_BUDGET_MESSAGE = (
        "[CONTEXT WINDOW] "
        "The active context exceeded its token budget. "
        "Older conversation history has been removed from "
        "the active context. Historical information remains "
        "available through Recall."
    )

    def __init__(
        self,
        max_messages: int | None = None,
        context_budget: int | None = None,
        pressure_threshold: float = (
            DEFAULT_PRESSURE_THRESHOLD
        ),
    ) -> None:
        """
        Initialize the Context Window Manager.

        Parameters
        ----------
        max_messages:
            Existing message-count safety limit.
            Kept for backward compatibility.

        context_budget:
            Maximum estimated input-context tokens.

            If omitted, the budget follows the same
            context_size configured for Ollama.

        pressure_threshold:
            Fraction of the token budget at which the
            context enters PRESSURE state.

            Default:
                0.70 = 70%
        """

        if context_budget is None:
            context_budget = settings.context_size

        if context_budget <= 0:
            raise ValueError(
                "context_budget must be greater than zero."
            )

        if not 0 < pressure_threshold <= 1:
            raise ValueError(
                "pressure_threshold must be greater than "
                "0 and less than or equal to 1."
            )

        if (
            max_messages is not None
            and max_messages <= 0
        ):
            raise ValueError(
                "max_messages must be greater than zero "
                "when provided."
            )

        self.max_messages = max_messages

        self.context_budget = context_budget

        self.pressure_threshold = (
            pressure_threshold
        )

    # ==========================================================
    # TOKEN ESTIMATION
    # ==========================================================

    @staticmethod
    def estimate_tokens(
        text: str,
    ) -> int:
        """
        Estimate the number of tokens in a text string.

        Approximation:

            4 characters ≈ 1 token

        Empty or whitespace-only text returns 0.

        Non-empty text always returns at least 1.
        """

        if text is None:
            return 0

        text = str(text)

        if not text.strip():
            return 0

        return max(
            1,
            len(text) // 4,
        )

    def estimate_context_tokens(
        self,
        context: AgentContext,
    ) -> int:
        """
        Estimate the total token usage of an AgentContext.

        Every message contributes the estimated token count
        of its content.

        This method never modifies the context.
        """

        total_tokens = 0

        for message in context.as_messages():

            content = message.get(
                "content",
                "",
            )

            if content is None:
                continue

            total_tokens += self.estimate_tokens(
                str(content)
            )

        return total_tokens
    # ==========================================================
    # RETRIEVAL BUDGET
    # ==========================================================

    def estimate_retrieval_tokens(
        self,
        result: RetrievalResult,
    ) -> int:
        """
        Estimate the token cost of one retrieval result.

        The estimate includes the information that will be
        rendered into the LLM-facing retrieval section.

        This intentionally remains a cheap approximation.
        """

        content_tokens = self.estimate_tokens(
            result.content
        )

        metadata_tokens = 0

        if result.metadata:
            metadata_tokens = self.estimate_tokens(
                str(result.metadata)
            )

        identity_tokens = self.estimate_tokens(
            (
                f"[{result.source}] "
                f"id={result.identifier} "
                f"score={result.score:.3f}"
            )
        )

        return (
            content_tokens
            + metadata_tokens
            + identity_tokens
        )

    def fit_retrieval_budget(
        self,
        results: list[RetrievalResult],
        *,
        retrieval_budget: int | None = None,
    ) -> list[RetrievalResult]:
        """
        Return the highest-ranked retrieval results that fit
        within the retrieval token budget.

        Results are assumed to already be ordered by relevance.

        The original list is never modified.

        A result is either included in full or excluded.
        Individual retrieval results are never truncated.
        """

        if retrieval_budget is None:
            retrieval_budget = (
                settings.retrieval_budget
            )

        if retrieval_budget <= 0:
            raise ValueError(
                "retrieval_budget must be greater than zero."
            )

        selected: list[RetrievalResult] = []

        used_tokens = 0

        for result in results:

            result_tokens = (
                self.estimate_retrieval_tokens(
                    result
                )
            )

            if (
                used_tokens + result_tokens
                > retrieval_budget
            ):
                continue

            selected.append(
                result
            )

            used_tokens += result_tokens

        return selected

    def get_retrieval_budget(self) -> int:
        """
        Return the configured retrieval token budget.
        """

        return settings.retrieval_budget
    # ==========================================================
    # BUDGET
    # ==========================================================

    def get_budget(self) -> int:
        """
        Return the configured context token budget.
        """

        return self.context_budget

    def get_pressure_threshold_tokens(self) -> int:
        """
        Return the token threshold at which pressure begins.
        """

        return int(
            self.context_budget
            * self.pressure_threshold
        )

    def get_usage_ratio(
        self,
        context: AgentContext,
    ) -> float:
        """
        Return estimated context usage as a fraction
        of the configured budget.
        """

        estimated_tokens = (
            self.estimate_context_tokens(
                context
            )
        )

        return (
            estimated_tokens
            / self.context_budget
        )

    def get_pressure(
        self,
        context: AgentContext,
    ) -> ContextPressure:
        """
        Determine the current context-pressure state.

        NORMAL:
            usage is below the configured threshold.

        PRESSURE:
            usage has reached the warning threshold but
            remains within the budget.

        OVER_BUDGET:
            usage has reached or exceeded the budget.
        """

        estimated_tokens = (
            self.estimate_context_tokens(
                context
            )
        )

        if estimated_tokens >= self.context_budget:
            return ContextPressure.OVER_BUDGET

        if (
            estimated_tokens
            >= self.get_pressure_threshold_tokens()
        ):
            return ContextPressure.PRESSURE

        return ContextPressure.NORMAL

    def is_under_pressure(
        self,
        context: AgentContext,
    ) -> bool:
        """
        Return True when the context has entered
        PRESSURE or OVER_BUDGET state.
        """

        return (
            self.get_pressure(context)
            != ContextPressure.NORMAL
        )

    def is_over_budget(
        self,
        context: AgentContext,
    ) -> bool:
        """
        Return True when estimated context usage has
        reached or exceeded the configured budget.
        """

        return (
            self.get_pressure(context)
            == ContextPressure.OVER_BUDGET
        )

    # ==========================================================
    # PRESSURE SIGNAL
    # ==========================================================

    def _pressure_message(
        self,
        pressure: ContextPressure,
    ) -> dict[str, str] | None:
        """
        Build the system-level pressure signal.

        No signal is produced for NORMAL contexts.
        """

        if pressure == ContextPressure.PRESSURE:
            return {
                "role": "system",
                "content": self.PRESSURE_MESSAGE,
            }

        if pressure == ContextPressure.OVER_BUDGET:
            return {
                "role": "system",
                "content": self.OVER_BUDGET_MESSAGE,
            }

        return None

    # ==========================================================
    # TOKEN-AWARE EVICTION
    # ==========================================================

    def _evict_to_budget(
        self,
        messages: list[dict],
        *,
        reserved_tokens: int = 0,
    ) -> list[dict]:
        """
        Evict the oldest non-system messages until the
        context fits within the configured budget.

        The first message is always treated as the primary
        system message and is never evicted.

        Eviction is strictly oldest-first.

        Messages are removed from the active context only.
        Nothing is deleted from persistent storage.

        Parameters
        ----------
        messages:
            Current context messages.

        reserved_tokens:
            Estimated tokens reserved for a pressure signal
            that will be appended afterward.
        """

        if not messages:
            return []

        system_message = messages[0]

        system_tokens = self.estimate_tokens(
            system_message.get(
                "content",
                "",
            )
        )

        available_budget = (
            self.context_budget
            - system_tokens
            - reserved_tokens
        )

        if available_budget <= 0:
            return [system_message]

        # ------------------------------------------------------
        # Work from newest to oldest to determine the newest
        # suffix that can fit.
        #
        # This is equivalent to repeatedly evicting the oldest
        # message until the remaining context fits.
        # ------------------------------------------------------

        conversation_messages = messages[1:]

        retained_reversed: list[dict] = []
        used_tokens = 0

        for message in reversed(
            conversation_messages
        ):
            message_tokens = self.estimate_tokens(
                message.get(
                    "content",
                    "",
                )
            )

            # Once we encounter a message that cannot fit,
            # every message older than it must also be evicted.
            #
            # We therefore STOP rather than skipping it.
            if (
                used_tokens + message_tokens
                > available_budget
            ):
                break

            retained_reversed.append(message)

            used_tokens += message_tokens

        retained_reversed.reverse()

        return [
            system_message,
            *retained_reversed,
        ]
    def _apply_pressure(
        self,
        context: AgentContext,
    ) -> AgentContext:
        """
        Apply pressure signalling and eviction.

        Normal contexts are returned unchanged.

        Pressure contexts receive a system warning.

        Over-budget contexts are reduced using token-aware
        oldest-first eviction, while preserving the primary
        system message and newest conversation messages.
        """

        pressure = self.get_pressure(context)

        if pressure == ContextPressure.NORMAL:
            return context

        messages = context.as_messages()

        signal = self._pressure_message(
            pressure
        )

        if signal is None:
            return context

        signal_tokens = self.estimate_tokens(
            signal["content"]
        )

        # --------------------------------------------------
        # PRESSURE
        #
        # We are below the hard budget. Add the warning
        # without evicting history.
        # --------------------------------------------------

        if pressure == ContextPressure.PRESSURE:

            return AgentContext(
                messages=[
                    *messages,
                    signal,
                ]
            )

        # --------------------------------------------------
        # OVER BUDGET
        #
        # Reserve space for the warning first, then evict
        # the oldest messages until the final context fits.
        # --------------------------------------------------

        retained = self._evict_to_budget(
            messages,
            reserved_tokens=signal_tokens,
        )

        final_messages = [
            *retained,
            signal,
        ]

        # --------------------------------------------------
        # Extremely large system message safeguard.
        #
        # We cannot evict the primary system message.
        # If it alone exceeds the budget, preserving the
        # system message is the safer invariant.
        # --------------------------------------------------

        if (
            self.estimate_context_tokens(
                AgentContext(
                    messages=final_messages
                )
            )
            > self.context_budget
        ):
            return AgentContext(
                messages=[
                    messages[0],
                    signal,
                ]
            )

        return AgentContext(
            messages=final_messages
        )

    # ==========================================================
    # WINDOW PREPARATION
    # ==========================================================

    def prepare(
        self,
        context: AgentContext,
    ) -> AgentContext:
        """
        Prepare context for the LLM.

        Processing order:

            1. Apply existing message-count boundary.
            2. Measure token usage.
            3. Detect pressure.
            4. Add pressure signal.
            5. Evict oldest active messages if over budget.

        Eviction only affects the temporary AgentContext.

        Persistent Recall is never touched here.
        """

        prepared = context

        # --------------------------------------------------
        # Existing message-count boundary
        # --------------------------------------------------

        if self.max_messages is not None:

            messages = prepared.as_messages()

            if len(messages) > self.max_messages:

                system_message = messages[0]

                remaining_count = (
                    self.max_messages - 1
                )

                if remaining_count <= 0:
                    remaining = []
                else:
                    remaining = messages[
                        -remaining_count:
                    ]

                prepared = AgentContext(
                    messages=[
                        system_message,
                        *remaining,
                    ]
                )

        # --------------------------------------------------
        # Token pressure / eviction
        # --------------------------------------------------

        return self._apply_pressure(
            prepared
        )