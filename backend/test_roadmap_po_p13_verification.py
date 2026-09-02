"""
Roadmap verification — P0 through P13.

This file is a single, cumulative checkpoint. It does not replace
the dedicated test files for each phase (test_agent_run_end_to_end,
test_agent_restart_reload, test_context_window, test_agent_failure_
injection, test_agent_reasoning_loop, test_agent_p7_integration,
test_capability_request_contract) — those remain the source of truth
for phase-specific behavior and should keep passing on their own.

What this file adds is proof that everything still cooperates as one
stack, end to end:

    P0-P6   the live Agent loop (memory, diary, operation results,
            context window, restart survival, failure injection)
            is exercised through one real two-turn conversation.
    P7      the bounded multi-step reasoning loop, execution trace,
            and context rebuild are exercised across 3+ steps in
            that same conversation.
    P8      CapabilityRequest is the shape every tool call is
            normalized into before execution, regardless of which
            registry executes it.
    P9      Capability / OperationDefinition / CapabilityMetadata
            are real, enforceable interfaces.
    P10     OperationResult carries the fuller OperationState
            vocabulary without breaking the original SUCCESS/
            FAILURE contract anything built before P10 depends on.
    P11     the Capability Registry can register, discover, and
            describe operations, and rejects malformed registration.
    P12     the Capability Controller is the single execute(request)
            gateway: unregistered operations, missing arguments, and
            raised exceptions are all normalized rather than
            escaping.
    P13     the Apps subsystem runs as a real Capability through
            that Controller, including the NOT_FOUND vs
            REQUIRES_INPUT distinction P10 exists to support.

Only the LLM boundary and, for P13, the OS-level parts of the Apps
subsystem (discovery/launch/verification) are stubbed. Everything
else — persistence, context assembly, memory formation, diary,
retrieval, the reasoning loop, and the new capabilities package —
is real.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.core.agent_turn import AgentToolCall
from jarvis.core.capability_request import CapabilityRequest
from jarvis.storage.database import Database

from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationState,
    OperationStatus,
    classify_operation_exception,
)

from jarvis.capabilities.contracts import (
    Capability,
    CapabilityMetadata,
    OperationDefinition,
    OperationParameter,
    OperationSchema,
)
from jarvis.capabilities.registry import (
    CapabilityRegistrationError,
    CapabilityRegistry,
)
from jarvis.capabilities.controller import (
    CapabilityController,
)
from jarvis.capabilities.apps_capability import (
    ApplicationsCapability,
)
from jarvis.features.apps.manager import LaunchResult
from jarvis.features.apps.models import (
    Application,
    ApplicationType,
)
from jarvis.features.apps.resolver import ResolutionResult


# ======================================================================
# Shared agent-construction helper (matches the pattern used by the
# P4/P6/P7/P8 test files).
# ======================================================================


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


# ======================================================================
# P0-P7 — one real, multi-step conversation exercising the live loop.
# ======================================================================


class ThreeStepLLM:
    """
    Deterministic LLM stub driving a 3-step reasoning loop:

        step 1: remembers a fact (memory_create)
        step 2: uses an application tool (open_url)
        step 3: returns a final answer with no further tool calls
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, *, messages: list, tools: list):

        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
            }
        )

        step = len(self.calls)

        if step == 1:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="memory_create",
                                arguments={
                                    "content": (
                                        "The user's main "
                                        "editor is Cursor."
                                    ),
                                    "subject": "editor",
                                },
                            )
                        )
                    ],
                )
            )

        if step == 2:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="open_url",
                                arguments={
                                    "url": (
                                        "https://example.com"
                                    )
                                },
                            )
                        )
                    ],
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Done across three steps.",
                tool_calls=[],
            )
        )


