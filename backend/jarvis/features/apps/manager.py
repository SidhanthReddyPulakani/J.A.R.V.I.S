"""
High-level application management.

ApplicationManager coordinates:

    Discovery
        ↓
    Resolution
        ↓
    Relationship learning
        ↓
    Launching
        ↓
    Verification
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
    ResolutionResult,
)
from jarvis.features.apps.verification import (
    ApplicationVerifier,
)

from jarvis.relationships.models import (
    Relationship,
)
from jarvis.relationships.store import (
    RelationshipStore,
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
    resolution, relationship learning and launching.
    """

    RELATIONSHIP_TARGET_TYPE = "application"

    def __init__(self) -> None:

        self.discovery = ApplicationDiscovery()

        self.resolver = ApplicationResolver()

        self.launcher = ApplicationLauncher()

        self.verifier = ApplicationVerifier()

        self.relationship_store = RelationshipStore()

        self._applications: list[Application] = []

    # ======================================================
    # Discovery
    # ======================================================

    def refresh(self) -> list[Application]:
        """
        Rediscover installed applications.
        """

        self._applications = (
            self.discovery.discover()
        )

        return list(
            self._applications
        )

    def applications(self) -> list[Application]:
        """
        Return currently discovered applications.

        Discovery is performed automatically when the
        application index has not been populated yet.
        """

        if not self._applications:
            self.refresh()

        return list(
            self._applications
        )

    # ======================================================
    # Resolution
    # ======================================================

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

    def resolve_detailed(
        self,
        query: str,
        refresh_on_miss: bool = True,
    ) -> ResolutionResult:
        """
        Resolve an application and preserve candidate
        information.
        """

        result = self.resolver.resolve_detailed(
            query,
            self.applications(),
        )

        # --------------------------------------------------
        # Refresh discovery when resolution fails.
        #
        # This allows newly installed applications to be
        # discovered without restarting Jarvis.
        # --------------------------------------------------

        if (
            refresh_on_miss
            and not result.resolved
            and not result.ambiguous
        ):

            self.refresh()

            result = (
                self.resolver.resolve_detailed(
                    query,
                    self._applications,
                )
            )

        return result

    # ======================================================
    # Relationship learning
    # ======================================================

    def learn_relationship(
        self,
        query: str,
        application: Application,
        confidence: float = 1.0,
    ) -> Relationship:
        """
        Store a relationship between a user's phrase and
        a discovered application.

        Example:

            query:
                "browser"

            application:
                Brave

        becomes:

            browser → application → Brave
        """

        relationship = Relationship(
            id=None,
            source=query,
            target_type=self.RELATIONSHIP_TARGET_TYPE,
            target=application.name,
            confidence=max(
                0.0,
                min(1.0, confidence),
            ),
            confirmations=1,
        )

        return self.relationship_store.save(
            relationship
        )

    def confirm_relationship(
        self,
        query: str,
        application: Application,
    ) -> Relationship:
        """
        Confirm or create a learned relationship.

        This is intended to be called when the user explicitly
        chooses an application from ambiguous candidates.
        """

        existing = (
            self.relationship_store.find_exact(
                source=query,
                target_type=self.RELATIONSHIP_TARGET_TYPE,
                target=application.name,
            )
        )

        if existing is None:

            return self.learn_relationship(
                query=query,
                application=application,
                confidence=1.0,
            )
        
        existing.confirmations += 1
        existing.confidence = 1.0

        return self.relationship_store.save(
            existing
        )

    def forget_relationship(
        self,
        query: str,
        application: Application,
    ) -> bool:
        """
        Remove a specific learned relationship.

        Returns True if the relationship existed and was
        removed.
        """

        existing = (
            self.relationship_store.find_exact(
                source=query,
                target_type=self.RELATIONSHIP_TARGET_TYPE,
                target=application.name,
            )
        )

        if existing is None:
            return False

        if existing.id is None:
            return False

        self.relationship_store.delete(
            existing.id
        )

        return True

    # ======================================================
    # Launching
    # ======================================================

    def launch(
        self,
        query: str,
    ) -> LaunchResult:
        """
        Resolve and launch an application.
        """

        result = self.resolve_detailed(
            query,
            refresh_on_miss=True,
        )

        # --------------------------------------------------
        # No application resolved.
        #
        # IMPORTANT:
        # We return candidates here rather than guessing.
        # The conversational/controller layer can later use
        # these candidates to ask the user.
        # --------------------------------------------------

        if result.application is None:

            if result.candidates:

                candidate_names = ", ".join(
                    application.name
                    for application in result.candidates
                )

                return LaunchResult(
                    success=False,
                    application=None,
                    message=(
                        f"I couldn't confidently identify "
                        f"'{query}'. Candidates: "
                        f"{candidate_names}"
                    ),
                    error=result.reason,
                )

            return LaunchResult(
                success=False,
                application=None,
                message=(
                    f"Could not find application: "
                    f"{query}"
                ),
                error="application_not_found",
            )

        application = result.application

        # --------------------------------------------------
        # Launch
        # --------------------------------------------------

        launched = self.launcher.launch(
            application
        )

        if not launched:

            return LaunchResult(
                success=False,
                application=application,
                message=(
                    f"Failed to launch "
                    f"{application.name}."
                ),
                error="launch_failed",
            )

        # --------------------------------------------------
        # Verification
        # --------------------------------------------------

        verified = self.verifier.verify(
            application
        )

        if not verified:

            return LaunchResult(
                success=False,
                application=application,
                message=(
                    f"{application.name} launch was "
                    "requested, but the process could "
                    "not be verified."
                ),
                error="verification_failed",
            )

        return LaunchResult(
            success=True,
            application=application,
            message=(
                f"{application.name} "
                "launched successfully."
            ),
        )


