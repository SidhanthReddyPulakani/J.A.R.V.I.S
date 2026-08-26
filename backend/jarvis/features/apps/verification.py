"""
Application launch verification.
"""

import time

import psutil

from jarvis.features.apps.models import Application


class ApplicationVerifier:
    """
    Performs basic verification that an application launched.
    """

    def verify(
        self,
        application: Application,
        timeout: float = 3.0,
    ) -> bool:
        """
        Attempt to verify that the application is running.

        This first implementation checks executable process names
        when the target is an executable.
        """

        target_name = application.target.lower()

        if not target_name.endswith(".exe"):
            # Shortcuts and other launch targets cannot reliably
            # be verified using only the target path.
            return True

        executable_name = (
            application.target
            .replace("\\", "/")
            .split("/")[-1]
            .lower()
        )

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._process_exists(executable_name):
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

                if name and name.lower() == executable_name:
                    return True

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                continue

        return False