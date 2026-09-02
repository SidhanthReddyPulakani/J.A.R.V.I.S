"""
Public interface for the Jarvis memory subsystem.

The package intentionally avoids eagerly importing service and repository
modules here.

This is important because:

    storage.repositories.core_memory
        -> jarvis.memory.models
        -> jarvis.memory package initialization

Eagerly importing CoreMemoryService from this package would create a
circular dependency back into the repository.

The public names are therefore exposed lazily through __getattr__.
"""

from __future__ import annotations


__all__ = [
    "MemoryBlock",
    "CoreMemoryService",
    "LongTermMemory",
    "LongTermMemoryService",
    "AgentMemoryOperations",
    "get_memory_operation_definitions",
    "FormationAction",
    "FormationDecision",
    "MemoryCandidate",
    "MemoryEvaluator",
    "MemoryFormationService",
    "MemorySource",
    "RetentionReason",
    "OperationStatus",
    "OperationState",
    "OperationErrorCode",
    "OperationResult",
    "classify_operation_exception",
]


def __getattr__(name: str):
    """
    Lazily resolve public memory-package exports.

    Keeping these imports lazy prevents package initialization from
    importing services that depend on repositories which themselves
    import memory models.
    """

    if name == "MemoryBlock":
        from jarvis.memory.models import MemoryBlock

        return MemoryBlock

    if name == "LongTermMemory":
        from jarvis.memory.models import LongTermMemory

        return LongTermMemory

    if name == "CoreMemoryService":
        from jarvis.memory.service import CoreMemoryService

        return CoreMemoryService

    if name == "LongTermMemoryService":
        from jarvis.memory.long_term import LongTermMemoryService

        return LongTermMemoryService

    if name == "AgentMemoryOperations":
        from jarvis.memory.operations import AgentMemoryOperations

        return AgentMemoryOperations

    if name == "get_memory_operation_definitions":
        from jarvis.memory.operation_definitions import (
            get_memory_operation_definitions,
        )

        return get_memory_operation_definitions

    if name == "OperationStatus":
        from jarvis.memory.operation_results import OperationStatus

        return OperationStatus

    if name == "OperationState":
        from jarvis.memory.operation_results import OperationState

        return OperationState

    if name == "OperationErrorCode":
        from jarvis.memory.operation_results import OperationErrorCode

        return OperationErrorCode

    if name == "OperationResult":
        from jarvis.memory.operation_results import OperationResult

        return OperationResult

    if name == "classify_operation_exception":
        from jarvis.memory.operation_results import (
            classify_operation_exception,
        )

        return classify_operation_exception

    if name == "FormationAction":
        from jarvis.memory.formation import FormationAction

        return FormationAction

    if name == "FormationDecision":
        from jarvis.memory.formation import FormationDecision

        return FormationDecision

    if name == "MemoryCandidate":
        from jarvis.memory.formation import MemoryCandidate

        return MemoryCandidate

    if name == "MemoryEvaluator":
        from jarvis.memory.formation import MemoryEvaluator

        return MemoryEvaluator

    if name == "MemoryFormationService":
        from jarvis.memory.formation import MemoryFormationService

        return MemoryFormationService

    if name == "MemorySource":
        from jarvis.memory.formation import MemorySource

        return MemorySource

    if name == "RetentionReason":
        from jarvis.memory.formation import RetentionReason

        return RetentionReason

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )