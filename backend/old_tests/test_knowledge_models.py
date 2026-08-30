from jarvis.knowledge import (
    KnowledgeDocument,
    KnowledgePassage,
    KnowledgeSource,
)


def main() -> None:

    source = KnowledgeSource(
        name="Jarvis Documentation",
        source_type="file",
        origin="docs/",
        metadata={
            "project": "Jarvis",
        },
    )

    assert source.id is None
    assert source.name == "Jarvis Documentation"
    assert source.source_type == "file"
    assert source.origin == "docs/"
    assert source.ingestion_status == "pending"

    document = KnowledgeDocument(
        source_id=1,
        title="architecture.md",
        content_type="text/markdown",
        external_id="architecture.md",
        metadata={
            "project": "Jarvis",
        },
        content_hash="abc123",
    )

    assert document.source_id == 1
    assert document.title == "architecture.md"
    assert document.content_type == "text/markdown"
    assert document.content_hash == "abc123"

    passage = KnowledgePassage(
        document_id=1,
        sequence=0,
        content=(
            "The LLM is the reasoning engine "
            "surrounded by persistent state."
        ),
        metadata={
            "section": "Architecture",
            "page": 1,
        },
        content_hash="passage123",
    )

    assert passage.document_id == 1
    assert passage.sequence == 0
    assert "reasoning engine" in passage.content
    assert passage.metadata["section"] == "Architecture"

    try:

        KnowledgeSource(
            name="",
            source_type="file",
            origin="test",
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Empty source name should be rejected."
        )

    try:

        KnowledgePassage(
            document_id=1,
            sequence=-1,
            content="Invalid passage",
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Negative passage sequence "
            "should be rejected."
        )

    try:

        KnowledgePassage(
            document_id=1,
            sequence=0,
            content="",
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Empty passage content "
            "should be rejected."
        )

    print(
        "PASS: KnowledgeSource model works."
    )

    print(
        "PASS: KnowledgeDocument model works."
    )

    print(
        "PASS: KnowledgePassage model works."
    )

    print(
        "PASS: Knowledge model validation works."
    )

    print(
        "PASS: R2.4A Knowledge models complete."
    )


if __name__ == "__main__":
    main()