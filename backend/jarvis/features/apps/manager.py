"""
High-level application management.
"""

from dataclasses import dataclass

from jarvis.features.apps.discovery import (
    ApplicationDiscovery,
)
from jarvis.features.apps.launcher import (
    ApplicationLauncher,
)
from jarvis.features.apps.models import (
    Application,
)
from jarvis.features.apps.resolver import (
    ApplicationResolver,
)
from jarvis.features.apps.verification import (
    ApplicationVerifier,
)
from jarvis.features.apps.resolver import (
    ApplicationResolver,
    ResolutionResult,
)


@dataclass(frozen=True)
class LaunchResult:
    success: bool
    application: Application | None
    message: str
    error: str | None = None


class ApplicationManager:
    """
    High-level interface for application discovery,
    resolution and launching.
    """

    def __init__(self) -> None:
        self.discovery = ApplicationDiscovery()
        self.resolver = ApplicationResolver()
        self.launcher = ApplicationLauncher()
        self.verifier = ApplicationVerifier()

        self._applications: list[Application] = []

    def refresh(self) -> list[Application]:
        """
        Rediscover installed applications.
        """

        self._applications = self.discovery.discover()

        return list(self._applications)

    def applications(self) -> list[Application]:
        """
        Return currently discovered applications.
        """

        if not self._applications:
            self.refresh()

        return list(self._applications)

    def resolve(
        self,
        query: str,
        refresh_on_miss: bool = True,
    ) -> Application | None:
        """
        Resolve an application query.
        """

        result = self.resolve_detailed(
            query,
            refresh_on_miss=refresh_on_miss,
        )

        return result.application
    def launch(
        self,
        query: str,
    ) -> LaunchResult:
        """
        Resolve and launch an application.
        """

        application = self.resolve(
            query,
            refresh_on_miss=True,
        )

        if application is None:
            return LaunchResult(
                success=False,
                application=None,
                message=f"Could not find application: {query}",
                error="application_not_found",
            )

        launched = self.launcher.launch(
            application
        )

        if not launched:
            return LaunchResult(
                success=False,
                application=application,
                message=f"Failed to launch {application.name}.",
                error="launch_failed",
            )

        verified = self.verifier.verify(
            application
        )

        if not verified:
            return LaunchResult(
                success=False,
                application=application,
                message=(
                    f"{application.name} launch was requested, "
                    "but the process could not be verified."
                ),
                error="verification_failed",
            )

        return LaunchResult(
            success=True,
            application=application,
            message=f"{application.name} launched successfully.",
        )
    def resolve_detailed(
        self,
        query: str,
        refresh_on_miss: bool = True,
    ) -> ResolutionResult:
        """
        Resolve an application and preserve candidate information.
        """

        result = self.resolver.resolve_detailed(
            query,
            self.applications(),
        )

        # If nothing useful was found, refresh discovery once.
        if (
            refresh_on_miss
            and not result.resolved
            and not result.ambiguous
        ):
            self.refresh()

            result = self.resolver.resolve_detailed(
                query,
                self._applications,
            )

        return result