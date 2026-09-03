from jarvis.context.window import (
    ContextWindowManager,
)
from jarvis.retrieval.models import (
    RetrievalResult,
)


def make_result(
    identifier: int,
    content: str,
    score: float,
) -> RetrievalResult:
    return RetrievalResult(
        source="recall",
        identifier=identifier,
        content=content,
        score=score,
    )


def test_retrieval_results_under_budget_are_preserved():
    manager = ContextWindowManager()

    results = [
        make_result(
            1,
            "Short relevant memory.",
            0.95,
        ),
        make_result(
            2,
            "Another short relevant memory.",
            0.85,
        ),
    ]

    selected = manager.fit_retrieval_budget(
        results,
        retrieval_budget=1000,
    )

    assert selected == results


def test_retrieval_budget_excludes_results_that_do_not_fit():
    manager = ContextWindowManager()

    results = [
        make_result(
            1,
            "A" * 800,
            0.95,
        ),
        make_result(
            2,
            "B" * 800,
            0.90,
        ),
        make_result(
            3,
            "C" * 800,
            0.85,
        ),
    ]

    selected = manager.fit_retrieval_budget(
        results,
        retrieval_budget=220,
    )

    assert len(selected) == 1
    assert selected[0].identifier == 1

def test_retrieval_budget_preserves_complete_results():
    manager = ContextWindowManager()

    results = [
        make_result(
            1,
            "Important complete memory.",
            0.95,
        ),
        make_result(
            2,
            "Another complete memory.",
            0.90,
        ),
    ]

    selected = manager.fit_retrieval_budget(
        results,
        retrieval_budget=20,
    )

    for result in selected:
        assert result.content in (
            "Important complete memory.",
            "Another complete memory.",
        )


def test_retrieval_budget_does_not_modify_original_results():
    manager = ContextWindowManager()

    results = [
        make_result(
            1,
            "Memory one.",
            0.95,
        ),
        make_result(
            2,
            "Memory two.",
            0.90,
        ),
    ]

    original = list(results)

    manager.fit_retrieval_budget(
        results,
        retrieval_budget=20,
    )

    assert results == original


def test_retrieval_budget_keeps_smaller_later_result_when_large_result_does_not_fit():
    manager = ContextWindowManager()

    results = [
        make_result(
            1,
            "A" * 500,
            0.99,
        ),
        make_result(
            2,
            "Small useful result.",
            0.80,
        ),
    ]

    selected = manager.fit_retrieval_budget(
        results,
        retrieval_budget=100,
    )

    assert all(
        result.identifier != 1
        for result in selected
    )

    assert any(
        result.identifier == 2
        for result in selected
    )


def test_retrieval_budget_rejects_zero_budget():
    manager = ContextWindowManager()

    try:
        manager.fit_retrieval_budget(
            [],
            retrieval_budget=0,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for zero retrieval budget."
    )


def test_retrieval_budget_rejects_negative_budget():
    manager = ContextWindowManager()

    try:
        manager.fit_retrieval_budget(
            [],
            retrieval_budget=-1,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for negative retrieval budget."
    )