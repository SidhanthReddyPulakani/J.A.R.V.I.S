"""
P8 — Contract tests for CapabilityRequest and the unified Agent
dispatch entry point.

These tests lock down what P8 is actually responsible for:

1. `CapabilityRequest.from_tool_call` normalizes a provider-agnostic
   `AgentToolCall` into one request shape, carrying invocation
   metadata (`invocation_id`, `step`) that `AgentToolCall` alone does
   not have anywhere else to live.
2. `agent._execute_capability_request` is the single call site the
   Agent Execution Loop uses regardless of whether an operation is
   handled by the Agent Memory Operation surface (P1) or an existing
   application tool (jarvis.core.tools) — both still route to
   separate internal registries, but through one entry point.
3. Whichever registry executes a request, the result comes back as
   the same `OperationResult` shape (same fields, same type) — P8
   does not introduce a second result type for capabilities.
4. The tool-message content shown to the model preserves the exact
   framing each registry already had (application-tool exceptions
   keep "Tool execution failed: ..."; everything else is shown
   unprefixed), now derived from one function instead of two
   independently-tracked strings.

Only the LLM boundary is stubbed in the end-to-end test. Everything
else runs against a real JarvisAgent and an isolated SQLite database,
matching the pattern used by the P6/P7 test files.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.core.agent_turn import AgentToolCall
from jarvis.core.capability_request import CapabilityRequest
from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationStatus,
)
from jarvis.storage.database import Database


# ==========================================================
# Pure CapabilityRequest tests — no Agent involved.
# ==========================================================


def test_from_tool_call_normalizes_fields() -> None:
    """
    from_tool_call carries the operation name, arguments, the
    provider-supplied tool_call id, and the reasoning-loop step into
    one normalized request.
    """

    call = AgentToolCall(
        id="call_1",
        name="open_url",
        arguments={"url": "https://example.com"},
    )

    request = CapabilityRequest.from_tool_call(
        call,
        step=3,
    )

    assert request.operation == "open_url"
    assert request.arguments == {
        "url": "https://example.com"
    }
    assert request.invocation_id == "call_1"
    assert request.step == 3


def test_from_tool_call_allows_missing_invocation_id() -> None:
    """
    Some providers may not supply a tool_call id. The request must
    still build cleanly with invocation_id=None rather than failing.
    """

    call = AgentToolCall(
        id=None,
        name="get_current_datetime",
        arguments={},
    )

    request = CapabilityRequest.from_tool_call(
        call,
        step=1,
    )

    assert request.invocation_id is None


def test_from_tool_call_copies_arguments_defensively() -> None:
    """
    Mutating the original AgentToolCall.arguments dict after the
    request is built must not retroactively change the request.
    """

    original_arguments = {"app": "notepad"}

    call = AgentToolCall(
        id=None,
        name="open_application",
        arguments=original_arguments,
    )

    request = CapabilityRequest.from_tool_call(
        call,
        step=1,
    )

    original_arguments["app"] = "mutated"

    assert request.arguments == {
        "app": "notepad"
    }


def test_to_dict_is_transport_safe() -> None:
    """
    to_dict() produces a plain, serializable dictionary containing
    exactly the request's fields.
    """

    request = CapabilityRequest(
        operation="memory_search",
        arguments={"query": "cursor"},
        invocation_id="abc",
        step=2,
    )

    assert request.to_dict() == {
        "operation": "memory_search",
        "arguments": {"query": "cursor"},
        "invocation_id": "abc",
        "step": 2,
    }


def test_capability_request_is_immutable() -> None:
    """
    CapabilityRequest is a frozen dataclass: once built, a request
    cannot be mutated out from under the loop that issued it.
    """

    request = CapabilityRequest(
        operation="open_url",
        arguments={},
    )

    with pytest.raises(
        dataclasses.FrozenInstanceError
    ):
        request.operation = "changed"  # type: ignore[misc]


# ==========================================================
# Agent-integration tests — real JarvisAgent, isolated DB.
# ==========================================================


def build_test_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    database_name: str,
) -> tuple[JarvisAgent, Database]:
    """Construct a real Agent against an isolated SQLite database."""

    test_database = Database(
        tmp_path / database_name
    )

    monkeypatch.setattr(
        agent_module,
        "database",
        test_database,
    )

    test_database.initialize()

    return JarvisAgent(), test_database


def test_execute_capability_request_routes_memory_operation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A request naming a memory operation is routed to
    _execute_memory_operation, not the application-tool registry.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_memory_route.db",
    )

    recorded_calls: list[tuple[str, dict]] = []

    def fake_memory_operation(
        *,
        name: str,
        args: dict,
    ) -> OperationResult:
        recorded_calls.append((name, args))
        return OperationResult.success_result(
            operation=name,
            data="ok",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    request = CapabilityRequest(
        operation="memory_search",
        arguments={"query": "cursor"},
        invocation_id="call_1",
        step=1,
    )

    result = agent._execute_capability_request(
        request
    )

    assert recorded_calls == [
        ("memory_search", {"query": "cursor"})
    ]
    assert result.status == OperationStatus.SUCCESS
    assert result.data == "ok"


def test_execute_capability_request_routes_application_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A request naming an application tool is routed to
    _execute_application_tool, not the memory-operation registry.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_tool_route.db",
    )

    monkeypatch.setitem(
        agent_module.AVAILABLE_TOOLS,
        "p8_echo_tool",
        lambda value: f"echo:{value}",
    )

    request = CapabilityRequest(
        operation="p8_echo_tool",
        arguments={"value": "hi"},
        invocation_id="call_2",
        step=1,
    )

    result = agent._execute_capability_request(
        request
    )

    assert result.status == OperationStatus.SUCCESS
    assert result.data == "echo:hi"


def test_unknown_operation_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    An operation name matching neither registry fails as NOT_FOUND
    rather than raising.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_unknown_operation.db",
    )

    request = CapabilityRequest(
        operation="totally_unknown_operation",
        arguments={},
    )

    result = agent._execute_capability_request(
        request
    )

    assert result.status == OperationStatus.FAILURE
    assert result.error_code == (
        OperationErrorCode.NOT_FOUND
    )
    assert result.error_message == (
        "Unknown tool: totally_unknown_operation"
    )


def test_operation_result_shape_is_identical_across_registries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Whichever registry actually executes a request, the caller gets
    back the same OperationResult type with the same field set —
    this is the "one true result shape" P8 is meant to guarantee.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_shape_parity.db",
    )

    monkeypatch.setitem(
        agent_module.AVAILABLE_TOOLS,
        "p8_ok_tool",
        lambda: "tool-data",
    )

    def fake_memory_operation(
        *,
        name: str,
        args: dict,
    ) -> OperationResult:
        return OperationResult.success_result(
            operation=name,
            data="memory-data",
        )

    agent._execute_memory_operation = (
        fake_memory_operation
    )

    tool_result = agent._execute_capability_request(
        CapabilityRequest(
            operation="p8_ok_tool",
            arguments={},
        )
    )

    memory_result = agent._execute_capability_request(
        CapabilityRequest(
            operation="memory_get",
            arguments={"id": 1},
        )
    )

    assert type(tool_result) is type(
        memory_result
    )
    assert set(tool_result.to_dict().keys()) == set(
        memory_result.to_dict().keys()
    )
    assert tool_result.data == "tool-data"
    assert memory_result.data == "memory-data"


# ==========================================================
# Tool-message content framing.
# ==========================================================


def test_tool_message_content_prefixes_application_tool_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    An application-tool failure is shown to the model with the
    "Tool execution failed: ..." framing it has always had, even
    though the underlying OperationResult.error_message carries no
    such prefix.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_tool_exception_framing.db",
    )

    request = CapabilityRequest(
        operation="p8_failing_tool",
        arguments={},
    )

    operation_result = (
        OperationResult.failure_result(
            operation="p8_failing_tool",
            error_code=(
                OperationErrorCode.SERVICE_ERROR
            ),
            error_message="boom",
        )
    )

    content = agent._build_tool_message_content(
        request,
        operation_result,
    )

    assert content == "Tool execution failed: boom"
    assert operation_result.error_message == "boom"


def test_tool_message_content_does_not_prefix_memory_operation_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A memory-operation failure is shown to the model as its own
    error message, unprefixed — matching the memory branch's
    existing behavior.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_memory_failure_framing.db",
    )

    request = CapabilityRequest(
        operation="memory_replace_core",
        arguments={},
    )

    operation_result = (
        OperationResult.failure_result(
            operation="memory_replace_core",
            error_code=(
                OperationErrorCode.VALIDATION_ERROR
            ),
            error_message=(
                "label must be a string"
            ),
        )
    )

    content = agent._build_tool_message_content(
        request,
        operation_result,
    )

    assert content == "label must be a string"


def test_tool_message_content_does_not_prefix_unknown_tool(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    An unknown-operation failure is shown unprefixed, matching the
    original AVAILABLE_TOOLS branch's behavior for a missing tool
    (as opposed to a tool that raised).
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_unknown_tool_framing.db",
    )

    request = CapabilityRequest(
        operation="totally_unknown_operation",
        arguments={},
    )

    result = agent._execute_capability_request(
        request
    )

    content = agent._build_tool_message_content(
        request,
        result,
    )

    assert content == result.error_message
    assert content == (
        "Unknown tool: totally_unknown_operation"
    )


# ==========================================================
# End-to-end: invocation metadata flows through a real run().
# ==========================================================


class SingleToolCallLLM:
    """Requests one application tool, then returns a final answer."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, *, messages: list, tools: list):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        if len(self.calls) == 1:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="p8_e2e_tool",
                                arguments={
                                    "value": "hi"
                                },
                            )
                        )
                    ],
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Done.",
                tool_calls=[],
            )
        )


def test_request_step_matches_trace_step_across_a_real_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    During a real two-step run(), the CapabilityRequest built for
    the first model turn's tool call carries step=1, matching the
    execution trace's own step numbering for that same turn.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p8_e2e_step_metadata.db",
    )

    monkeypatch.setitem(
        agent_module.AVAILABLE_TOOLS,
        "p8_e2e_tool",
        lambda value: f"echo:{value}",
    )

    agent.llm = SingleToolCallLLM()

    result = agent.run(
        "Run the p8 end-to-end tool."
    )

    assert result == "Done."
    assert len(agent.operation_results) == 1
    assert (
        agent.operation_results[0].data
        == "echo:hi"
    )

    trace = agent.last_execution_trace
    first_step = trace.steps[0]

    assert first_step.step == 1
    assert len(first_step.observations) == 1

    observation = first_step.observations[0]

    assert observation.operation == "p8_e2e_tool"
    assert observation.result.data == "echo:hi"