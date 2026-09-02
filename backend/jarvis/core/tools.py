import webbrowser
from datetime import datetime
from typing import Callable


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
    "open_url": open_url,
    "get_current_datetime": get_current_datetime,
}