def test_p0_to_p7_multistep_conversation_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    One real run() exercising memory formation (P1), the context
    window (P5), the bounded multi-step reasoning loop and execution
    trace (P7), and the unified P8 capability-request dispatch,
    across a memory operation and an application tool in the same
    conversation turn.
    """

    agent, database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p0_p7_e2e.db",
    )

    llm = ThreeStepLLM()
    agent.llm = llm

    result = agent.run(
        "Remember my editor, then open example.com."
    )

    assert result == "Done across three steps."
    assert len(llm.calls) == 3

    # P1 — memory formation and the memory-operation surface both
    # produced real, persisted effects.
    assert len(agent.operation_results) == 2
    assert agent.operation_results[0].status == (
        OperationStatus.SUCCESS
    )
    assert agent.operation_results[1].status == (
        OperationStatus.SUCCESS
    )

    # P7 — three real model turns, three trace steps, correct
    # termination reason.
    trace = agent.last_execution_trace
    assert len(trace.steps) == 3
    assert trace.steps[0].step == 1
    assert trace.steps[1].step == 2
    assert trace.steps[2].step == 3
    assert (
        trace.termination_reason.value
        == "model_completed"
    )

    # P8 — both operations, despite coming from two different
    # internal registries, produced observations tagged with the
    # exact operation name the model requested.
    assert (
        trace.steps[0].observations[0].operation
        == "memory_create"
    )
    assert (
        trace.steps[1].observations[0].operation
        == "open_url"
    )

    # Diary (P1) recorded the completed turn.
    diary_rows = database.fetch_all(
        """
        SELECT COUNT(*) FROM diary_events
        WHERE conversation_id = ?
          AND event_type = 'conversation_turn'
        """,
        (agent.state.conversation_id,),
    )
    assert diary_rows[0][0] == 1


def test_p4_agent_survives_restart_with_state_intact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    P4 — a second JarvisAgent against the same database path reloads
    State/Core Memory/conversation history correctly.
    """

    database_path = (
        tmp_path / "jarvis_p4_restart.db"
    )

    test_database = Database(database_path)

    monkeypatch.setattr(
        agent_module,
        "database",
        test_database,
    )

    test_database.initialize()

    agent_one = JarvisAgent()

    class SimpleLLM:
        def chat(self, *, messages, tools):
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content="Acknowledged.",
                    tool_calls=[],
                )
            )

    agent_one.llm = SimpleLLM()
    agent_one.run("Hello, Jarvis.")

    conversation_id = (
        agent_one.state.conversation_id
    )

    del agent_one

    agent_two = JarvisAgent()

    assert (
        agent_two.state.conversation_id
        == conversation_id
    )


# ======================================================================
# P9 — Capability & Operation contracts are real, enforceable
# interfaces.
# ======================================================================


def test_capability_is_abstract_and_cannot_be_instantiated_directly() -> None:
    """
    Capability is an ABC: something must implement metadata,
    operations, and execute before it can be instantiated at all.
    """

    with pytest.raises(TypeError):
        Capability()  # type: ignore[abstract]


def test_incomplete_capability_subclass_cannot_be_instantiated() -> None:
    """
    A subclass that only implements part of the interface still
    cannot be instantiated — P9 is enforced at the interpreter level,
    not just by convention.
    """

    class IncompleteCapability(Capability):

        @property
        def metadata(self) -> CapabilityMetadata:
            return CapabilityMetadata(
                name="incomplete",
                identity="test.incomplete",
                version="0.0.1",
            )

        # operations() and execute() intentionally omitted.

    with pytest.raises(TypeError):
        IncompleteCapability()  # type: ignore[abstract]


def test_operation_definition_address_is_derived_not_parsed() -> None:
    """
    An operation's "capability.operation" address is built from its
    two structured fields rather than requiring any caller to
    construct or parse the string themselves.
    """

    definition = OperationDefinition(
        capability_name="apps",
        operation_name="launch",
        description="Launch an application.",
        schema=OperationSchema(
            inputs=(
                OperationParameter(
                    name="query",
                    type="str",
                ),
            )
        ),
    )

    assert definition.address == "apps.launch"


class MinimalEchoCapability(Capability):
    """
    A minimal, fully-conforming Capability used to test the Registry
    and Controller in isolation from the Apps subsystem.
    """

    def __init__(self) -> None:
        self.executed_with: list[
            tuple[str, dict]
        ] = []

    @property
    def metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            name="echo",
            identity="test.echo_capability",
            version="0.1.0",
        )

    def operations(
        self,
    ) -> tuple[OperationDefinition, ...]:
        return (
            OperationDefinition(
                capability_name="echo",
                operation_name="say",
                description="Echo a value back.",
                schema=OperationSchema(
                    inputs=(
                        OperationParameter(
                            name="value",
                            type="str",
                            required=True,
                        ),
                    ),
                    outputs="The same value.",
                ),
            ),
        )

    def execute(
        self,
        operation_name: str,
        arguments: dict[str, Any],
    ) -> OperationResult:

        self.executed_with.append(
            (operation_name, dict(arguments))
        )

        if operation_name != "say":
            return OperationResult.failure_result(
                operation=f"echo.{operation_name}",
                error_code=OperationErrorCode.NOT_FOUND,
                error_message="Unknown echo operation.",
            )

        if arguments.get("value") == "__raise__":
            raise RuntimeError(
                "Injected echo capability failure"
            )

        return OperationResult.success_result(
            operation="echo.say",
            data=arguments["value"],
        )


