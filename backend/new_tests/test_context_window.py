from jarvis.context.models import AgentContext
from jarvis.context.window import ContextWindowManager

from jarvis.context.window import (
    ContextPressure,
    ContextWindowManager,
)
from jarvis.core.config import settings

def make_context(*contents: str | None) -> AgentContext:
    """
    Build a minimal AgentContext for ContextWindowManager tests.
    """

    return AgentContext(
        messages=[
            {
                "role": "system",
                "content": contents[0] if contents else "",
            },
            *[
                {
                    "role": "user",
                    "content": content,
                }
                for content in contents[1:]
            ],
        ]
    )


# ============================================================
# TOKEN ESTIMATION
# ============================================================


def test_estimate_tokens_empty_text_returns_zero():
    manager = ContextWindowManager()

    assert manager.estimate_tokens("") == 0


def test_estimate_tokens_whitespace_returns_zero():
    manager = ContextWindowManager()

    assert manager.estimate_tokens("   \n\t   ") == 0


def test_estimate_tokens_uses_four_characters_per_token():
    manager = ContextWindowManager()

    text = "a" * 100

    assert manager.estimate_tokens(text) == 25


def test_estimate_tokens_short_non_empty_text_returns_at_least_one():
    manager = ContextWindowManager()

    assert manager.estimate_tokens("a") == 1
    assert manager.estimate_tokens("abc") == 1


def test_estimate_tokens_accepts_non_string_values():
    manager = ContextWindowManager()

    assert manager.estimate_tokens(1234) == 1


def test_estimate_context_tokens_sums_message_content():
    manager = ContextWindowManager()

    context = make_context(
        "a" * 100,
        "b" * 40,
        "c" * 20,
    )

    assert manager.estimate_context_tokens(context) == 40


def test_estimate_context_tokens_ignores_none_content():
    manager = ContextWindowManager()

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "a" * 20,
            },
            {
                "role": "user",
                "content": None,
            },
        ]
    )

    assert manager.estimate_context_tokens(context) == 5


def test_estimate_context_tokens_does_not_modify_context():
    manager = ContextWindowManager()

    context = make_context(
        "system message",
        "first message",
        "second message",
    )

    before = context.as_messages()

    manager.estimate_context_tokens(context)

    after = context.as_messages()

    assert after == before


# ============================================================
# EXISTING MESSAGE-COUNT WINDOW BEHAVIOR
# ============================================================


def test_prepare_without_message_limit_returns_context():
    manager = ContextWindowManager()

    context = make_context(
        "system",
        "message 1",
        "message 2",
    )

    result = manager.prepare(context)

    assert result.as_messages() == context.as_messages()


def test_prepare_under_message_limit_returns_context():
    manager = ContextWindowManager(max_messages=5)

    context = make_context(
        "system",
        "message 1",
        "message 2",
    )

    result = manager.prepare(context)

    assert result.as_messages() == context.as_messages()


def test_prepare_over_message_limit_keeps_system_and_newest_messages():
    manager = ContextWindowManager(max_messages=3)

    context = make_context(
        "system",
        "message 1",
        "message 2",
        "message 3",
        "message 4",
    )

    result = manager.prepare(context)

    assert result.as_messages() == [
        {
            "role": "system",
            "content": "system",
        },
        {
            "role": "user",
            "content": "message 3",
        },
        {
            "role": "user",
            "content": "message 4",
        },
    ]


def test_prepare_does_not_modify_original_context():
    manager = ContextWindowManager(max_messages=3)

    context = make_context(
        "system",
        "message 1",
        "message 2",
        "message 3",
    )

    before = context.as_messages()

    manager.prepare(context)

    after = context.as_messages()

    assert after == before

# ============================================================
# TOKEN BUDGET
# ============================================================


def test_default_context_budget_comes_from_settings():
    manager = ContextWindowManager()

    assert manager.get_budget() == settings.context_size


def test_custom_context_budget_is_used():
    manager = ContextWindowManager(
        context_budget=1000
    )

    assert manager.get_budget() == 1000


def test_pressure_threshold_defaults_to_seventy_percent():
    manager = ContextWindowManager(
        context_budget=1000
    )

    assert (
        manager.get_pressure_threshold_tokens()
        == 700
    )


def test_custom_pressure_threshold_is_used():
    manager = ContextWindowManager(
        context_budget=1000,
        pressure_threshold=0.80,
    )

    assert (
        manager.get_pressure_threshold_tokens()
        == 800
    )


