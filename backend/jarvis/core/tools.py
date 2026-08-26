import webbrowser
from datetime import datetime
from typing import Callable

from jarvis.features.apps.manager import (
    ApplicationManager,
)


# One application manager for the backend process.
_application_manager = ApplicationManager()


def open_application(app: str) -> str:
    """Open a Windows application.

    Args:
        app: Application name, alias, executable name, or
             user-provided application description.
    """

    try:
        result = _application_manager.launch(
            app
        )

        if result.success:
            return result.message

        if result.candidates:
            candidates = "\n".join(
                f"- {candidate.name}"
                for candidate in result.candidates
            )

            return (
                f"I couldn't confidently identify "
                f"'{app}'.\n"
                f"Possible matches:\n"
                f"{candidates}"
            )

        return result.message

    except Exception as exc:
        return (
            f"Could not open {app}: {exc}"
        )


def open_url(url: str) -> str:
    """Open a URL in the default browser.

    Args:
        url: Full URL to open.
    """
    try:
        webbrowser.open(url)
        return f"Opened {url}."
    except Exception as exc:
        return f"Could not open {url}: {exc}"


def get_current_datetime() -> str:
    """Get the current local date and time."""
    return datetime.now().astimezone().strftime(
        "%A, %d %B %Y, %I:%M:%S %p"
    )


AVAILABLE_TOOLS: dict[str, Callable] = {
    "open_application": open_application,
    "open_url": open_url,
    "get_current_datetime": get_current_datetime,
}