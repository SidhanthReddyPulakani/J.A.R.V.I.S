"""
Agent-callable definitions for information operations.

These definitions describe the operations exposed by
AgentMemoryOperations in a model-friendly function/tool format.

They do not:
- execute operations,
- parse tool calls,
- invoke the LLM,
- access persistence, or
- implement the Agent reasoning loop.

A later Agent protocol can use these definitions when
constructing the LLM's available operations.
"""

from __future__ import annotations

from typing import Any


def _string_parameter(
    description: str,
) -> dict[str, Any]:
    return {
        "type": "string",
        "description": description,
    }


def _integer_parameter(
    description: str,
) -> dict[str, Any]:
    return {
        "type": "integer",
        "description": description,
    }


def _number_parameter(
    description: str,
) -> dict[str, Any]:
    return {
        "type": "number",
        "description": description,
        "minimum": 0.0,
        "maximum": 1.0,
    }


def _boolean_parameter(
    description: str,
) -> dict[str, Any]:
    return {
        "type": "boolean",
        "description": description,
    }


def _tool(
    *,
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    """
    Build one LLM-compatible function definition.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_memory_operation_definitions() -> list[dict[str, Any]]:
    """
    Return all Agent-callable information operation definitions.

    The returned definitions are immutable-by-convention descriptions.
    Executing the corresponding operation remains the responsibility
    of the Agent operation layer.
    """
    return [
        _tool(
            name="memory_read_core",
            description=(
                "Read one Core Memory block by label."
            ),
            properties={
                "label": _string_parameter(
                    "Core Memory block label."
                ),
            },
            required=["label"],
        ),
        _tool(
            name="memory_list_core",
            description=(
                "List all Core Memory blocks."
            ),
            properties={},
            required=[],
        ),
        _tool(
            name="memory_replace_core",
            description=(
                "Replace the contents of one writable "
                "Core Memory block."
            ),
            properties={
                "label": _string_parameter(
                    "Core Memory block label."
                ),
                "content": _string_parameter(
                    "New complete block contents."
                ),
            },
            required=[
                "label",
                "content",
            ],
        ),
        _tool(
            name="memory_append_core",
            description=(
                "Append content to one writable "
                "Core Memory block."
            ),
            properties={
                "label": _string_parameter(
                    "Core Memory block label."
                ),
                "content": _string_parameter(
                    "Content to append."
                ),
            },
            required=[
                "label",
                "content",
            ],
        ),
        _tool(
            name="memory_create",
            description=(
                "Create a new Long-Term Memory."
            ),
            properties={
                "content": _string_parameter(
                    "Semantic information to retain."
                ),
                "category": _string_parameter(
                    "Optional memory category."
                ),
                "subject": _string_parameter(
                    "Optional subject."
                ),
                "project": _string_parameter(
                    "Optional project association."
                ),
                "importance": _number_parameter(
                    "Importance from 0 to 1."
                ),
                "confidence": _number_parameter(
                    "Confidence from 0 to 1."
                ),
            },
            required=["content"],
        ),
        _tool(
            name="memory_get",
            description=(
                "Retrieve one Long-Term Memory by ID."
            ),
            properties={
                "memory_id": _integer_parameter(
                    "Long-Term Memory ID."
                ),
            },
            required=["memory_id"],
        ),
        _tool(
            name="memory_list",
            description=(
                "List Long-Term Memories."
            ),
            properties={
                "include_superseded": _boolean_parameter(
                    "Whether superseded memories should be included."
                ),
            },
            required=[],
        ),
        _tool(
            name="memory_delete",
            description=(
                "Delete one active Long-Term Memory by ID."
            ),
            properties={
                "memory_id": _integer_parameter(
                    "Long-Term Memory ID."
                ),
            },
            required=["memory_id"],
        ),
        _tool(
            name="recall_search",
            description=(
                "Search persisted conversation history."
            ),
            properties={
                "query": _string_parameter(
                    "Historical information to search for."
                ),
                "limit": _integer_parameter(
                    "Maximum number of results."
                ),
            },
            required=["query"],
        ),
        _tool(
            name="knowledge_search",
            description=(
                "Search archived Knowledge through "
                "the unified Retrieval layer."
            ),
            properties={
                "query": _string_parameter(
                    "Knowledge to search for."
                ),
                "limit": _integer_parameter(
                    "Maximum number of results."
                ),
            },
            required=["query"],
        ),
        _tool(
            name="memory_search",
            description=(
                "Search Long-Term Memory through "
                "the unified Retrieval layer."
            ),
            properties={
                "query": _string_parameter(
                    "Long-Term Memory information to search for."
                ),
                "limit": _integer_parameter(
                    "Maximum number of results."
                ),
            },
            required=["query"],
        ),
    ]


__all__ = [
    "get_memory_operation_definitions",
]