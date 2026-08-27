from jarvis.memory.formation import (
    MemoryCandidate,
    MemorySource,
    RetentionReason,
)


def main() -> None:

    candidate = MemoryCandidate(
        content=(
            "Sidhanth uses Cursor as "
            "his primary editor."
        ),
        source=MemorySource.USER,
        reason=RetentionReason.PREFERENCE,
        confidence=0.98,
        importance=0.85,
        category="preference",
        subject="editor",
        project="Jarvis",
        source_id=123,
        metadata={
            "explicit": True,
            "test": True,
        },
    )

    # --------------------------------------------------
    # Core fields
    # --------------------------------------------------

    assert (
        candidate.content
        == "Sidhanth uses Cursor as "
        "his primary editor."
    )

    assert (
        candidate.source
        == MemorySource.USER
    )

    assert (
        candidate.reason
        == RetentionReason.PREFERENCE
    )

    # --------------------------------------------------
    # Scoring
    # --------------------------------------------------

    assert (
        candidate.confidence
        == 0.98
    )

    assert (
        candidate.importance
        == 0.85
    )

    # --------------------------------------------------
    # Classification
    # --------------------------------------------------

    assert (
        candidate.category
        == "preference"
    )

    assert (
        candidate.subject
        == "editor"
    )

    assert (
        candidate.project
        == "Jarvis"
    )

    # --------------------------------------------------
    # Provenance
    # --------------------------------------------------

    assert (
        candidate.source_id
        == 123
    )

    assert (
        candidate.metadata["explicit"]
        is True
    )

    # --------------------------------------------------
    # Serialization
    # --------------------------------------------------

    serialized = (
        candidate.to_dict()
    )

    assert (
        serialized["content"]
        == candidate.content
    )

    assert (
        serialized["source"]
        == "user"
    )

    assert (
        serialized["reason"]
        == "preference"
    )

    assert (
        serialized["confidence"]
        == 0.98
    )

    assert (
        serialized["importance"]
        == 0.85
    )

    # --------------------------------------------------
    # Empty content rejected
    # --------------------------------------------------

    try:

        MemoryCandidate(
            content="   ",
            source=MemorySource.USER,
            reason=(
                RetentionReason.PERSONAL_FACT
            ),
        )

        raise AssertionError(
            "Empty content should fail."
        )

    except ValueError:
        pass

    # --------------------------------------------------
    # Invalid confidence rejected
    # --------------------------------------------------

    try:

        MemoryCandidate(
            content="Valid candidate",
            source=MemorySource.USER,
            reason=(
                RetentionReason.PERSONAL_FACT
            ),
            confidence=1.5,
        )

        raise AssertionError(
            "Invalid confidence should fail."
        )

    except ValueError:
        pass

    # --------------------------------------------------
    # Invalid importance rejected
    # --------------------------------------------------

    try:

        MemoryCandidate(
            content="Valid candidate",
            source=MemorySource.USER,
            reason=(
                RetentionReason.PERSONAL_FACT
            ),
            importance=-0.1,
        )

        raise AssertionError(
            "Invalid importance should fail."
        )

    except ValueError:
        pass

    print(
        "MEMORY CANDIDATE:"
    )

    print(
        candidate.to_dict()
    )

    print()

    print(
        "PASS: MemoryCandidate contract works."
    )

    print(
        "PASS: Candidate validation works."
    )

    print(
        "PASS: Candidate serialization works."
    )


if __name__ == "__main__":
    main()