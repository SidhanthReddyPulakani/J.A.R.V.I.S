"""
Application launch verification.
"""

import time

import psutil

from jarvis.features.apps.models import (
    Application,
    ApplicationType,
)


class ApplicationVerifier:
    """
    Performs best-effort verification that an application
    launch actually resulted in a running application.
    """

    def verify(
        self,
        application: Application,
        timeout: float = 4.0,
    ) -> bool:

        # ----------------------------------------------
        # Executable
        # ----------------------------------------------

        if (
            application.application_type
            == ApplicationType.EXECUTABLE
        ):

            executable_name = (
                application.target
                .replace("\\", "/")
                .split("/")[-1]
                .lower()
            )

            return self._wait_for_process(
                executable_name,
                timeout,
            )

        # ----------------------------------------------
        # Shortcut
        #
        # We don't know the shortcut's target without
        # resolving the .lnk. Launching the shortcut
        # successfully is sufficient at this layer.
        #
        # A future Windows-specific verifier can inspect
        # the actual shortcut target/process.
        # ----------------------------------------------

        if (
            application.application_type
            == ApplicationType.SHORTCUT
        ):

            return True

        # ----------------------------------------------
        # Packaged app
        #
        # The Windows shell accepted the AppsFolder
        # launch request. Packaged applications do not
        # expose a stable executable name that we can
        # safely infer from the AppID.
        # ----------------------------------------------

        if (
            application.application_type
            == ApplicationType.PACKAGED
        ):

            return True

        # ----------------------------------------------
        # URI
        # ----------------------------------------------

        if (
            application.application_type
            == ApplicationType.URI
        ):

            return True

        # ----------------------------------------------
        # Generic command
        # ----------------------------------------------

        if (
            application.application_type
            == ApplicationType.COMMAND
        ):

            return True

        return False

    @staticmethod
    def _wait_for_process(
        executable_name: str,
        timeout: float,
    ) -> bool:

        deadline = (
            time.monotonic()
            + timeout
        )

        while (
            time.monotonic()
            < deadline
        ):

            if ApplicationVerifier._process_exists(
                executable_name
            ):
                return True

            time.sleep(0.15)

        return False

    @staticmethod
    def _process_exists(
        executable_name: str,
    ) -> bool:

        for process in psutil.process_iter(
            ["name"]
        ):

            try:

                name = process.info["name"]

                if (
                    name
                    and name.lower()
                    == executable_name
                ):
                    return True

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):

                continue

        return False