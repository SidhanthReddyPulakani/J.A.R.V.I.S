from jarvis.memory.formation import (
    MemoryCandidateExtractor,
    MemorySource,
    RetentionReason,
)


def main() -> None:

    extractor = (
        MemoryCandidateExtractor()
    )

    # -----------------------------------------------
    # Ordinary conversation
    # -----------------------------------------------

    candidates = extractor.extract(
        "Hey Jarvis."
    )

    assert candidates == []

    print(
        "PASS: Ordinary conversation produces "
        "no memory candidate."
    )

    # -----------------------------------------------
    # Explicit request
    # -----------------------------------------------

    candidates = extractor.extract(
        "Remember that my primary editor is Cursor.",
        source=MemorySource.USER,
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert (
        candidate.reason
        == RetentionReason.EXPLICIT_REQUEST
    )

    assert (
        candidate.content
        == "my primary editor is Cursor"
    )

    assert (
        candidate.confidence
        == 1.0
    )

    print(
        "PASS: Explicit memory request "
        "produces a candidate."
    )

    # -----------------------------------------------
    # Preference
    # -----------------------------------------------

    candidates = extractor.extract(
        "I prefer dark mode."
    )

    assert len(candidates) == 1

    assert (
        candidates[0].reason
        == RetentionReason.PREFERENCE
    )

    assert (
        candidates[0].content
        == "User prefers dark mode."
    )

    print(
        "PASS: Preference extraction works."
    )

    # -----------------------------------------------
    # Project context
    # -----------------------------------------------

    candidates = extractor.extract(
        "I'm working on Jarvis.",
        project="Jarvis",
    )

    assert len(candidates) == 1

    assert (
        candidates[0].reason
        == RetentionReason.PROJECT_CONTEXT
    )

    assert (
        candidates[0].project
        == "Jarvis"
    )

    print(
        "PASS: Project-context extraction works."
    )

    # -----------------------------------------------
    # Personal fact
    # -----------------------------------------------

    candidates = extractor.extract(
        "I use Cursor."
    )

    assert len(candidates) == 1

    assert (
        candidates[0].reason
        == RetentionReason.PERSONAL_FACT
    )

    assert (
        candidates[0].content
        == "User uses Cursor."
    )

    print(
        "PASS: Personal-fact extraction works."
    )

    # -----------------------------------------------
    # Correction / switch
    # -----------------------------------------------

    candidates = extractor.extract(
        "I switched from VS Code to Cursor."
    )

    assert len(candidates) == 1

    assert (
        candidates[0].reason
        == RetentionReason.CORRECTION
    )

    assert (
        candidates[0].content
        == (
            "User switched from "
            "VS Code to Cursor."
        )
    )

    print(
        "PASS: Correction extraction works."
    )

    # -----------------------------------------------
    # Empty input
    # -----------------------------------------------

    assert (
        extractor.extract("")
        == []
    )

    assert (
        extractor.extract("   ")
        == []
    )

    print(
        "PASS: Empty experiences are ignored."
    )

    print()
    print(
        "PASS: Memory candidate extraction works."
    )


if __name__ == "__main__":
    main()