"""
Retrieval providers.

Providers adapt individual information stores into the
common RetrievalResult contract.

Providers do not own orchestration or context compilation.
"""

from abc import ABC, abstractmethod
import re
from typing import Any

from jarvis.retrieval.models import RetrievalResult


class RetrievalProvider(ABC):
    """
    Base interface for a Retrieval provider.
    """

    name: str

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[RetrievalResult]:
        """
        Search this provider.
        """
        raise NotImplementedError


class RecallProvider(RetrievalProvider):
    """
    Retrieves relevant historical conversation messages.
    """

    name = "recall"

    def __init__(
        self,
        recall_service: Any,
        conversation_id: int | None = None,
    ) -> None:
        self.recall_service = recall_service
        self.conversation_id = conversation_id

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[RetrievalResult]:

        messages = self.recall_service.search(
            query,
            conversation_id=self.conversation_id,
            limit=limit,
        )

        results: list[RetrievalResult] = []

        for message in messages:

            content = str(
                message.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            results.append(
                RetrievalResult(
                    source=self.name,
                    identifier=message.get("id"),
                    content=content,
                    score=_lexical_score(
                        query,
                        content,
                    ),
                    metadata={
                        "role": message.get("role"),
                        "conversation_id": (
                            message.get(
                                "conversation_id"
                            )
                        ),
                        "created_at": (
                            message.get(
                                "created_at"
                            )
                        ),
                    },
                )
            )

        return results


class MemoryProvider(RetrievalProvider):
    """
    Retrieves relevant active Long-Term Memories.
    """

    name = "memory"

    def __init__(
        self,
        memory_service: Any,
    ) -> None:
        self.memory_service = memory_service

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[RetrievalResult]:

        memories = self.memory_service.list(
            include_superseded=False
        )

        scored: list[RetrievalResult] = []

        for memory in memories:

            content = str(
                getattr(
                    memory,
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            searchable_parts = [
                content,
                str(
                    getattr(
                        memory,
                        "category",
                        ""
                    )
                    or ""
                ),
                str(
                    getattr(
                        memory,
                        "subject",
                        ""
                    )
                    or ""
                ),
                str(
                    getattr(
                        memory,
                        "project",
                        ""
                    )
                    or ""
                ),
            ]

            searchable_text = " ".join(
                searchable_parts
            )

            score = _lexical_score(
                query,
                searchable_text,
            )

            if score <= 0:
                continue

            # Importance and confidence provide secondary
            # ranking signals without replacing lexical relevance.
            importance = float(
                getattr(
                    memory,
                    "importance",
                    0.5,
                )
            )

            confidence = float(
                getattr(
                    memory,
                    "confidence",
                    1.0,
                )
            )

            adjusted_score = min(
                1.0,
                (
                    score * 0.70
                    + importance * 0.15
                    + confidence * 0.15
                ),
            )

            scored.append(
                RetrievalResult(
                    source=self.name,
                    identifier=getattr(
                        memory,
                        "id",
                        None,
                    ),
                    content=content,
                    score=adjusted_score,
                    metadata={
                        "category": getattr(
                            memory,
                            "category",
                            None,
                        ),
                        "subject": getattr(
                            memory,
                            "subject",
                            None,
                        ),
                        "project": getattr(
                            memory,
                            "project",
                            None,
                        ),
                        "importance": importance,
                        "confidence": confidence,
                        "status": getattr(
                            memory,
                            "status",
                            None,
                        ),
                    },
                )
            )

        scored.sort(
            key=lambda result: (
                result.score,
                result.identifier
                if result.identifier is not None
                else -1,
            ),
            reverse=True,
        )

        return scored[:limit]

class KnowledgeProvider(RetrievalProvider):
    """
    Retrieval provider for archival Knowledge.

    KnowledgeService performs domain-level passage lookup.
    This provider converts those passages into the common
    RetrievalResult contract.
    """

    name = "knowledge"

    def __init__(
        self,
        knowledge_service: Any,
    ) -> None:

        self.knowledge_service = (
            knowledge_service
        )

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[RetrievalResult]:

        passages = (
            self.knowledge_service.search_passages(
                query,
                limit=limit,
            )
        )

        results: list[RetrievalResult] = []

        for passage in passages:

            content = (
                passage.content.strip()
            )

            if not content:
                continue

            score = _lexical_score(
                query,
                content,
            )

            if score <= 0:
                continue

            metadata = dict(
                getattr(
                    passage,
                    "metadata",
                    {},
                )
                or {}
            )

            metadata.update(
                {
                    "document_id": (
                        passage.document_id
                    ),
                    "sequence": (
                        passage.sequence
                    ),
                    "content_hash": (
                        passage.content_hash
                    ),
                }
            )

            document = (
                self.knowledge_service.get_document(
                    passage.document_id
                )
            )

            if document is not None:

                metadata.update(
                    {
                        "document_title": (
                            document.title
                        ),
                        "source_id": (
                            document.source_id
                        ),
                        "content_type": (
                            document.content_type
                        ),
                        "external_id": (
                            document.external_id
                        ),
                    }
                )

            results.append(
                RetrievalResult(
                    source=self.name,
                    identifier=passage.id,
                    content=content,
                    score=score,
                    metadata=metadata,
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                result.identifier
                if result.identifier is not None
                else -1,
            ),
            reverse=True,
        )

        return results[:limit]

class RelationshipProvider(RetrievalProvider):
    """
    Retrieves relationships relevant to a query.

    Relationships are associations rather than prose memory,
    so the result content is normalized into a readable form.
    """

    name = "relationship"

    def __init__(
        self,
        relationship_store: Any,
    ) -> None:
        self.relationship_store = (
            relationship_store
        )

    def search(
        self,
        query: str,
        *,
        limit: int,
    ) -> list[RetrievalResult]:

        relationships = (
            self.relationship_store.all()
        )

        results: list[RetrievalResult] = []

        for relationship in relationships:

            source = str(
                getattr(
                    relationship,
                    "source",
                    "",
                )
            )

            target_type = str(
                getattr(
                    relationship,
                    "target_type",
                    "",
                )
            )

            target = str(
                getattr(
                    relationship,
                    "target",
                    "",
                )
            )

            searchable_text = (
                f"{source} "
                f"{target_type} "
                f"{target}"
            )

            score = _lexical_score(
                query,
                searchable_text,
            )

            if score <= 0:
                continue

            confidence = float(
                getattr(
                    relationship,
                    "confidence",
                    0.5,
                )
            )

            # Confidence is a secondary signal.
            adjusted_score = min(
                1.0,
                score * 0.80
                + confidence * 0.20,
            )

            results.append(
                RetrievalResult(
                    source=self.name,
                    identifier=getattr(
                        relationship,
                        "id",
                        None,
                    ),
                    content=(
                        f"{source} → "
                        f"{target_type}: "
                        f"{target}"
                    ),
                    score=adjusted_score,
                    metadata={
                        "source": source,
                        "target_type": target_type,
                        "target": target,
                        "confidence": confidence,
                        "confirmations": getattr(
                            relationship,
                            "confirmations",
                            0,
                        ),
                        "uses": getattr(
                            relationship,
                            "uses",
                            0,
                        ),
                    },
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                result.identifier
                if result.identifier is not None
                else -1,
            ),
            reverse=True,
        )

        return results[:limit]


def _lexical_score(
    query: str,
    text: str,
) -> float:
    """
    Calculate a simple normalized lexical relevance score.

    This is deliberately deterministic and dependency-free.

    Later semantic/vector retrieval can replace or augment
    this scoring mechanism without changing RetrievalResult.
    """

    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)

    if not query_tokens or not text_tokens:
        return 0.0

    query_set = set(query_tokens)
    text_set = set(text_tokens)

    matched = query_set.intersection(
        text_set
    )

    if not matched:
        return 0.0

    coverage = (
        len(matched)
        / len(query_set)
    )

    frequency_bonus = min(
        1.0,
        sum(
            text_tokens.count(token)
            for token in matched
        )
        / max(
            1,
            len(query_tokens),
        ),
    )

    return min(
        1.0,
        coverage * 0.80
        + frequency_bonus * 0.20,
    )


def _tokenize(
    text: str,
) -> list[str]:
    """
    Normalize text into simple lexical tokens.
    """

    return re.findall(
        r"[\w]+(?:['’-][\w]+)*",
        text.lower(),
        flags=re.UNICODE,
    )