class MismatchedCapabilityNameCapability(Capability):
    """A malformed capability whose operation lies about its owner."""

    @property
    def metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            name="mismatched",
            identity="test.mismatched",
            version="0.0.1",
        )

    def operations(
        self,
    ) -> tuple[OperationDefinition, ...]:
        return (
            OperationDefinition(
                capability_name="not_mismatched",
                operation_name="broken",
                description="Deliberately wrong.",
            ),
        )

    def execute(
        self,
        operation_name: str,
        arguments: dict[str, Any],
    ) -> OperationResult:
        raise AssertionError(
            "should never be called"
        )


# ======================================================================
# P10 — OperationResult / OperationState.
# ======================================================================


def test_legacy_success_and_failure_results_are_unaffected() -> None:
    """
    The original P1 constructors still build results with state=None
    and unchanged status/error_code behavior — P10 is additive.
    """

    success = OperationResult.success_result(
        operation="memory_get",
        data="hello",
    )

    assert success.status == OperationStatus.SUCCESS
    assert success.success is True
    assert success.state is None
    assert success.is_terminal is True

    failure = OperationResult.failure_result(
        operation="memory_get",
        error_code=OperationErrorCode.NOT_FOUND,
        error_message="not found",
    )

    assert failure.status == OperationStatus.FAILURE
    assert failure.failed is True
    assert failure.state is None
    assert failure.is_terminal is True


def test_from_state_success_maps_to_success_status() -> None:

    result = OperationResult.from_state(
        operation="apps.launch",
        state=OperationState.SUCCESS,
        data="launched",
    )

    assert result.status == OperationStatus.SUCCESS
    assert result.state == OperationState.SUCCESS
    assert result.is_terminal is True


@pytest.mark.parametrize(
    "state",
    [
        OperationState.FAILED,
        OperationState.PARTIAL,
        OperationState.BLOCKED,
        OperationState.INVALID,
        OperationState.NOT_FOUND,
        OperationState.REQUIRES_INPUT,
        OperationState.IN_PROGRESS,
        OperationState.CANCELLED,
    ],
)
def test_from_state_non_success_states_map_to_failure_status(
    state: OperationState,
) -> None:
    """
    Every state other than SUCCESS maps to the coarse FAILURE
    status, and produces some error_code, so a legacy consumer that
    only understands OperationStatus/error_code still gets something
    usable.
    """

    result = OperationResult.from_state(
        operation="test.op",
        state=state,
        error_message="something happened",
    )

    assert result.status == OperationStatus.FAILURE
    assert result.state == state
    assert result.error_code is not None


def test_requires_input_and_not_found_are_both_failures_but_distinguishable() -> None:
    """
    The exact principle P10 exists for: two different outcomes that
    both read as a coarse FAILURE but mean different things to an
    Agent deciding what to do next.
    """

    not_found = OperationResult.from_state(
        operation="apps.launch",
        state=OperationState.NOT_FOUND,
        error_message="Could not find VS Code",
    )

    requires_input = OperationResult.from_state(
        operation="apps.launch",
        state=OperationState.REQUIRES_INPUT,
        data={"candidates": ["A", "B", "C"]},
        error_message="Found 3 matching applications.",
    )

    assert not_found.status == OperationStatus.FAILURE
    assert requires_input.status == OperationStatus.FAILURE
    assert not_found.state != requires_input.state
    assert not_found.state == OperationState.NOT_FOUND
    assert (
        requires_input.state
        == OperationState.REQUIRES_INPUT
    )


def test_non_terminal_states_are_not_terminal() -> None:

    for state in (
        OperationState.BLOCKED,
        OperationState.REQUIRES_INPUT,
        OperationState.IN_PROGRESS,
    ):
        result = OperationResult.from_state(
            operation="test.op",
            state=state,
        )
        assert result.is_terminal is False