def test_usage_ratio_reports_fraction_of_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 2000,
    )

    assert (
        manager.get_usage_ratio(context)
        == 0.5
    )


# ============================================================
# CONTEXT PRESSURE
# ============================================================


def test_context_below_seventy_percent_is_normal():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 2760,
    )

    assert (
        manager.get_pressure(context)
        == ContextPressure.NORMAL
    )


def test_context_at_seventy_percent_enters_pressure():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 2800,
    )

    assert (
        manager.get_pressure(context)
        == ContextPressure.PRESSURE
    )


def test_context_between_seventy_and_one_hundred_percent_is_pressure():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 3000,
    )

    assert (
        manager.get_pressure(context)
        == ContextPressure.PRESSURE
    )


def test_context_at_budget_is_over_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 4000,
    )

    assert (
        manager.get_pressure(context)
        == ContextPressure.OVER_BUDGET
    )


def test_context_above_budget_is_over_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 4800,
    )

    assert (
        manager.get_pressure(context)
        == ContextPressure.OVER_BUDGET
    )


def test_is_under_pressure_is_true_for_pressure_state():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 3000,
    )

    assert manager.is_under_pressure(context)


def test_is_under_pressure_is_true_for_over_budget_state():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 4000,
    )

    assert manager.is_under_pressure(context)


def test_is_under_pressure_is_false_for_normal_state():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 2000,
    )

    assert not manager.is_under_pressure(context)


def test_is_over_budget_is_false_for_pressure_state():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 3000,
    )

    assert not manager.is_over_budget(context)


def test_is_over_budget_is_true_at_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 4000,
    )

    assert manager.is_over_budget(context)


def test_is_over_budget_is_true_above_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 4800,
    )

    assert manager.is_over_budget(context)


# ============================================================
# INVALID BUDGET CONFIGURATION
# ============================================================


def test_zero_context_budget_is_rejected():
    try:
        ContextWindowManager(
            context_budget=0
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for zero context budget."
    )


def test_negative_context_budget_is_rejected():
    try:
        ContextWindowManager(
            context_budget=-1
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for negative context budget."
    )


def test_zero_pressure_threshold_is_rejected():
    try:
        ContextWindowManager(
            context_budget=1000,
            pressure_threshold=0,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for zero pressure threshold."
    )


def test_pressure_threshold_above_one_is_rejected():
    try:
        ContextWindowManager(
            context_budget=1000,
            pressure_threshold=1.1,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError for pressure threshold above 1."
    )

# ============================================================
# P5.3 — PRESSURE SIGNAL
# ============================================================


def test_pressure_context_gets_pressure_signal():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 3000,
    )

    prepared = manager.prepare(context)

    messages = prepared.as_messages()

    assert (
        messages[-1]["role"]
        == "system"
    )

    assert (
        "[CONTEXT PRESSURE]"
        in messages[-1]["content"]
    )


def test_normal_context_gets_no_pressure_signal():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = make_context(
        "a" * 2000,
    )

    prepared = manager.prepare(context)

    messages = prepared.as_messages()

    assert not any(
        "[CONTEXT PRESSURE]"
        in message.get("content", "")
        for message in messages
    )


# ============================================================
# P5.3 — TOKEN-AWARE EVICTION
# ============================================================


def test_over_budget_context_evicts_oldest_messages():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "OLD MESSAGE " * 200,
            },
            {
                "role": "assistant",
                "content": "MIDDLE MESSAGE " * 200,
            },
            {
                "role": "user",
                "content": "NEW MESSAGE",
            },
        ]
    )

    prepared = manager.prepare(context)

    messages = prepared.as_messages()

    contents = [
        message["content"]
        for message in messages
    ]

    assert "System" in contents

    assert (
        "NEW MESSAGE"
        in contents
    )

    assert not any(
        "OLD MESSAGE"
        in content
        for content in contents
    )

    assert any(
        "MIDDLE MESSAGE"
        in content
        for content in contents
    )


def test_over_budget_context_preserves_primary_system_message():
    manager = ContextWindowManager(
        context_budget=100
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "Primary system instruction.",
            },
            {
                "role": "user",
                "content": "Very large historical message "
                           * 100,
            },
        ]
    )

    prepared = manager.prepare(context)

    messages = prepared.as_messages()

    assert (
        messages[0]["role"]
        == "system"
    )

    assert (
        messages[0]["content"]
        == "Primary system instruction."
    )


