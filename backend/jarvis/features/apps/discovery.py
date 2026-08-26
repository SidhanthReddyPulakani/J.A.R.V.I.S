"""
Windows application discovery.

Discovery sources:

1. Start Menu shortcuts/executables
2. Windows registered Start Apps / packaged applications

Discovery never launches applications.
"""

import json
import os
import subprocess
from pathlib import Path

from jarvis.features.apps.models import (
    Application,
    ApplicationType,
)


class ApplicationDiscovery:
    """
    Discovers applications available to the user.
    """

    def discover(self) -> list[Application]:

        applications: list[Application] = []

        # ----------------------------------------------
        # Traditional Start Menu applications
        # ----------------------------------------------

        for directory in self._start_menu_directories():
            applications.extend(
                self._scan_directory(directory)
            )

        # ----------------------------------------------
        # Windows registered / packaged applications
        # ----------------------------------------------

        applications.extend(
            self._discover_registered_apps()
        )

        # ----------------------------------------------
        # Clean up
        # ----------------------------------------------

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

    # ==================================================
    # Start Menu
    # ==================================================

    def _start_menu_directories(self) -> list[Path]:

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

    def _scan_directory(
        self,
        directory: Path,
    ) -> list[Application]:

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

    # ==================================================
    # Traditional application creation
    # ==================================================

    def _from_shortcut(
        self,
        path: Path,
    ) -> Application | None:

        name = self._clean_name(
            path.stem
        )

        if not name:
            return None

        return Application(
            name=name,
            target=str(path),
            application_type=ApplicationType.SHORTCUT,
            source="start_menu_shortcut",
        )

    def _from_executable(
        self,
        path: Path,
    ) -> Application | None:

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

    # ==================================================
    # Windows registered applications
    # ==================================================

    def _discover_registered_apps(
        self,
    ) -> list[Application]:

        command = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "Get-StartApps | "
                "Select-Object Name, AppID | "
                "ConvertTo-Json -Compress"
            ),
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                ),
            )

        except (
            OSError,
            subprocess.SubprocessError,
        ):

            return []

        if result.returncode != 0:
            return []

        output = result.stdout.strip()

        if not output:
            return []

        try:
            data = json.loads(output)

        except json.JSONDecodeError:
            return []

        if isinstance(data, dict):
            data = [data]

        applications: list[Application] = []

        for item in data:

            if not isinstance(item, dict):
                continue

            name = item.get("Name")
            app_id = item.get("AppID")

            if not name or not app_id:
                continue

            name = self._clean_name(
                str(name)
            )

            app_id = str(app_id).strip()

            if not name or not app_id:
                continue

            # Packaged Windows applications normally expose
            # an AppID containing '!'.
            #
            # We deliberately filter these here so that
            # ordinary Win32 applications aren't duplicated
            # with our Start Menu discovery.
            if "!" not in app_id:
                continue

            target = (
                "shell:AppsFolder\\"
                + app_id
            )

            applications.append(
                Application(
                    name=name,
                    target=target,
                    application_type=(
                        ApplicationType.PACKAGED
                    ),
                    source="windows_start_apps",
                )
            )

        return applications

    # ==================================================
    # Validation
    # ==================================================

    def _remove_invalid(
        self,
        applications: list[Application],
    ) -> list[Application]:

        valid: list[Application] = []

        for application in applications:

            # Windows shell targets do not correspond
            # to normal filesystem paths.
            if application.application_type in {
                ApplicationType.PACKAGED,
                ApplicationType.URI,
            }:
                valid.append(application)
                continue

            try:

                target = Path(
                    application.target
                )

                if not target.exists():
                    continue

            except (
                OSError,
                ValueError,
            ):
                continue

            valid.append(application)

        return valid

    # ==================================================
    # Deduplication
    # ==================================================

    def _deduplicate(
        self,
        applications: list[Application],
    ) -> list[Application]:

        seen: set[tuple[str, str]] = set()

        result: list[Application] = []

        for application in applications:

            key = (
                application.normalized_name,
                application.target.strip().lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(
                application
            )

        return result

    # ==================================================
    # Helpers
    # ==================================================

    @staticmethod
    def _clean_name(
        name: str,
    ) -> str:

        return " ".join(
            name.strip().split()
        )

    @staticmethod
    def _unique_paths(
        paths: list[Path],
    ) -> list[Path]:

        seen: set[str] = set()
        result: list[Path] = []

        for path in paths:

            key = str(path).lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(path)

        return result