def test_cancelled_result_is_terminal_and_carries_cancelled_state() -> None:

    result = OperationResult.cancelled_result(
        operation="apps.launch",
        message="User cancelled the launch.",
    )

    assert result.state == OperationState.CANCELLED
    assert result.is_terminal is True
    assert result.status == OperationStatus.FAILURE
    assert (
        result.error_message
        == "User cancelled the launch."
    )


def test_to_dict_includes_state_field() -> None:

    result = OperationResult.from_state(
        operation="apps.resolve",
        state=OperationState.REQUIRES_INPUT,
        error_message="ambiguous",
    )

    as_dict = result.to_dict()

    assert as_dict["state"] == "requires_input"
    assert as_dict["status"] == "failure"


# ======================================================================
# P11 — Capability Registry.
# ======================================================================


def test_registry_register_and_discover() -> None:

    registry = CapabilityRegistry()
    capability = MinimalEchoCapability()

    registry.register(capability)

    discovered = registry.discover()

    assert len(discovered) == 1
    assert discovered[0].address == "echo.say"


def test_registry_describe_returns_operation_definition() -> None:

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())

    definition = registry.describe("echo.say")

    assert definition is not None
    assert definition.description == (
        "Echo a value back."
    )
    assert definition.schema.inputs[0].name == "value"


def test_registry_describe_unknown_operation_returns_none() -> None:

    registry = CapabilityRegistry()

    assert registry.describe("nothing.here") is None


def test_registry_resolve_operation_returns_capability_and_definition() -> None:

    registry = CapabilityRegistry()
    capability = MinimalEchoCapability()
    registry.register(capability)

    resolved = registry.resolve_operation(
        "echo.say"
    )

    assert resolved is not None

    resolved_capability, definition = resolved

    assert resolved_capability is capability
    assert definition.operation_name == "say"


def test_registry_rejects_duplicate_capability_name() -> None:

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())

    with pytest.raises(
        CapabilityRegistrationError
    ):
        registry.register(MinimalEchoCapability())


def test_registry_rejects_mismatched_capability_name() -> None:

    registry = CapabilityRegistry()

    with pytest.raises(
        CapabilityRegistrationError
    ):
        registry.register(
            MismatchedCapabilityNameCapability()
        )


def test_registry_rejects_duplicate_operation_address_across_capabilities() -> None:

    class OtherEchoCapability(Capability):

        @property
        def metadata(self) -> CapabilityMetadata:
            return CapabilityMetadata(
                name="echo",
                identity="test.other_echo",
                version="0.0.1",
            )

        def operations(
            self,
        ) -> tuple[OperationDefinition, ...]:
            return (
                OperationDefinition(
                    capability_name="echo",
                    operation_name="say",
                    description="Also echo.",
                ),
            )

        def execute(
            self,
            operation_name: str,
            arguments: dict,
        ) -> OperationResult:
            raise AssertionError(
                "should never be called"
            )

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())

    # Same capability name "echo" already registered -> this must
    # fail on the duplicate-capability-name check before it would
    # even reach the duplicate-address check.
    with pytest.raises(
        CapabilityRegistrationError
    ):
        registry.register(OtherEchoCapability())


# ======================================================================
# P12 — Capability Controller.
# ======================================================================


def test_controller_has_no_separate_result_method() -> None:
    """
    Locks in the explicit design decision: execute() returns the
    result directly, there is no second result()/poll() call.
    """

    assert not hasattr(
        CapabilityController, "result"
    )


def test_controller_execute_success_passthrough() -> None:

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())
    controller = CapabilityController(registry)

    result = controller.execute(
        CapabilityRequest(
            operation="echo.say",
            arguments={"value": "hi"},
        )
    )

    assert result.status == OperationStatus.SUCCESS
    assert result.data == "hi"


