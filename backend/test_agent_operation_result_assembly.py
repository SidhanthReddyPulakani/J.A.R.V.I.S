"""
R2.10C.7

Agent-level verification of OperationResult -> Context
assembly.

Operation results are treated as ephemeral reasoning
information. They are not persisted by Context.
"""

from __future__ import annotations

from jarvis.context import (
    ContextCompiler,
    ContextWindowManager,
)
from jarvis.core.agent import JarvisAgent
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
)


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Be concise and conversational.
""".strip()


class FakeCoreMemory:
    def list_blocks(self):
        return []


class FakeRetrieval:
    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ):
        return []


class FakeDiary:
    def search(
        self,
        query: str,
        *,
        conversation_id=None,
        limit: int = 10,
    ):
        return []

    def recent(
        self,
        *,
        conversation_id=None,
        limit: int = 10,
    ):
        return []


def build_agent() -> JarvisAgent:
    """
    Build only the Agent components required for
    _build_context().
    """

    agent = object.__new__(JarvisAgent)

    agent.state = type(
        "TestState",
        (),
        {
            "agent_id": "operation-result-test",
            "conversation_id": 42,
            "current_task": "Testing operation results",
            "current_goal": (
                "Verify OperationResult reaches Context."
            ),
            "mode": "testing",
            "active_project": "Jarvis",
            "active_operation": None,
            "operation_status": "idle",
        },
    )()

    agent.messages = []

    agent.core_memory = FakeCoreMemory()
    agent.retrieval = FakeRetrieval()
    agent.diary = FakeDiary()

    agent.operation_results = []

    agent.context_compiler = ContextCompiler(
        system_prompt=SYSTEM_PROMPT
    )

    agent.context_window = ContextWindowManager()

    return agent


def test_success_operation_result_reaches_context() -> None:
    agent = build_agent()

    result = OperationResult.success_result(
        "memory_create",
        data={
            "memory_id": 501,
        },
    )

    context = agent._build_context(
        user_input="What just happened?",
        operation_results=[result],
    )

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    assert (
        "OPERATION RESULTS"
        in system_content
    )

    assert (
        "memory_create"
        in system_content
    )

    assert (
        "success"
        in system_content
    )

    assert (
        "memory_id"
        in system_content
    )

    assert (
        "501"
        in system_content
    )


def test_failure_operation_result_reaches_context() -> None:
    agent = build_agent()

    result = OperationResult.failure_result(
        "memory_read",
        OperationErrorCode.NOT_FOUND,
        "Memory was not found.",
    )

    context = agent._build_context(
        user_input="What happened?",
        operation_results=[result],
    )

    messages = context.as_messages()

    assert messages

    system_content = messages[0]["content"]

    assert (
        "OPERATION RESULTS"
        in system_content
    )

    assert (
        "memory_read"
        in system_content
    )

    assert (
        "failure"
        in system_content
    )

    assert (
        "not_found"
        in system_content
    )

    assert (
        "Memory was not found."
        in system_content
    )


def test_agent_operation_results_are_used_by_default() -> None:
    agent = build_agent()

    result = OperationResult.success_result(
        "knowledge_search",
        data=[
            {
                "id": 202,
                "title": "Jarvis Architecture",
            }
        ],
    )

    agent.operation_results = [result]

    context = agent._build_context(
        user_input="Show me the result."
    )

    system_content = (
        context.as_messages()[0]["content"]
    )

    assert (
        "knowledge_search"
        in system_content
    )

    assert (
        "Jarvis Architecture"
        in system_content
    )


def test_explicit_operation_results_override_agent_results() -> None:
    agent = build_agent()

    stored_result = OperationResult.success_result(
        "old_operation",
        data={
            "value": "old",
        },
    )

    explicit_result = OperationResult.success_result(
        "new_operation",
        data={
            "value": "new",
        },
    )

    agent.operation_results = [
        stored_result
    ]

    context = agent._build_context(
        user_input="Use the new result.",
        operation_results=[
            explicit_result
        ],
    )

    system_content = (
        context.as_messages()[0]["content"]
    )

    assert (
        "new_operation"
        in system_content
    )

    assert (
        "old_operation"
        not in system_content
    )


def test_operation_results_are_not_persisted_by_context() -> None:
    agent = build_agent()

    result = OperationResult.success_result(
        "temporary_operation",
        data={
            "value": "temporary",
        },
    )

    first = agent._build_context(
        user_input="Use this result.",
        operation_results=[result],
    )

    first_content = (
        first.as_messages()[0]["content"]
    )

    assert (
        "temporary_operation"
        in first_content
    )

    second = agent._build_context(
        user_input="Fresh context."
    )

    second_content = (
        second.as_messages()[0]["content"]
    )

    assert (
        "temporary_operation"
        not in second_content
    )


def test_operation_result_context_is_deterministic() -> None:
    agent = build_agent()

    result = OperationResult.success_result(
        "memory_create",
        data={
            "memory_id": 501,
        },
    )

    first = agent._build_context(
        user_input="What happened?",
        operation_results=[result],
    )

    second = agent._build_context(
        user_input="What happened?",
        operation_results=[result],
    )

    assert (
        first.as_messages()
        == second.as_messages()
    )


def main() -> None:
    test_success_operation_result_reaches_context()
    test_failure_operation_result_reaches_context()
    test_agent_operation_results_are_used_by_default()
    test_explicit_operation_results_override_agent_results()
    test_operation_results_are_not_persisted_by_context()
    test_operation_result_context_is_deterministic()

    print(
        "PASS: successful OperationResult -> Context."
    )

    print(
        "PASS: failed OperationResult -> Context."
    )

    print(
        "PASS: Agent operation-result assembly works."
    )

    print(
        "PASS: Explicit operation results override stored results."
    )

    print(
        "PASS: Operation results remain ephemeral."
    )

    print(
        "PASS: Operation-result Context assembly is deterministic."
    )


if __name__ == "__main__":
    main()