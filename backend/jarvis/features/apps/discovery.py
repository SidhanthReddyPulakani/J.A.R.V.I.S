"""
Windows application discovery.

Discovery finds applications available to the user without
launching them.
"""

import os
from pathlib import Path

from jarvis.features.apps.models import (
    Application,
    ApplicationType,
)


class ApplicationDiscovery:
    """
    Discovers Windows applications from supported locations.
    """

    def discover(self) -> list[Application]:
        """
        Perform a fresh application discovery.
        """

        applications: list[Application] = []

        for directory in self._start_menu_directories():
            applications.extend(
                self._scan_directory(directory)
            )

        applications = self._remove_invalid(
            applications
        )

        applications = self._deduplicate(
            applications
        )

        applications.sort(
            key=lambda application: (
                application.name.lower(),
                application.target.lower(),
            )
        )

        return applications

    # --------------------------------------------------
    # Discovery locations
    # --------------------------------------------------

    def _start_menu_directories(self) -> list[Path]:
        """
        Return available Windows Start Menu locations.
        """

        directories: list[Path] = []

        appdata = os.environ.get("APPDATA")

        if appdata:
            directories.append(
                Path(appdata)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        program_data = os.environ.get("PROGRAMDATA")

        if program_data:
            directories.append(
                Path(program_data)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        return self._unique_paths(
            directories
        )

    # --------------------------------------------------
    # Directory scanning
    # --------------------------------------------------

    def _scan_directory(
        self,
        directory: Path,
    ) -> list[Application]:
        """
        Recursively scan a Start Menu directory.
        """

        applications: list[Application] = []

        try:
            entries = directory.rglob("*")
        except OSError:
            return applications

        for path in entries:

            try:
                if not path.is_file():
                    continue
            except OSError:
                continue

            suffix = path.suffix.lower()

            if suffix == ".lnk":
                application = (
                    self._from_shortcut(path)
                )

                if application:
                    applications.append(
                        application
                    )

            elif suffix == ".exe":
                application = (
                    self._from_executable(path)
                )

                if application:
                    applications.append(
                        application
                    )

        return applications

    # --------------------------------------------------
    # Application creation
    # --------------------------------------------------

    def _from_shortcut(
        self,
        path: Path,
    ) -> Application | None:
        """
        Create an Application from a Windows shortcut.

        The shortcut itself is retained as the launch target.
        """

        name = self._clean_name(
            path.stem
        )

        if not name:
            return None

        return Application(
            name=name,
            target=str(path),
            application_type=ApplicationType.COMMAND,
            source="start_menu_shortcut",
        )

    def _from_executable(
        self,
        path: Path,
    ) -> Application | None:
        """
        Create an Application from an executable.
        """

        name = self._clean_name(
            path.stem
        )

        if not name:
            return None

        return Application(
            name=name,
            target=str(path),
            application_type=ApplicationType.EXECUTABLE,
            source="start_menu_executable",
        )

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def _remove_invalid(
        self,
        applications: list[Application],
    ) -> list[Application]:
        """
        Remove entries whose launch target no longer exists.
        """

        valid: list[Application] = []

        for application in applications:

            try:
                target = Path(
                    application.target
                )

                if not target.exists():
                    continue

            except (OSError, ValueError):
                continue

            valid.append(
                application
            )

        return valid

    # --------------------------------------------------
    # Deduplication
    # --------------------------------------------------

    def _deduplicate(
        self,
        applications: list[Application],
    ) -> list[Application]:
        """
        Remove duplicate applications.

        The target path is the strongest identity.
        """

        seen_targets: set[str] = set()
        result: list[Application] = []

        for application in applications:

            target_key = self._normalize_path(
                application.target
            )

            if target_key in seen_targets:
                continue

            seen_targets.add(
                target_key
            )

            result.append(
                application
            )

        return result

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    @staticmethod
    def _clean_name(
        name: str,
    ) -> str:
        """
        Normalize an application display name.
        """

        return " ".join(
            name.strip().split()
        )

    @staticmethod
    def _normalize_path(
        path: str,
    ) -> str:
        """
        Normalize a Windows path for comparison.
        """

        try:
            return str(
                Path(path)
                .resolve()
            ).lower()
        except OSError:
            return path.strip().lower()

    @staticmethod
    def _unique_paths(
        paths: list[Path],
    ) -> list[Path]:
        """
        Remove duplicate directory paths.
        """

        seen: set[str] = set()
        result: list[Path] = []

        for path in paths:

            key = str(path).lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(path)

        return result