def test_controller_execute_unregistered_operation_is_not_found() -> None:

    registry = CapabilityRegistry()
    controller = CapabilityController(registry)

    result = controller.execute(
        CapabilityRequest(
            operation="nothing.here",
            arguments={},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.error_code == (
        OperationErrorCode.NOT_FOUND
    )


def test_controller_execute_missing_required_argument_is_validation_error() -> None:

    registry = CapabilityRegistry()
    capability = MinimalEchoCapability()
    registry.register(capability)
    controller = CapabilityController(registry)

    result = controller.execute(
        CapabilityRequest(
            operation="echo.say",
            arguments={},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.error_code == (
        OperationErrorCode.VALIDATION_ERROR
    )
    assert "value" in (result.error_message or "")

    # Validation failing before dispatch means the capability's
    # execute() was never even called.
    assert capability.executed_with == []


def test_controller_execute_normalizes_raised_exception() -> None:

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())
    controller = CapabilityController(registry)

    result = controller.execute(
        CapabilityRequest(
            operation="echo.say",
            arguments={"value": "__raise__"},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.error_code == (
        classify_operation_exception(
            RuntimeError("x")
        )
    )
    assert (
        "Injected echo capability failure"
        in (result.error_message or "")
    )


def test_controller_accepts_a_request_built_from_an_agent_tool_call() -> None:
    """
    The P8 CapabilityRequest and the P12 Controller are the same
    contract on both ends: a request built from a real AgentToolCall
    (the shape the Agent Execution Loop produces) executes cleanly
    through the Controller.
    """

    registry = CapabilityRegistry()
    registry.register(MinimalEchoCapability())
    controller = CapabilityController(registry)

    call = AgentToolCall(
        id="call_1",
        name="echo.say",
        arguments={"value": "from the agent loop"},
    )

    request = CapabilityRequest.from_tool_call(
        call,
        step=1,
    )

    result = controller.execute(request)

    assert result.status == OperationStatus.SUCCESS
    assert result.data == "from the agent loop"


# ======================================================================
# P13 — Apps Capability, wired through the real Controller/Registry.
# ======================================================================


class FakeApplicationManager:
    """
    A test double satisfying the same public surface as
    ApplicationManager, without touching real OS discovery,
    launching, or process verification.
    """

    def __init__(
        self,
        installed: list[Application],
    ) -> None:
        self._installed = installed

    def applications(self) -> list[Application]:
        return list(self._installed)

    def resolve_detailed(
        self,
        query: str,
        refresh_on_miss: bool = True,
    ) -> ResolutionResult:

        normalized = query.strip().lower()

        exact = [
            application
            for application in self._installed
            if application.normalized_name
            == normalized
        ]

        if len(exact) == 1:
            return ResolutionResult(
                query=query,
                application=exact[0],
                candidates=exact,
                confidence=1.0,
                reason="exact_match",
            )

        partial = [
            application
            for application in self._installed
            if normalized
            in application.normalized_name
        ]

        if len(partial) == 1:
            return ResolutionResult(
                query=query,
                application=partial[0],
                candidates=partial,
                confidence=0.8,
                reason="scored_match",
            )

        if len(partial) > 1:
            return ResolutionResult(
                query=query,
                application=None,
                candidates=partial,
                confidence=0.5,
                reason="ambiguous_match",
            )

        return ResolutionResult(
            query=query,
            application=None,
            candidates=[],
            confidence=0.0,
            reason="no_match",
        )

    def launch(
        self,
        query: str,
    ) -> LaunchResult:

        result = self.resolve_detailed(query)

        if result.application is None:

            if result.candidates:
                return LaunchResult(
                    success=False,
                    application=None,
                    message=(
                        "I couldn't confidently identify "
                        f"'{query}'."
                    ),
                    error=result.reason,
                )

            return LaunchResult(
                success=False,
                application=None,
                message=(
                    "Could not find application: "
                    f"{query}"
                ),
                error="application_not_found",
            )

        return LaunchResult(
            success=True,
            application=result.application,
            message=(
                f"{result.application.name} "
                "launched successfully."
            ),
        )


@pytest.fixture
def apps_fixture() -> tuple[
    FakeApplicationManager,
    ApplicationsCapability,
    CapabilityRegistry,
    CapabilityController,
]:

    installed = [
        Application(
            name="Visual Studio Code",
            target="code.exe",
            application_type=(
                ApplicationType.EXECUTABLE
            ),
        ),
        Application(
            name="Visual Studio",
            target="devenv.exe",
            application_type=(
                ApplicationType.EXECUTABLE
            ),
        ),
        Application(
            name="Notepad",
            target="notepad.exe",
            application_type=(
                ApplicationType.EXECUTABLE
            ),
        ),
    ]

    manager = FakeApplicationManager(installed)
    capability = ApplicationsCapability(
        manager=manager
    )

    registry = CapabilityRegistry()
    registry.register(capability)

    controller = CapabilityController(registry)

    return (
        manager,
        capability,
        registry,
        controller,
    )


def test_apps_capability_registers_find_resolve_launch(
    apps_fixture,
) -> None:

    _manager, _capability, registry, _controller = (
        apps_fixture
    )

    addresses = {
        definition.address
        for definition in registry.discover()
    }

    assert addresses == {
        "apps.find",
        "apps.resolve",
        "apps.launch",
    }


def test_apps_find_returns_matching_names(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.find",
            arguments={"query": "visual"},
        )
    )

    assert result.status == OperationStatus.SUCCESS
    assert set(result.data) == {
        "Visual Studio Code",
        "Visual Studio",
    }


def test_apps_resolve_exact_match_succeeds(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.resolve",
            arguments={
                "query": "Visual Studio Code"
            },
        )
    )

    assert result.status == OperationStatus.SUCCESS
    assert result.state == OperationState.SUCCESS
    assert result.data == "Visual Studio Code"


def test_apps_resolve_ambiguous_returns_requires_input(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.resolve",
            arguments={"query": "visual"},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert (
        result.state
        == OperationState.REQUIRES_INPUT
    )
    assert set(
        result.data["candidates"]
    ) == {
        "Visual Studio Code",
        "Visual Studio",
    }


def test_apps_resolve_no_match_returns_not_found(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.resolve",
            arguments={"query": "photoshop"},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.state == OperationState.NOT_FOUND


def test_apps_launch_success(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.launch",
            arguments={"query": "notepad"},
        )
    )

    assert result.status == OperationStatus.SUCCESS
    assert result.state == OperationState.SUCCESS
    assert "Notepad" in result.data


def test_apps_launch_not_found(
    apps_fixture,
) -> None:

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.launch",
            arguments={"query": "photoshop"},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.state == OperationState.NOT_FOUND


def test_apps_launch_ambiguous_returns_requires_input_not_failed(
    apps_fixture,
) -> None:
    """
    The exact scenario P10's own principle names: launching an
    ambiguous query must be distinguishable from a hard failure so
    the Agent can ask the user to choose, rather than giving up.
    """

    _manager, _capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.launch",
            arguments={"query": "visual"},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert (
        result.state
        == OperationState.REQUIRES_INPUT
    )
    assert result.state != OperationState.NOT_FOUND


def test_apps_launch_missing_query_is_validated_before_execution(
    apps_fixture,
) -> None:

    _manager, capability, _registry, controller = (
        apps_fixture
    )

    result = controller.execute(
        CapabilityRequest(
            operation="apps.launch",
            arguments={},
        )
    )

    assert result.status == OperationStatus.FAILURE
    assert result.error_code == (
        OperationErrorCode.VALIDATION_ERROR
    )


# ======================================================================
# Phase-boundary guard: this used to assert P15 had *not* started
# (P13 complete, Controller not yet wired into the live Agent loop).
# P15 has since happened on purpose — see
# test_capability_integration_p14_p15.py for what that integration
# actually provides. The guard below now locks in the new contract
# instead of the old one, so a future *regression* (the wiring
# silently disappearing) is caught the same way the original absence
# was.
# ======================================================================


def test_agent_module_now_integrates_the_capability_controller() -> None:
    """
    P15 is complete: `jarvis.core.agent` wires the reasoning loop to
    the Capability Registry/Controller built by
    `jarvis.capabilities.bootstrap.build_default_registry`.

    This test supersedes the earlier boundary guard of the same
    name's opposite assertion — that guard's job was to catch this
    integration happening silently, before it was deliberately
    started. Now that P15 has happened on purpose, this test locks
    in the new contract instead of the old one. See
    `test_capability_integration_p14_p15.py` for the behavior this
    integration actually provides.
    """

    with open(
        agent_module.__file__,
        "r",
        encoding="utf-8",
    ) as handle:
        source = handle.read()

    assert (
        "jarvis.capabilities" in source
    ), (
        "agent.py no longer references "
        "jarvis.capabilities -- if P15 has been reverted, "
        "update this test (and the roadmap) rather than "
        "deleting it."
    )