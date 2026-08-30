"""
Tests for R2.9D structured operation results.
"""

from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationStatus,
    classify_operation_exception,
)


def test_success_result() -> None:
    result = OperationResult.success_result(
        "memory_search",
        data=["result"],
    )

    assert result.success
    assert not result.failed
    assert result.status == OperationStatus.SUCCESS
    assert result.data == ["result"]
    assert result.error_code is None
    assert result.error_message is None


def test_failure_result() -> None:
    result = OperationResult.failure_result(
        "memory_read",
        OperationErrorCode.NOT_FOUND,
        "Memory was not found.",
    )

    assert result.failed
    assert not result.success
    assert result.status == OperationStatus.FAILURE
    assert result.data is None
    assert (
        result.error_code
        == OperationErrorCode.NOT_FOUND
    )
    assert (
        result.error_message
        == "Memory was not found."
    )


def test_result_serialization() -> None:
    result = OperationResult.success_result(
        "recall_search",
        data=[
            {
                "content": "previous message",
            }
        ],
    )

    payload = result.to_dict()

    assert payload["operation"] == "recall_search"
    assert payload["status"] == "success"
    assert payload["success"] is True
    assert payload["data"]
    assert payload["error_code"] is None
    assert payload["error_message"] is None


def test_exception_classification() -> None:
    assert (
        classify_operation_exception(
            ValueError("bad input")
        )
        == OperationErrorCode.VALIDATION_ERROR
    )

    assert (
        classify_operation_exception(
            TypeError("wrong type")
        )
        == OperationErrorCode.VALIDATION_ERROR
    )

    assert (
        classify_operation_exception(
            KeyError("missing")
        )
        == OperationErrorCode.NOT_FOUND
    )

    assert (
        classify_operation_exception(
            PermissionError("denied")
        )
        == OperationErrorCode.PERMISSION_ERROR
    )

    assert (
        classify_operation_exception(
            RuntimeError("service failure")
        )
        == OperationErrorCode.SERVICE_ERROR
    )

    assert (
        classify_operation_exception(
            Exception("unexpected")
        )
        == OperationErrorCode.UNKNOWN_ERROR
    )


def main() -> None:
    test_success_result()
    test_failure_result()
    test_result_serialization()
    test_exception_classification()

    print(
        "R2.9D operation-result tests passed."
    )


if __name__ == "__main__":
    main()