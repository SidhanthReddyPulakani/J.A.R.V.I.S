"""
P13 — Migrate features/apps/ into the first real Capability.

This wraps the existing, already-solid Apps subsystem (discovery,
resolver, launcher, verification, manager) behind the P9-P12
contracts. It exposes `apps.find`, `apps.resolve`, and `apps.launch`
through the Controller. `apps.close` is left for later, matching the
roadmap's own note.

This is packaging, not a rewrite: every operation below delegates
directly to the existing ApplicationManager. The only new logic is
translating ApplicationManager's own result types (LaunchResult,
ResolutionResult) into OperationResult, including the P10 states
that distinguish "could not find it" (NOT_FOUND) from "found more
than one, need the user to choose" (REQUIRES_INPUT) — the exact
example the roadmap itself uses to motivate having those states at
all.
"""

from __future__ import annotations

from typing import Any

from jarvis.capabilities.contracts import (
    Capability,
    CapabilityMetadata,
    OperationDefinition,
    OperationParameter,
    OperationSchema,
)
from jarvis.features.apps.manager import ApplicationManager
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationState,
)


class ApplicationsCapability(Capability):
    """
    The Apps capability: find, resolve, and launch applications.

    Accepts an existing ApplicationManager (or any object exposing
    the same `applications()` / `resolve_detailed()` / `launch()`
    surface) so tests can inject a fake manager instead of hitting
    real OS-level discovery, launching, and process verification.
    """

    def __init__(
        self,
        manager: ApplicationManager | None = None,
    ) -> None:

        self._manager = (
            manager
            if manager is not None
            else ApplicationManager()
        )

    @property
    def metadata(self) -> CapabilityMetadata:

        return CapabilityMetadata(
            name="apps",
            identity=(
                "jarvis.capabilities.apps_capability"
                ".ApplicationsCapability"
            ),
            version="1.0.0",
        )

    def operations(
        self,
    ) -> tuple[OperationDefinition, ...]:

        query_parameter = OperationParameter(
            name="query",
            type="str",
            required=True,
            description=(
                "Application name, alias, or "
                "user-provided description."
            ),
        )

        return (
            OperationDefinition(
                capability_name="apps",
                operation_name="find",
                description=(
                    "Search discovered applications by "
                    "name, without resolving to a single "
                    "result or launching anything."
                ),
                schema=OperationSchema(
                    inputs=(query_parameter,),
                    outputs=(
                        "A list of matching application "
                        "names."
                    ),
                ),
            ),
            OperationDefinition(
                capability_name="apps",
                operation_name="resolve",
                description=(
                    "Resolve a query to exactly one "
                    "application, or report ambiguous or "
                    "not-found candidates without "
                    "launching anything."
                ),
                schema=OperationSchema(
                    inputs=(query_parameter,),
                    outputs=(
                        "The resolved application's name "
                        "on success; candidate names when "
                        "ambiguous."
                    ),
                ),
            ),
            OperationDefinition(
                capability_name="apps",
                operation_name="launch",
                description=(
                    "Resolve and launch an application."
                ),
                schema=OperationSchema(
                    inputs=(query_parameter,),
                    outputs=(
                        "A confirmation message once the "
                        "application has launched and been "
                        "verified running."
                    ),
                    requirements=(
                        "Launching and verification are "
                        "Windows-specific "
                        "(os.startfile / psutil).",
                    ),
                ),
            ),
        )

    def execute(
        self,
        operation_name: str,
        arguments: dict[str, Any],
    ) -> OperationResult:

        if operation_name == "find":
            return self._find(**arguments)

        if operation_name == "resolve":
            return self._resolve(**arguments)

        if operation_name == "launch":
            return self._launch(**arguments)

        return (
            OperationResult.failure_result(
                operation=f"apps.{operation_name}",
                error_code=(
                    OperationErrorCode.NOT_FOUND
                ),
                error_message=(
                    "Unknown apps operation: "
                    f"{operation_name}"
                ),
            )
        )

    # ======================================================
    # Operations
    # ======================================================

    def _find(
        self,
        query: str,
    ) -> OperationResult:

        normalized_query = (
            query.strip().lower()
        )

        matches = [
            application.name
            for application in (
                self._manager.applications()
            )
            if normalized_query
            in application.normalized_name
        ]

        return (
            OperationResult.from_state(
                operation="apps.find",
                state=OperationState.SUCCESS,
                data=matches,
            )
        )

    def _resolve(
        self,
        query: str,
    ) -> OperationResult:

        result = (
            self._manager.resolve_detailed(
                query
            )
        )

        if result.resolved:

            return (
                OperationResult.from_state(
                    operation="apps.resolve",
                    state=OperationState.SUCCESS,
                    data=result.application.name,
                )
            )

        if result.ambiguous:

            candidate_names = [
                application.name
                for application in result.candidates
            ]

            return (
                OperationResult.from_state(
                    operation="apps.resolve",
                    state=(
                        OperationState.REQUIRES_INPUT
                    ),
                    data={
                        "candidates": candidate_names
                    },
                    error_message=(
                        f"Found {len(candidate_names)} "
                        "matching applications."
                    ),
                )
            )

        return (
            OperationResult.from_state(
                operation="apps.resolve",
                state=OperationState.NOT_FOUND,
                error_message=(
                    f"Could not find application: "
                    f"{query}"
                ),
            )
        )

    def _launch(
        self,
        query: str,
    ) -> OperationResult:

        result = self._manager.launch(
            query
        )

        if result.success:

            return (
                OperationResult.from_state(
                    operation="apps.launch",
                    state=OperationState.SUCCESS,
                    data=result.message,
                )
            )

        # --------------------------------------------------
        # Two different reasons `application` can be None:
        #
        # 1. Nothing resolved at all -> NOT_FOUND.
        # 2. Candidates existed but nothing was confident
        #    enough to launch automatically -> REQUIRES_INPUT.
        #
        # ApplicationManager.launch() sets error to the fixed
        # sentinel "application_not_found" only for case (1);
        # any other error value alongside application=None
        # means candidates existed (see manager.py's own
        # branching). Reading these structured fields avoids
        # parsing the human-readable message.
        # --------------------------------------------------

        if (
            result.application is None
            and result.error
            == "application_not_found"
        ):

            return (
                OperationResult.from_state(
                    operation="apps.launch",
                    state=OperationState.NOT_FOUND,
                    error_message=result.message,
                )
            )

        if result.application is None:

            return (
                OperationResult.from_state(
                    operation="apps.launch",
                    state=(
                        OperationState.REQUIRES_INPUT
                    ),
                    error_message=result.message,
                )
            )

        # Application resolved, but launch or verification
        # failed.

        return (
            OperationResult.from_state(
                operation="apps.launch",
                state=OperationState.FAILED,
                error_message=result.message,
            )
        )


__all__ = [
    "ApplicationsCapability",
]