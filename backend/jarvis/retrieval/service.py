"""
Unified Retrieval service.

The RetrievalService orchestrates independent providers and
returns normalized, globally ranked RetrievalResult objects.

It does not compile prompts.
It does not persist information.
It does not decide what information the LLM should see.

Those responsibilities belong to Context and Agent layers.
"""

from jarvis.retrieval.models import (
    RetrievalRequest,
    RetrievalResult,
)
from jarvis.retrieval.providers import (
    RetrievalProvider,
)


class RetrievalService:
    """
    Unified retrieval interface for Jarvis.
    """

    def __init__(
        self,
        providers: list[RetrievalProvider] | None = None,
    ) -> None:
        self._providers: dict[
            str,
            RetrievalProvider,
        ] = {}

        for provider in (
            providers or []
        ):
            self.register(
                provider
            )

    def register(
        self,
        provider: RetrievalProvider,
    ) -> None:
        """
        Register one retrieval provider.

        Provider names must be unique.
        """

        if not provider.name:
            raise ValueError(
                "Retrieval provider name cannot be empty."
            )

        if provider.name in self._providers:
            raise ValueError(
                f"Retrieval provider "
                f"'{provider.name}' is already registered."
            )

        self._providers[
            provider.name
        ] = provider

    def unregister(
        self,
        name: str,
    ) -> None:
        """
        Remove a provider.
        """

        self._providers.pop(
            name,
            None,
        )

    def providers(
        self,
    ) -> list[str]:
        """
        Return registered provider names.
        """

        return list(
            self._providers.keys()
        )

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        """
        Search selected retrieval providers.

        Results from all providers are merged and globally ranked.

        Args:
            query:
                Information being searched for.

            sources:
                Optional provider names.

                If omitted, all registered providers are queried.

            limit:
                Maximum number of results returned globally.
        """

        request = RetrievalRequest(
            query=query,
            sources=sources,
            limit=limit,
        )

        selected = self._select_providers(
            request.sources
        )

        results: list[
            RetrievalResult
        ] = []

        for provider in selected:

            provider_results = (
                provider.search(
                    request.query,
                    limit=request.limit,
                )
            )

            results.extend(
                provider_results
            )

        results.sort(
            key=lambda result: (
                result.score,
                _source_priority(
                    result.source
                ),
            ),
            reverse=True,
        )

        return results[
            :request.limit
        ]

    def _select_providers(
        self,
        sources: list[str] | None,
    ) -> list[RetrievalProvider]:
        """
        Resolve the requested provider set.
        """

        if sources is None:
            return list(
                self._providers.values()
            )

        selected: list[
            RetrievalProvider
        ] = []

        for source in sources:

            provider = (
                self._providers.get(
                    source
                )
            )

            if provider is None:
                raise KeyError(
                    f"Unknown retrieval source "
                    f"'{source}'. "
                    f"Available sources: "
                    f"{self.providers()}"
                )

            selected.append(
                provider
            )

        return selected


def _source_priority(
    source: str,
) -> int:
    """
    Stable secondary ranking between providers.

    This does not override relevance score.
    It only resolves equal-score results deterministically.
    """

    priorities = {
        "memory": 4,
        "relationship": 3,
        "knowledge": 2,
        "recall": 1,
    }

    return priorities.get(
        source,
        0,
    )