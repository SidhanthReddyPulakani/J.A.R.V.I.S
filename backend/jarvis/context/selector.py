"""
Adaptive context selection and window integration.

O2.3:

    ContextRequest
        ↓
    ContextDemandProfile
        ↓
    Context selection
        ↓
    ContextCompiler
        ↓
    ContextWindowManager
        ↓
    bounded AgentContext

This module is responsible for selecting which already-supplied
context sources participate in the current reasoning step.

It does NOT:
    - retrieve information
    - mutate persistent state
    - compile information itself
    - tokenize information itself
    - make LLM calls
    - replace ContextWindowManager's budget enforcement

Architectural boundary:

    ContextDemandProfile
        describes demand.

    ContextSelector
        applies that demand to an existing ContextRequest.

    ContextCompiler
        renders the selected request.

    ContextWindowManager
        enforces the final context-window boundary.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from jarvis.context.compiler import ContextCompiler
from jarvis.context.demand import (
    ContextDemandProfile,
    ContextPriority,
    ContextSource,
)
from jarvis.context.models import (
    AgentContext,
    ContextRequest,
)
from jarvis.context.window import ContextWindowManager


class ContextSelector:
    """
    Applies a ContextDemandProfile to an existing ContextRequest.

    Selection is intentionally source-level.

    The selector never retrieves additional information and never
    performs token-based eviction. Final fitting remains the
    responsibility of ContextWindowManager.
    """

    _SOURCE_FIELDS: dict[ContextSource, str] = {
        ContextSource.CORE_MEMORY: "core_memory",
        ContextSource.CONVERSATION: "conversation",
        ContextSource.RETRIEVAL: "retrieval_results",
        ContextSource.MEMORY: "memories",
        ContextSource.KNOWLEDGE: "knowledge",
        ContextSource.DIARY: "diary",
        ContextSource.RELATIONSHIPS: "relationships",
        ContextSource.OPERATION_RESULTS: "operation_results",
        ContextSource.CAPABILITY_INFORMATION: (
            "capability_information"
        ),
    }

    def select(
        self,
        request: ContextRequest,
        profile: ContextDemandProfile,
    ) -> ContextRequest:
        """
        Return a filtered ContextRequest according to the profile.

        The original request is never mutated.

        CURRENT_STATE is always preserved because ContextCompiler
        requires request.state to build the active agent-state
        section.

        Sources marked EXCLUDED are replaced with empty collections.
        All other supplied sources are preserved unchanged.
        """

        updates: dict[str, Any] = {}

        for source, field_name in self._SOURCE_FIELDS.items():
            if profile.priority_for(source) != ContextPriority.EXCLUDED:
                continue

            updates[field_name] = []

        return replace(
            request,
            **updates,
        )

    def is_selected(
        self,
        profile: ContextDemandProfile,
        source: ContextSource,
    ) -> bool:
        """
        Return whether a source participates in the selected context.
        """

        return not profile.is_excluded(source)


class AdaptiveContextBuilder:
    """
    Builds bounded AgentContext instances from adaptive demand.

    Processing order:

        1. Select supplied sources using ContextDemandProfile.
        2. Compile the selected ContextRequest.
        3. Apply ContextWindowManager.

    This class coordinates existing context-layer components; it
    does not replace their individual responsibilities.
    """

    def __init__(
        self,
        compiler: ContextCompiler,
        window_manager: ContextWindowManager,
        selector: ContextSelector | None = None,
    ) -> None:
        self.compiler = compiler
        self.window_manager = window_manager
        self.selector = selector or ContextSelector()

    def build(
        self,
        request: ContextRequest,
        profile: ContextDemandProfile,
    ) -> AgentContext:
        """
        Build the final bounded AgentContext for one reasoning step.
        """

        selected_request = self.selector.select(
            request,
            profile,
        )

        compiled_context = self.compiler.compile(
            selected_request,
        )

        return self.window_manager.prepare(
            compiled_context,
        )

    def select(
        self,
        request: ContextRequest,
        profile: ContextDemandProfile,
    ) -> ContextRequest:
        """
        Expose source selection without compiling or window fitting.

        Useful for inspection and focused tests.
        """

        return self.selector.select(
            request,
            profile,
        )

    def compile(
        self,
        request: ContextRequest,
        profile: ContextDemandProfile,
    ) -> AgentContext:
        """
        Select and compile context without applying the window manager.

        This is primarily useful for testing the separation between
        adaptive selection and context-window enforcement.
        """

        selected_request = self.selector.select(
            request,
            profile,
        )

        return self.compiler.compile(
            selected_request,
        )