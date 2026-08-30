"""
Jarvis Knowledge / Archive package.

The package intentionally avoids eagerly importing service and
ingestion modules here.

This is important because:

    storage.repositories.knowledge
        -> jarvis.knowledge.models
        -> jarvis.knowledge package initialization

Eagerly importing KnowledgeService/KnowledgeIngestionService from this
package would create a circular dependency back into the repository
(service/ingestion both import KnowledgeRepository from
jarvis.storage.repositories.knowledge, which may still be mid-import
when it is the module that triggered this package init in the first
place).

The public names are therefore exposed lazily through __getattr__.
"""

from __future__ import annotations


__all__ = [
    "KnowledgeDocument",
    "KnowledgeIngestionResult",
    "KnowledgeIngestionService",
    "KnowledgePassage",
    "KnowledgeService",
    "KnowledgeSource",
]


def __getattr__(name: str):
    """
    Lazily resolve public knowledge-package exports.
    """

    if name in (
        "KnowledgeDocument",
        "KnowledgePassage",
        "KnowledgeSource",
    ):
        from jarvis.knowledge import models

        return getattr(models, name)

    if name in (
        "KnowledgeIngestionResult",
        "KnowledgeIngestionService",
    ):
        from jarvis.knowledge import ingestion

        return getattr(ingestion, name)

    if name == "KnowledgeService":
        from jarvis.knowledge.service import KnowledgeService

        return KnowledgeService

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )