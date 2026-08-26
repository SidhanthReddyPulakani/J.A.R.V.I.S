"""
Application models used by the Jarvis application manager.
"""

from dataclasses import dataclass
from enum import Enum


class ApplicationType(str, Enum):
    EXECUTABLE = "executable"
    URI = "uri"
    COMMAND = "command"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Application:
    """
    Represents a discovered Windows application.
    """

    name: str
    target: str
    application_type: ApplicationType
    source: str | None = None

    @property
    def normalized_name(self) -> str:
        return self.name.strip().lower()