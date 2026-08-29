"""
Tests for R2.9 Agent Memory Operations.

Covers:

- operation validation,
- Core Memory operations,
- Long-Term Memory operations,
- Recall search,
- Knowledge search,
- Memory retrieval,
- agent-callable operation definitions,
- definition uniqueness and required parameters.
"""

from __future__ import annotations

from jarvis.memory.operation_definitions import (
    get_memory_operation_definitions,
)
from jarvis.memory.operation_validation import (
    MAX_LIMIT,
    validate_content,
    validate_id,
    validate_limit,
    validate_query,
)


def test_validation_helpers() -> None:
    assert validate_content("hello") == "hello"
    assert validate_query("hello") == "hello"
    assert validate_id(1) == 1
    assert validate_limit(10) == 10

    try:
        validate_content("   ")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Empty content should fail validation."
        )

    try:
        validate_query("")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Empty query should fail validation."
        )

    try:
        validate_id(0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Non-positive IDs should fail validation."
        )

    try:
        validate_limit(0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Non-positive limits should fail validation."
        )

    try:
        validate_limit(MAX_LIMIT + 1)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Oversized limits should fail validation."
        )


def test_operation_definitions() -> None:
    definitions = get_memory_operation_definitions()

    assert definitions

    names = [
        definition["function"]["name"]
        for definition in definitions
    ]

    assert len(names) == len(set(names))

    expected = {
        "memory_read_core",
        "memory_list_core",
        "memory_replace_core",
        "memory_append_core",
        "memory_create",
        "memory_get",
        "memory_list",
        "memory_delete",
        "recall_search",
        "knowledge_search",
        "memory_search",
    }

    assert set(names) == expected

    for definition in definitions:
        assert definition["type"] == "function"

        function = definition["function"]

        assert function["name"]
        assert function["description"]

        parameters = function["parameters"]

        assert parameters["type"] == "object"
        assert isinstance(
            parameters["properties"],
            dict,
        )
        assert isinstance(
            parameters["required"],
            list,
        )


def test_required_parameters() -> None:
    definitions = get_memory_operation_definitions()

    by_name = {
        definition["function"]["name"]: definition
        for definition in definitions
    }

    assert by_name[
        "memory_read_core"
    ]["function"]["parameters"]["required"] == [
        "label"
    ]

    assert by_name[
        "memory_replace_core"
    ]["function"]["parameters"]["required"] == [
        "label",
        "content",
    ]

    assert by_name[
        "memory_append_core"
    ]["function"]["parameters"]["required"] == [
        "label",
        "content",
    ]

    assert by_name[
        "memory_create"
    ]["function"]["parameters"]["required"] == [
        "content"
    ]

    assert by_name[
        "memory_get"
    ]["function"]["parameters"]["required"] == [
        "memory_id"
    ]

    assert by_name[
        "memory_delete"
    ]["function"]["parameters"]["required"] == [
        "memory_id"
    ]

    assert by_name[
        "recall_search"
    ]["function"]["parameters"]["required"] == [
        "query"
    ]

    assert by_name[
        "knowledge_search"
    ]["function"]["parameters"]["required"] == [
        "query"
    ]

    assert by_name[
        "memory_search"
    ]["function"]["parameters"]["required"] == [
        "query"
    ]


def test_operation_definitions_are_tool_compatible() -> None:
    definitions = get_memory_operation_definitions()

    for definition in definitions:
        assert set(definition) == {
            "type",
            "function",
        }

        function = definition["function"]

        assert set(function) == {
            "name",
            "description",
            "parameters",
        }


def test_memory_operations_import() -> None:
    from jarvis.memory import (
        AgentMemoryOperations,
        get_memory_operation_definitions,
    )

    assert AgentMemoryOperations is not None
    assert get_memory_operation_definitions is not None


def main() -> None:
    test_validation_helpers()
    test_operation_definitions()
    test_required_parameters()
    test_operation_definitions_are_tool_compatible()
    test_memory_operations_import()

    print(
        "R2.9B/R2.9C memory operation tests passed."
    )


if __name__ == "__main__":
    main()