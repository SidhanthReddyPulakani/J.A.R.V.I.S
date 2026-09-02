"""
P12 — Capability Controller.

The single governed gateway every capability operation must go
through. There is no separate `result()` method — `execute()`
returns the OperationResult directly.

The one rule that matters most: capabilities must never call each
other directly. If Capability A needs Capability B, it goes
`A -> Controller -> B`. This module is what "the Controller" means
in that rule — nothing in `jarvis.capabilities` should import a
sibling capability module directly to invoke it.

From day one this includes: validation (required arguments present),
error normalization (any raised exception becomes a failed
OperationResult instead of escaping), and logging. Permissions and
governance beyond "did this validate", dependency management between
capabilities, and versioning are explicitly deferred until a real
capability needs them (P24 is where capability-to-capability
dependency resolution actually arrives).
"""

from __future__ import annotations

import logging

from jarvis.capabilities.contracts import OperationDefinition
from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.core.capability_request import CapabilityRequest
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    classify_operation_exception,
)

logger = logging.getLogger(
    "jarvis.capabilities.controller"
)


class CapabilityController:
    """
    Validates, dispatches, and normalizes the result of every
    capability operation request.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
    ) -> None:

        self._registry = registry

    def execute(
        self,
        request: CapabilityRequest,
    ) -> OperationResult:
        """
        Execute one CapabilityRequest and return its OperationResult
        directly.

        Unregistered operations, missing required arguments, and any
        exception raised by the capability itself are all normalized
        into a failed OperationResult rather than propagating —
        nothing calling this method should ever need a try/except
        around it for a routing or validation failure.
        """

        resolved = (
            self._registry.resolve_operation(
                request.operation
            )
        )

        if resolved is None:

            logger.info(
                "capability_operation_not_found "
                "operation=%s",
                request.operation,
            )

            return (
                OperationResult.failure_result(
                    operation=request.operation,
                    error_code=(
                        OperationErrorCode.NOT_FOUND
                    ),
                    error_message=(
                        "Unknown capability operation: "
                        f"{request.operation}"
                    ),
                )
            )

        capability, definition = resolved

        validation_error = (
            self._validate_arguments(
                definition,
                request.arguments,
            )
        )

        if validation_error is not None:

            logger.info(
                "capability_operation_validation_"
                "failed operation=%s reason=%s",
                request.operation,
                validation_error,
            )

            return (
                OperationResult.failure_result(
                    operation=request.operation,
                    error_code=(
                        OperationErrorCode.VALIDATION_ERROR
                    ),
                    error_message=validation_error,
                )
            )

        try:

            result = capability.execute(
                definition.operation_name,
                request.arguments,
            )

        except Exception as exc:

            logger.exception(
                "capability_operation_raised "
                "operation=%s",
                request.operation,
            )

            return (
                OperationResult.failure_result(
                    operation=request.operation,
                    error_code=(
                        classify_operation_exception(
                            exc
                        )
                    ),
                    error_message=str(exc),
                )
            )

        logger.info(
            "capability_operation_completed "
            "operation=%s status=%s",
            request.operation,
            result.status.value,
        )

        return result

    def _validate_arguments(
        self,
        definition: OperationDefinition,
        arguments: dict,
    ) -> str | None:
        """
        Confirm every required input parameter declared by the
        operation's schema is present in the request arguments.

        This is deliberately shallow: presence only, no type
        checking. Real type validation is left for a capability that
        actually needs it rather than speculatively built now.
        """

        missing = [
            parameter.name
            for parameter in (
                definition.schema.inputs
            )
            if parameter.required
            and parameter.name not in arguments
        ]

        if not missing:
            return None

        missing_list = ", ".join(missing)

        return (
            "Missing required argument(s): "
            f"{missing_list}"
        )


__all__ = [
    "CapabilityController",
]