"""
Jarvis Diary package.

The package intentionally avoids eagerly importing the service module
here.

This is important because:

    storage.repositories.diary
        -> jarvis.diary.models
        -> jarvis.diary package initialization

Eagerly importing DiaryService from this package would create a
circular dependency back into the repository (service.py imports
DiaryRepository from jarvis.storage.repositories.diary, which may
still be mid-import when it is the module that triggered this
package init in the first place).

The public names are therefore exposed lazily through __getattr__.
"""

from __future__ import annotations


__all__ = [
    "DiaryEvent",
    "DiaryService",
]


def __getattr__(name: str):
    """
    Lazily resolve public diary-package exports.
    """

    if name == "DiaryEvent":
        from jarvis.diary.models import DiaryEvent

        return DiaryEvent

    if name == "DiaryService":
        from jarvis.diary.service import DiaryService

        return DiaryService

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )