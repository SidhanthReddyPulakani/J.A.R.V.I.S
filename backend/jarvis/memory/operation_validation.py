"""
Validation helpers for Agent-facing memory operations.

This module validates operation arguments before they reach
the information services.

It deliberately does not:
- access persistence,
- execute operations,
- parse LLM responses,
- compile context, or
- implement the Agent reasoning loop.

Its responsibility is only operation-input validation.
"""

from __future__ import annotations

from typing import Any


DEFAULT_LIMIT = 10
MAX_LIMIT = 50


def validate_label(
    label: str,
) -> str:
    """
    Validate a Core Memory block label.

    The original value is returned unchanged when valid.
    """
    if not isinstance(label, str):
        raise TypeError("Memory block label must be a string.")

    if not label.strip():
        raise ValueError(
            "Memory block label cannot be empty."
        )

    return label


def validate_content(
    content: str,
    *,
    field_name: str = "content",
) -> str:
    """
    Validate required textual content.
    """
    if not isinstance(content, str):
        raise TypeError(
            f"{field_name} must be a string."
        )

    if not content.strip():
        raise ValueError(
            f"{field_name} cannot be empty."
        )

    return content


def validate_query(
    query: str,
) -> str:
    """
    Validate a retrieval/search query.
    """
    if not isinstance(query, str):
        raise TypeError(
            "Search query must be a string."
        )

    if not query.strip():
        raise ValueError(
            "Search query cannot be empty."
        )

    return query


def validate_limit(
    limit: int,
) -> int:
    """
    Validate a result limit.

    Limits are bounded here so an Agent cannot accidentally
    request an unreasonably large result set.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(
            "Operation limit must be an integer."
        )

    if limit <= 0:
        raise ValueError(
            "Operation limit must be positive."
        )

    if limit > MAX_LIMIT:
        raise ValueError(
            f"Operation limit cannot exceed {MAX_LIMIT}."
        )

    return limit


def validate_id(
    value: int,
    *,
    field_name: str = "ID",
) -> int:
    """
    Validate a persistent positive integer identifier.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"{field_name} must be an integer."
        )

    if value <= 0:
        raise ValueError(
            f"{field_name} must be positive."
        )

    return value


def validate_agent_id(
    agent_id: str,
) -> str:
    """
    Validate an Agent identifier.
    """
    if not isinstance(agent_id, str):
        raise TypeError(
            "Agent ID must be a string."
        )

    if not agent_id.strip():
        raise ValueError(
            "Agent ID cannot be empty."
        )

    return agent_id


def validate_optional_text(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    """
    Validate optional textual metadata.

    None remains None.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string or None."
        )

    if not value.strip():
        raise ValueError(
            f"{field_name} cannot be empty when provided."
        )

    return value


def validate_unit_interval(
    value: float,
    *,
    field_name: str,
) -> float:
    """
    Validate a numeric value in the inclusive [0, 1] range.
    """
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            f"{field_name} must be a number."
        )

    value = float(value)

    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{field_name} must be between 0 and 1."
        )

    return value


def validate_boolean(
    value: bool,
    *,
    field_name: str,
) -> bool:
    """
    Validate a strict boolean operation argument.
    """
    if not isinstance(value, bool):
        raise TypeError(
            f"{field_name} must be a boolean."
        )

    return value


def validate_conversation_id(
    conversation_id: int | None,
) -> int | None:
    """
    Validate an optional conversation identifier.
    """
    if conversation_id is None:
        return None

    return validate_id(
        conversation_id,
        field_name="Conversation ID",
    )


def validate_memory_creation(
    *,
    content: str,
    category: str | None,
    subject: str | None,
    project: str | None,
    importance: float,
    confidence: float,
) -> dict[str, Any]:
    """
    Validate all arguments for Long-Term Memory creation.
    """
    return {
        "content": validate_content(
            content,
            field_name="Memory content",
        ),
        "category": validate_optional_text(
            category,
            field_name="category",
        ),
        "subject": validate_optional_text(
            subject,
            field_name="subject",
        ),
        "project": validate_optional_text(
            project,
            field_name="project",
        ),
        "importance": validate_unit_interval(
            importance,
            field_name="importance",
        ),
        "confidence": validate_unit_interval(
            confidence,
            field_name="confidence",
        ),
    }