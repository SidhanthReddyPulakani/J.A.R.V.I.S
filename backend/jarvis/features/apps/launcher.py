"""
Windows application launcher.
"""

import os
import subprocess

from jarvis.features.apps.models import (
    Application,
    ApplicationType,
)


class ApplicationLauncher:
    """
    Launches resolved applications.
    """

    def launch(
        self,
        application: Application,
    ) -> bool:
        """
        Attempt to launch an application.

        Returns True when Windows accepts the launch request.
        """

        try:
            if application.application_type in {
                ApplicationType.EXECUTABLE,
                ApplicationType.COMMAND,
            }:
                os.startfile(application.target)

                return True

            if application.application_type == ApplicationType.URI:
                os.startfile(application.target)

                return True

            return False

        except OSError:
            return False