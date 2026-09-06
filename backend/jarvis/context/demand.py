"""
Context demand models.

This module defines the model-independent contract describing what
contextual information a reasoning step may require.

The demand profile does NOT:
    - retrieve information
    - compile context
    - tokenize context
    - enforce context-window limits
    - mutate persistent JARVIS state
    - make LLM calls

It only describes contextual demand.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class ContextDepth(str, Enum):
    """
    Overall contextual depth requested for a reasoning step.
    """

    MINIMAL = "minimal"
    STANDARD = "standard"
    EXPANDED = "expanded"


class ContextSource(str, Enum):
    """
    Contextual information sources available to the context layer.
    """

    CURRENT_STATE = "current_state"
    CORE_MEMORY = "core_memory"
    CONVERSATION = "conversation"
    RETRIEVAL = "retrieval"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    DIARY = "diary"
    RELATIONSHIPS = "relationships"
    OPERATION_RESULTS = "operation_results"
    CAPABILITY_INFORMATION = "capability_information"


class ContextPriority(str, Enum):
    """
    Relative importance of a context source for the current
    reasoning step.

    These are semantic priorities, not token allocations.
    """

    REQUIRED = "required"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ContextSourceDemand:
    """
    Demand specification for one contextual source.

    `priority` describes how important the source is.

    `budget` is an optional desired budget for the source. It is
    intentionally not an enforcement mechanism. Actual context
    fitting remains the responsibility of ContextWindowManager.
    """

    priority: ContextPriority = ContextPriority.MEDIUM

    budget: int | None = None

    def __post_init__(self) -> None:
        if self.budget is not None and self.budget < 0:
            raise ValueError("Context source budget cannot be negative.")

        if (
            self.priority == ContextPriority.EXCLUDED
            and self.budget is not None
            and self.budget > 0
        ):
            raise ValueError(
                "Excluded context sources cannot have a positive budget."
            )


@dataclass(frozen=True)
class ContextDemandProfile:
    """
    Model-independent description of contextual demand for one
    reasoning step.

    The profile answers:

        "What contextual information does this reasoning step need?"

    It does NOT decide how information is retrieved, compiled,
    tokenized, or physically fitted into the model context window.

    The profile is transient and belongs to one reasoning cycle.
    """

    depth: ContextDepth = ContextDepth.STANDARD

    sources: Mapping[
        ContextSource,
        ContextSourceDemand,
    ] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_sources: dict[
            ContextSource,
            ContextSourceDemand,
        ] = {}

        for source, demand in self.sources.items():
            if not isinstance(source, ContextSource):
                raise TypeError(
                    "Context demand source keys must be ContextSource values."
                )

            if not isinstance(demand, ContextSourceDemand):
                raise TypeError(
                    "Context demand values must be ContextSourceDemand values."
                )

            normalized_sources[source] = demand

        object.__setattr__(
            self,
            "sources",
            normalized_sources,
        )

    def demand_for(
        self,
        source: ContextSource,
    ) -> ContextSourceDemand:
        """
        Return the demand specification for a source.

        Unspecified sources are treated as MEDIUM priority with no
        explicit budget rather than being implicitly excluded.
        """

        return self.sources.get(
            source,
            ContextSourceDemand(),
        )

    def priority_for(
        self,
        source: ContextSource,
    ) -> ContextPriority:
        """
        Return the priority assigned to a context source.
        """

        return self.demand_for(source).priority

    def budget_for(
        self,
        source: ContextSource,
    ) -> int | None:
        """
        Return the desired budget assigned to a context source.
        """

        return self.demand_for(source).budget

    def is_required(
        self,
        source: ContextSource,
    ) -> bool:
        """
        Return whether a source is explicitly required.
        """

        return (
            self.priority_for(source)
            == ContextPriority.REQUIRED
        )

    def is_excluded(
        self,
        source: ContextSource,
    ) -> bool:
        """
        Return whether a source is explicitly excluded.
        """

        return (
            self.priority_for(source)
            == ContextPriority.EXCLUDED
        )

    def with_source(
        self,
        source: ContextSource,
        demand: ContextSourceDemand,
    ) -> "ContextDemandProfile":
        """
        Return a new profile with one source requirement replaced.

        Profiles are immutable so that a previously selected demand
        profile cannot be accidentally mutated while a reasoning
        cycle is using it.
        """

        updated_sources = dict(self.sources)
        updated_sources[source] = demand

        return ContextDemandProfile(
            depth=self.depth,
            sources=updated_sources,
        )

    @classmethod
    def minimal(
        cls,
    ) -> "ContextDemandProfile":
        """
        Construct the structural MINIMAL profile.

        This factory defines the contextual shape of minimal
        computation. It does not define numeric token budgets.
        """

        return cls(
            depth=ContextDepth.MINIMAL,
            sources={
                ContextSource.CURRENT_STATE:
                    ContextSourceDemand(
                        priority=ContextPriority.REQUIRED,
                    ),
                ContextSource.CONVERSATION:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.RETRIEVAL:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.OPERATION_RESULTS:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.CORE_MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.LOW,
                    ),
                ContextSource.MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.EXCLUDED,
                    ),
                ContextSource.KNOWLEDGE:
                    ContextSourceDemand(
                        priority=ContextPriority.EXCLUDED,
                    ),
                ContextSource.DIARY:
                    ContextSourceDemand(
                        priority=ContextPriority.EXCLUDED,
                    ),
                ContextSource.RELATIONSHIPS:
                    ContextSourceDemand(
                        priority=ContextPriority.EXCLUDED,
                    ),
                ContextSource.CAPABILITY_INFORMATION:
                    ContextSourceDemand(
                        priority=ContextPriority.LOW,
                    ),
            },
        )

    @classmethod
    def standard(
        cls,
    ) -> "ContextDemandProfile":
        """
        Construct the structural STANDARD profile.

        This represents the normal JARVIS contextual operating
        envelope without imposing numeric token budgets.
        """

        return cls(
            depth=ContextDepth.STANDARD,
            sources={
                ContextSource.CURRENT_STATE:
                    ContextSourceDemand(
                        priority=ContextPriority.REQUIRED,
                    ),
                ContextSource.CORE_MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.CONVERSATION:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.RETRIEVAL:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.OPERATION_RESULTS:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.KNOWLEDGE:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.RELATIONSHIPS:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.DIARY:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.CAPABILITY_INFORMATION:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
            },
        )

    @classmethod
    def expanded(
        cls,
    ) -> "ContextDemandProfile":
        """
        Construct the structural EXPANDED profile.

        Expanded demand allows broader historical and informational
        context while remaining subject to ContextWindowManager
        enforcement.
        """

        return cls(
            depth=ContextDepth.EXPANDED,
            sources={
                ContextSource.CURRENT_STATE:
                    ContextSourceDemand(
                        priority=ContextPriority.REQUIRED,
                    ),
                ContextSource.CORE_MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.CONVERSATION:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.RETRIEVAL:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.MEMORY:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.KNOWLEDGE:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.DIARY:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.RELATIONSHIPS:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
                ContextSource.OPERATION_RESULTS:
                    ContextSourceDemand(
                        priority=ContextPriority.HIGH,
                    ),
                ContextSource.CAPABILITY_INFORMATION:
                    ContextSourceDemand(
                        priority=ContextPriority.MEDIUM,
                    ),
            },
        )