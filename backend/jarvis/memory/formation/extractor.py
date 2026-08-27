"""
Deterministic memory candidate extraction.

The extractor identifies explicit or strongly structured
memory-worthy statements without requiring an LLM.

This is intentionally conservative.

It does NOT assume:

    message == memory

Instead it looks for signals such as:

    "remember that ..."
    "remember my ..."
    "I prefer ..."
    "my ... is ..."
    "I use ..."
    "I'm working on ..."
    "I switched to ..."

An LLM-assisted extractor can be introduced later behind
the same output contract.
"""

import re

from jarvis.memory.formation.models import (
    MemoryCandidate,
    MemorySource,
    RetentionReason,
)


class MemoryCandidateExtractor:
    """
    Extract MemoryCandidate objects from experience text.
    """

    _EXPLICIT_PATTERNS = (
        re.compile(
            r"^\s*remember\s+(?:that\s+)?(.+?)[.!?]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*please\s+remember\s+(?:that\s+)?(.+?)[.!?]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*don't\s+forget\s+(?:that\s+)?(.+?)[.!?]?\s*$",
            re.IGNORECASE,
        ),
    )

    _PREFERENCE_PATTERN = re.compile(
        r"^\s*i\s+prefer\s+(.+?)[.!?]?\s*$",
        re.IGNORECASE,
    )

    _PROJECT_PATTERN = re.compile(
        r"^\s*(?:my|the)\s+main\s+project\s+is\s+(.+?)[.!?]?\s*$",
        re.IGNORECASE,
    )

    _WORKING_PATTERN = re.compile(
        r"^\s*i(?:'m|\s+am)\s+working\s+on\s+(.+?)[.!?]?\s*$",
        re.IGNORECASE,
    )

    _USE_PATTERN = re.compile(
        r"^\s*i\s+(?:use|am\s+using)\s+(.+?)[.!?]?\s*$",
        re.IGNORECASE,
    )

    _SWITCH_PATTERN = re.compile(
        r"^\s*i\s+(?:switched|moved)\s+"
        r"(?:from\s+(.+?)\s+)?"
        r"(?:to|over\s+to)\s+(.+?)[.!?]?\s*$",
        re.IGNORECASE,
    )

    def extract(
        self,
        text: str,
        source: MemorySource = MemorySource.CONVERSATION,
        project: str | None = None,
        source_id: int | str | None = None,
    ) -> list[MemoryCandidate]:
        """
        Extract zero or more candidates from text.

        The extractor intentionally returns an empty list
        for ordinary conversation.
        """

        if not text or not text.strip():
            return []

        candidates: list[MemoryCandidate] = []

        explicit = self._match_explicit(text)

        if explicit is not None:

            candidates.append(
                self._candidate(
                    content=explicit,
                    source=source,
                    reason=(
                        RetentionReason.EXPLICIT_REQUEST
                    ),
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        preference = (
            self._PREFERENCE_PATTERN.match(text)
        )

        if preference:

            content = (
                f"User prefers "
                f"{self._clean(preference.group(1))}."
            )

            candidates.append(
                self._candidate(
                    content=content,
                    source=source,
                    reason=RetentionReason.PREFERENCE,
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        project_match = (
            self._PROJECT_PATTERN.match(text)
        )

        if project_match:

            content = (
                "User's main project is "
                f"{self._clean(project_match.group(1))}."
            )

            candidates.append(
                self._candidate(
                    content=content,
                    source=source,
                    reason=(
                        RetentionReason.PROJECT_CONTEXT
                    ),
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        working = (
            self._WORKING_PATTERN.match(text)
        )

        if working:

            content = (
                "User is working on "
                f"{self._clean(working.group(1))}."
            )

            candidates.append(
                self._candidate(
                    content=content,
                    source=source,
                    reason=(
                        RetentionReason.PROJECT_CONTEXT
                    ),
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        use_match = self._USE_PATTERN.match(
            text
        )

        if use_match:

            value = self._clean(
                use_match.group(1)
            )

            candidates.append(
                self._candidate(
                    content=(
                        f"User uses {value}."
                    ),
                    source=source,
                    reason=(
                        RetentionReason.PERSONAL_FACT
                    ),
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        switch_match = (
            self._SWITCH_PATTERN.match(text)
        )

        if switch_match:

            old_value = (
                switch_match.group(1)
            )

            new_value = (
                self._clean(
                    switch_match.group(2)
                )
            )

            if old_value:

                old_value = self._clean(
                    old_value
                )

                content = (
                    "User switched from "
                    f"{old_value} to {new_value}."
                )

            else:

                content = (
                    f"User switched to "
                    f"{new_value}."
                )

            candidates.append(
                self._candidate(
                    content=content,
                    source=source,
                    reason=(
                        RetentionReason.CORRECTION
                    ),
                    project=project,
                    source_id=source_id,
                )
            )

            return candidates

        return candidates

    @staticmethod
    def _match_explicit(
        text: str,
    ) -> str | None:

        for pattern in (
            MemoryCandidateExtractor
            ._EXPLICIT_PATTERNS
        ):

            match = pattern.match(text)

            if match:

                return (
                    MemoryCandidateExtractor
                    ._clean(match.group(1))
                )

        return None

    @staticmethod
    def _candidate(
        content: str,
        source: MemorySource,
        reason: RetentionReason,
        project: str | None,
        source_id: int | str | None,
    ) -> MemoryCandidate:

        return MemoryCandidate(
            content=content,
            source=source,
            reason=reason,
            confidence=(
                1.0
                if reason
                == RetentionReason.EXPLICIT_REQUEST
                else 0.90
            ),
            importance=(
                0.90
                if reason
                == RetentionReason.EXPLICIT_REQUEST
                else 0.70
            ),
            project=project,
            source_id=source_id,
        )

    @staticmethod
    def _clean(
        value: str,
    ) -> str:

        value = value.strip()

        value = value.rstrip(
            ".!?"
        )

        return value.strip()