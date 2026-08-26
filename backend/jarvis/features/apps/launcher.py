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
    Launches resolved applications using the appropriate
    Windows mechanism for their target type.
    """

    def launch(
        self,
        application: Application,
    ) -> bool:

        try:

            # ------------------------------------------
            # Executables
            # ------------------------------------------

            if (
                application.application_type
                == ApplicationType.EXECUTABLE
            ):

                os.startfile(
                    application.target
                )

                return True

            # ------------------------------------------
            # .lnk shortcuts
            # ------------------------------------------

            if (
                application.application_type
                == ApplicationType.SHORTCUT
            ):

                os.startfile(
                    application.target
                )

                return True

            # ------------------------------------------
            # Windows URI
            # ------------------------------------------

            if (
                application.application_type
                == ApplicationType.URI
            ):

                os.startfile(
                    application.target
                )

                return True

            # ------------------------------------------
            # Packaged / Store applications
            # ------------------------------------------

            if (
                application.application_type
                == ApplicationType.PACKAGED
            ):

                subprocess.Popen(
                    [
                        "explorer.exe",
                        application.target,
                    ],
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                    ),
                )

                return True

            # ------------------------------------------
            # Generic command
            # ------------------------------------------

            if (
                application.application_type
                == ApplicationType.COMMAND
            ):

                subprocess.Popen(
                    application.target,
                    shell=True,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                    ),
                )

                return True

            return False

        except (
            OSError,
            subprocess.SubprocessError,
        ):

            return False