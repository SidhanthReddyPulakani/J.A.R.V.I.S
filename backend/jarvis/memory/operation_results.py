"""
Structured results for Agent-facing information operations.

This module defines the result contract used by the memory operation
surface.

The contract intentionally separates:

    operation execution
        ↓
    structured result
        ↓
    future Agent reasoning

The result object does not know about the LLM, persistence, or the
Agent reasoning loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class OperationStatus(str, Enum):
    """
    High-level outcome of an information operation.
    """

    SUCCESS = "success"
    FAILURE = "failure"


class OperationErrorCode(str, Enum):
    """
    Stable machine-readable error categories.
    """

    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    PERMISSION_ERROR = "permission_error"
    CONFLICT = "conflict"
    SERVICE_ERROR = "service_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass(frozen=True)
class OperationResult:
    """
    Structured result returned by an Agent-facing operation.

    `data` contains successful operation output.

    `error_code` and `error_message` describe failures.

    The object is intentionally serializable into a plain dictionary
    so a later Agent/LLM protocol can transport it without depending
    on internal service objects.
    """

    operation: str
    status: OperationStatus
    data: Any = None
    error_code: OperationErrorCode | None = None
    error_message: str | None = None

    @property
    def success(self) -> bool:
        """
        Whether the operation completed successfully.
        """
        return self.status == OperationStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """
        Whether the operation failed.
        """
        return self.status == OperationStatus.FAILURE

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the result into a transport-safe dictionary.
        """
        return {
            "operation": self.operation,
            "status": self.status.value,
            "success": self.success,
            "data": self.data,
            "error_code": (
                self.error_code.value
                if self.error_code is not None
                else None
            ),
            "error_message": self.error_message,
        }

    @classmethod
    def success_result(
        cls,
        operation: str,
        data: Any = None,
    ) -> "OperationResult":
        """
        Construct a successful result.
        """
        return cls(
            operation=operation,
            status=OperationStatus.SUCCESS,
            data=data,
        )

    @classmethod
    def failure_result(
        cls,
        operation: str,
        error_code: OperationErrorCode,
        error_message: str,
    ) -> "OperationResult":
        """
        Construct a failed result.
        """
        return cls(
            operation=operation,
            status=OperationStatus.FAILURE,
            error_code=error_code,
            error_message=error_message,
        )


def classify_operation_exception(
    exc: Exception,
) -> OperationErrorCode:
    """
    Convert known Python exceptions into stable operation error codes.

    Unknown exceptions are intentionally mapped to UNKNOWN_ERROR.
    """
    if isinstance(exc, (TypeError, ValueError)):
        return OperationErrorCode.VALIDATION_ERROR

    if isinstance(exc, KeyError):
        return OperationErrorCode.NOT_FOUND

    if isinstance(exc, PermissionError):
        return OperationErrorCode.PERMISSION_ERROR

    if isinstance(exc, RuntimeError):
        return OperationErrorCode.SERVICE_ERROR

    return OperationErrorCode.UNKNOWN_ERROR


__all__ = [
    "OperationStatus",
    "OperationErrorCode",
    "OperationResult",
    "classify_operation_exception",
]