def test_over_budget_context_gets_over_budget_signal():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "x" * 5000,
            },
        ]
    )

    prepared = manager.prepare(context)

    messages = prepared.as_messages()

    assert any(
        "[CONTEXT WINDOW]"
        in message.get("content", "")
        for message in messages
    )


def test_eviction_reduces_context_to_budget():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "old " * 1000,
            },
            {
                "role": "assistant",
                "content": "middle " * 1000,
            },
            {
                "role": "user",
                "content": "new " * 100,
            },
        ]
    )

    prepared = manager.prepare(context)

    assert (
        manager.estimate_context_tokens(
            prepared
        )
        <= manager.get_budget()
    )


def test_eviction_does_not_modify_original_context():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "old " * 1000,
            },
            {
                "role": "user",
                "content": "new",
            },
        ]
    )

    original_messages = (
        context.as_messages()
    )

    manager.prepare(context)

    assert (
        context.as_messages()
        == original_messages
    )


def test_newest_messages_are_preferred_during_eviction():
    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "OLD " * 1000,
            },
            {
                "role": "assistant",
                "content": "RECENT",
            },
        ]
    )

    prepared = manager.prepare(context)

    contents = [
        message["content"]
        for message in prepared.as_messages()
    ]

    assert "RECENT" in contents

    assert not any(
        "OLD"
        in content
        for content in contents
    )

    # ============================================================
# P5.4 — TOKEN-AWARE EVICTION
# ============================================================


def test_token_aware_eviction_does_not_use_message_count():
    """
    Prove that eviction is determined by token usage rather
    than by a fixed number of messages.

    A context containing only a few messages can still require
    eviction when those messages are large enough.
    """

    manager = ContextWindowManager(
        context_budget=1000
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "OLD " * 1200,
            },
            {
                "role": "user",
                "content": "NEW " * 100,
            },
        ]
    )

    prepared = manager.prepare(context)

    contents = [
        message["content"]
        for message in prepared.as_messages()
    ]

    assert "System" in contents

    assert any(
        "NEW "
        in content
        for content in contents
    )

    assert not any(
        "OLD "
        in content
        for content in contents
    )


def test_token_aware_eviction_keeps_small_recent_messages():
    """
    Prove that a large old message is evicted while a small
    recent message is retained.

    This is specifically a token-budget behavior, not a
    message-count behavior.
    """

    manager = ContextWindowManager(
        context_budget=100
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "LARGE OLD MESSAGE " * 100,
            },
            {
                "role": "user",
                "content": "Recent",
            },
        ]
    )

    prepared = manager.prepare(context)

    contents = [
        message["content"]
        for message in prepared.as_messages()
    ]

    assert "System" in contents
    assert "Recent" in contents

    assert not any(
        "LARGE OLD MESSAGE"
        in content
        for content in contents
    )


def test_token_aware_eviction_uses_oldest_first_order():
    """
    When multiple messages must be removed, eviction proceeds
    from oldest to newest.

    The newest message should survive whenever the budget
    permits it.
    """

    manager = ContextWindowManager(
        context_budget=500
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "FIRST OLD " * 300,
            },
            {
                "role": "assistant",
                "content": "SECOND OLD " * 300,
            },
            {
                "role": "user",
                "content": "LATEST",
            },
        ]
    )

    prepared = manager.prepare(context)

    contents = [
        message["content"]
        for message in prepared.as_messages()
    ]

    assert "System" in contents
    assert "LATEST" in contents

    assert not any(
        "FIRST OLD"
        in content
        for content in contents
    )

    assert not any(
        "SECOND OLD"
        in content
        for content in contents
    )


def test_token_aware_eviction_recalculates_after_each_eviction():
    """
    Prove that eviction continues until the remaining context
    fits the budget rather than removing a fixed number of
    messages.
    """

    manager = ContextWindowManager(
        context_budget=500
    )

    context = AgentContext(
        messages=[
            {
                "role": "system",
                "content": "System",
            },
            {
                "role": "user",
                "content": "OLD ONE " * 300,
            },
            {
                "role": "assistant",
                "content": "OLD TWO " * 300,
            },
            {
                "role": "user",
                "content": "RECENT " * 50,
            },
        ]
    )

    prepared = manager.prepare(context)

    assert (
        manager.estimate_context_tokens(
            prepared
        )
        <= manager.get_budget()
    )

    contents = [
        message["content"]
        for message in prepared.as_messages()
    ]

    assert "System" in contents

    assert any(
        "RECENT"
        in content
        for content in contents
    )