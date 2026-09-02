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
    High-level, coarse outcome of an information operation.

    This is the original P1 binary contract. It remains the field
    every existing consumer (Agent Memory Operations, the P8 unified
    tool dispatch) reads via `.success` / `.failed`. It is
    deliberately left unchanged so nothing built against it before
    P10 needs to change.
    """

    SUCCESS = "success"
    FAILURE = "failure"


class OperationState(str, Enum):
    """
    P10 — the fuller operation-lifecycle vocabulary.

    Where `OperationStatus` only distinguishes success from failure,
    `OperationState` lets an operation report *what happened*, not
    just whether it happened: `NOT_FOUND` ("Could not find VS Code")
    and `REQUIRES_INPUT` ("Found 3 matching applications") are both
    coarse FAILUREs, but the Agent needs to reason about them very
    differently.

    Not every capability needs every state on day one — add more
    call sites for a given state only once a real capability
    produces that outcome (see `jarvis.capabilities.apps_capability`
    for the first real user of NOT_FOUND and REQUIRES_INPUT).
    """

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    REQUIRES_INPUT = "requires_input"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"


# --------------------------------------------------------
# States that represent an operation still awaiting further
# action (more input from the user, more execution time, or
# explicit cancellation) rather than a finished outcome.
#
# This is the lifecycle half of P10: `OperationResult.is_terminal`
# is what a future Capability Controller / Agent loop would check
# before deciding whether an operation can be treated as done.
# --------------------------------------------------------

_NON_TERMINAL_STATES = frozenset(
    {
        OperationState.BLOCKED,
        OperationState.REQUIRES_INPUT,
        OperationState.IN_PROGRESS,
    }
)


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


# --------------------------------------------------------
# Coarse error-code fallback used only when a caller builds a
# result via `from_state` without supplying an explicit
# `error_code`. This exists purely so legacy consumers that only
# understand `OperationErrorCode` still get a reasonable value;
# `state` remains the source of truth for anything that reads it.
# --------------------------------------------------------

_DEFAULT_ERROR_CODE_FOR_STATE: dict[
    OperationState,
    OperationErrorCode,
] = {
    OperationState.FAILED: (
        OperationErrorCode.SERVICE_ERROR
    ),
    OperationState.PARTIAL: (
        OperationErrorCode.SERVICE_ERROR
    ),
    OperationState.BLOCKED: (
        OperationErrorCode.PERMISSION_ERROR
    ),
    OperationState.INVALID: (
        OperationErrorCode.VALIDATION_ERROR
    ),
    OperationState.NOT_FOUND: (
        OperationErrorCode.NOT_FOUND
    ),
    OperationState.REQUIRES_INPUT: (
        OperationErrorCode.VALIDATION_ERROR
    ),
    OperationState.IN_PROGRESS: (
        OperationErrorCode.SERVICE_ERROR
    ),
    OperationState.CANCELLED: (
        OperationErrorCode.SERVICE_ERROR
    ),
}


@dataclass(frozen=True)
class OperationResult:
    """
    Structured result returned by an Agent-facing operation.

    `data` contains successful operation output.

    `error_code` and `error_message` describe failures.

    `state` (P10) optionally carries the fuller OperationState
    lifecycle vocabulary. It defaults to None for every result built
    through the original `success_result` / `failure_result`
    constructors, so nothing built before P10 needs to change.
    Callers that want the richer vocabulary should build results
    through `from_state` instead.

    The object is intentionally serializable into a plain dictionary
    so a later Agent/LLM protocol can transport it without depending
    on internal service objects.
    """

    operation: str
    status: OperationStatus
    data: Any = None
    error_code: OperationErrorCode | None = None
    error_message: str | None = None
    state: OperationState | None = None

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

    @property
    def is_terminal(self) -> bool:
        """
        Whether this result represents a finished outcome rather
        than one still awaiting further action (more input from the
        user, more execution time, or explicit cancellation).

        Results with no `state` set are always terminal — the
        original SUCCESS/FAILURE contract never had a non-terminal
        concept, so every legacy result is, by definition, done.
        """
        if self.state is None:
            return True

        return self.state not in _NON_TERMINAL_STATES

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
            "state": (
                self.state.value
                if self.state is not None
                else None
            ),
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

    @classmethod
    def from_state(
        cls,
        operation: str,
        state: OperationState,
        data: Any = None,
        error_code: OperationErrorCode | None = None,
        error_message: str | None = None,
    ) -> "OperationResult":
        """
        Construct a result carrying the fuller OperationState
        vocabulary (P10).

        The coarse `status` field is always populated too, so every
        existing SUCCESS/FAILURE consumer keeps working unchanged:
        `SUCCESS` maps to `OperationStatus.SUCCESS`; every other
        state maps to `OperationStatus.FAILURE`. Callers that care
        about the difference between, say, a genuine failure and an
        operation that merely needs the user to pick one of several
        candidates should read `.state`, not `.status`.

        If `error_code` is omitted for a non-success state, a
        reasonable default is filled in from `state` so legacy
        consumers of `error_code` still get something sensible.
        """

        status = (
            OperationStatus.SUCCESS
            if state == OperationState.SUCCESS
            else OperationStatus.FAILURE
        )

        resolved_error_code = error_code

        if (
            status == OperationStatus.FAILURE
            and resolved_error_code is None
        ):
            resolved_error_code = (
                _DEFAULT_ERROR_CODE_FOR_STATE.get(
                    state,
                    OperationErrorCode.UNKNOWN_ERROR,
                )
            )

        return cls(
            operation=operation,
            status=status,
            data=data,
            error_code=resolved_error_code,
            error_message=error_message,
            state=state,
        )

    @classmethod
    def cancelled_result(
        cls,
        operation: str,
        message: str | None = None,
    ) -> "OperationResult":
        """
        Construct a result representing an explicitly cancelled
        operation (P10's cancellation semantics).

        Cancellation is always terminal — a cancelled operation does
        not resume — so this is a coarse FAILURE with `state`
        `CANCELLED`, distinguishable from a genuine error by callers
        that read `.state`.
        """

        return cls.from_state(
            operation=operation,
            state=OperationState.CANCELLED,
            error_message=(
                message or "Operation was cancelled."
            ),
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
    "OperationState",
    "OperationErrorCode",
    "OperationResult",
    "classify_operation_exception",
]