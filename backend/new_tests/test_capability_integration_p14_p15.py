"""
P14/P15 — the Capability Controller is permanently wired into the
live Agent, and adding a new Capability never requires touching
`jarvis/core/agent.py` again.

P14 retires the legacy AVAILABLE_TOOLS entry for Apps now that
`apps.*` runs through the real Controller (P13). P15 wires the
Agent Execution Loop (P7) to that Controller for real, replacing the
placeholder routing P8 introduced.

The property this file exists to prove is the one actually asked
for: "connect a capability to the Controller and forget about it."
Concretely:

    1. Every registered Capability's operations are automatically
       advertised to the model (`_get_llm_tools()`), with no
       per-capability code in the Agent.
    2. Every registered Capability's operations are automatically
       routed through the Controller (`_execute_capability_request`),
       with no per-capability code in the Agent.
    3. A brand-new Capability, invented only inside this test file
       and never mentioned anywhere in `jarvis/core/agent.py`,
       becomes fully callable through a real `agent.run()` the
       moment it is registered — proving (1) and (2) are not just
       true for Apps specifically.

Only the LLM boundary and, where relevant, the OS-level parts of the
Apps subsystem are stubbed. Everything else — persistence, the
reasoning loop, the real Registry/Controller — is real.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import jarvis.core.agent as agent_module
from jarvis.core.agent import JarvisAgent
from jarvis.core.capability_request import CapabilityRequest
from jarvis.core.tools import AVAILABLE_TOOLS
from jarvis.storage.database import Database

from jarvis.memory.operation_results import (
    OperationErrorCode,
    OperationResult,
    OperationState,
    OperationStatus,
)

from jarvis.capabilities.contracts import (
    Capability,
    CapabilityMetadata,
    OperationDefinition,
    OperationParameter,
    OperationSchema,
)
from jarvis.capabilities.registry import CapabilityRegistry
from jarvis.capabilities.controller import CapabilityController
from jarvis.capabilities.apps_capability import (
    ApplicationsCapability,
)
from jarvis.capabilities.bootstrap import build_default_registry
from jarvis.features.apps.manager import LaunchResult
from jarvis.features.apps.models import Application, ApplicationType
from jarvis.features.apps.resolver import ResolutionResult


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
# P14 — legacy AVAILABLE_TOOLS entry for Apps is gone.
# ======================================================================


def test_open_application_is_no_longer_a_legacy_tool() -> None:
    """
    apps.launch (P13) supersedes the old open_application entry.
    Only open_url and get_current_datetime remain legacy tools.
    """

    assert "open_application" not in AVAILABLE_TOOLS
    assert set(AVAILABLE_TOOLS.keys()) == {
        "open_url",
        "get_current_datetime",
    }


# ======================================================================
# P15 — a fresh JarvisAgent owns a real Registry/Controller built by
# build_default_registry(), with apps.* already registered.
# ======================================================================


def test_agent_constructs_a_real_capability_registry_and_controller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_construction.db",
    )

    assert isinstance(
        agent.capability_registry,
        CapabilityRegistry,
    )
    assert isinstance(
        agent.capability_controller,
        CapabilityController,
    )

    addresses = {
        definition.address
        for definition in agent.capability_registry.discover()
    }

    assert addresses == {
        "apps.find",
        "apps.resolve",
        "apps.launch",
    }


def test_get_llm_tools_advertises_registered_capability_operations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Every operation a registered Capability declares shows up in the
    model's tool list automatically, addressed as
    "capability.operation" — no code in agent.py names "apps"
    anywhere in this path.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_llm_tools.db",
    )

    tools = agent._get_llm_tools()

    function_names = {
        tool["function"]["name"]
        for tool in tools
        if isinstance(tool, dict)
        and tool.get("type") == "function"
    }

    assert {
        "apps.find",
        "apps.resolve",
        "apps.launch",
    }.issubset(function_names)


def test_execute_capability_request_routes_through_the_real_controller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A request addressed to a registered capability operation is
    routed through agent.capability_controller.execute(), not the
    legacy AVAILABLE_TOOLS fallback.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_routing.db",
    )

    installed = [
        Application(
            name="Notepad",
            target="notepad.exe",
            application_type=ApplicationType.EXECUTABLE,
        ),
    ]

    agent.capability_registry = CapabilityRegistry()
    agent.capability_registry.register(
        ApplicationsCapability(
            manager=FakeApplicationManager(installed)
        )
    )
    agent.capability_controller = CapabilityController(
        agent.capability_registry
    )

    request = CapabilityRequest(
        operation="apps.resolve",
        arguments={"query": "notepad"},
    )

    result = agent._execute_capability_request(request)

    assert result.status == OperationStatus.SUCCESS
    assert result.state == OperationState.SUCCESS
    assert result.data == "Notepad"


# ======================================================================
# Fakes for real end-to-end agent.run() tests against Apps, without
# touching real OS discovery/launch/verification.
# ======================================================================


class FakeApplicationManager:
    """
    A test double satisfying the same public surface as
    ApplicationManager, matching the one used by
    test_roadmap_p0_p13_verification.py's P13 tests.
    """

    def __init__(self, installed: list[Application]) -> None:
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
            if application.normalized_name == normalized
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
            if normalized in application.normalized_name
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

    def launch(self, query: str) -> LaunchResult:

        result = self.resolve_detailed(query)

        if result.application is None:

            if result.candidates:
                return LaunchResult(
                    success=False,
                    application=None,
                    message=(
                        f"I couldn't confidently identify '{query}'."
                    ),
                    error=result.reason,
                )

            return LaunchResult(
                success=False,
                application=None,
                message=f"Could not find application: {query}",
                error="application_not_found",
            )

        return LaunchResult(
            success=True,
            application=result.application,
            message=(
                f"{result.application.name} launched successfully."
            ),
        )


class SingleAppsToolCallLLM:
    """Requests one apps.* operation, then returns a final answer."""

    def __init__(self, operation: str, arguments: dict) -> None:
        self._operation = operation
        self._arguments = arguments
        self.calls: list[dict] = []

    def chat(self, *, messages: list, tools: list):

        self.calls.append(
            {"messages": messages, "tools": tools}
        )

        if len(self.calls) == 1:
            return SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=self._operation,
                                arguments=self._arguments,
                            )
                        )
                    ],
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="Handled.",
                tool_calls=[],
            )
        )


def _wire_fake_apps(
    agent: JarvisAgent,
    installed: list[Application],
) -> None:
    """Replace the agent's real Apps capability with a fake-backed one."""

    registry = CapabilityRegistry()
    registry.register(
        ApplicationsCapability(
            manager=FakeApplicationManager(installed)
        )
    )
    agent.capability_registry = registry
    agent.capability_controller = CapabilityController(registry)


def test_agent_run_launches_an_application_through_the_real_controller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    A real, full agent.run() call: the model requests "apps.launch",
    the Agent Execution Loop routes it through
    agent.capability_controller (not AVAILABLE_TOOLS), and the model
    sees the successful outcome as an unprefixed message.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_launch_success.db",
    )

    _wire_fake_apps(
        agent,
        [
            Application(
                name="Notepad",
                target="notepad.exe",
                application_type=ApplicationType.EXECUTABLE,
            )
        ],
    )

    llm = SingleAppsToolCallLLM(
        "apps.launch",
        {"query": "notepad"},
    )
    agent.llm = llm

    result = agent.run("Open Notepad.")

    assert result == "Handled."
    assert len(agent.operation_results) == 1

    operation_result = agent.operation_results[0]
    assert operation_result.status == OperationStatus.SUCCESS
    assert operation_result.state == OperationState.SUCCESS

    second_context = llm.calls[1]["messages"]
    tool_message = next(
        message
        for message in second_context
        if message.get("role") == "tool"
        and message.get("tool_name") == "apps.launch"
    )

    assert (
        tool_message["content"]
        == "Notepad launched successfully."
    )
    # Never dressed up as an exception.
    assert "Tool execution failed" not in tool_message["content"]


def test_agent_run_surfaces_requires_input_unprefixed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    An ambiguous apps.launch reaches the model as the Capability's
    own REQUIRES_INPUT message, never wrapped in the legacy
    "Tool execution failed: ..." framing.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_requires_input.db",
    )

    _wire_fake_apps(
        agent,
        [
            Application(
                name="Visual Studio Code",
                target="code.exe",
                application_type=ApplicationType.EXECUTABLE,
            ),
            Application(
                name="Visual Studio",
                target="devenv.exe",
                application_type=ApplicationType.EXECUTABLE,
            ),
        ],
    )

    llm = SingleAppsToolCallLLM(
        "apps.launch",
        {"query": "visual"},
    )
    agent.llm = llm

    result = agent.run("Open visual studio.")

    assert result == "Handled."

    operation_result = agent.operation_results[0]
    assert operation_result.status == OperationStatus.FAILURE
    assert operation_result.state == OperationState.REQUIRES_INPUT

    second_context = llm.calls[1]["messages"]
    tool_message = next(
        message
        for message in second_context
        if message.get("role") == "tool"
        and message.get("tool_name") == "apps.launch"
    )

    assert "Tool execution failed" not in tool_message["content"]
    assert "couldn't confidently identify" in tool_message["content"]


# ======================================================================
# The actual point of this file: a brand-new Capability, never
# mentioned in jarvis/core/agent.py, works through a real agent.run()
# purely by being registered.
# ======================================================================


class CoinFlipCapability(Capability):
    """
    A minimal Capability invented only in this test. Nothing in
    jarvis/core/agent.py, jarvis/capabilities/bootstrap.py, or any
    other production file has ever heard of "coinflip.flip" before
    this test registers it.
    """

    def __init__(self, forced_result: str) -> None:
        self._forced_result = forced_result

    @property
    def metadata(self) -> CapabilityMetadata:
        return CapabilityMetadata(
            name="coinflip",
            identity="test.coinflip_capability",
            version="0.0.1",
        )

    def operations(self) -> tuple[OperationDefinition, ...]:
        return (
            OperationDefinition(
                capability_name="coinflip",
                operation_name="flip",
                description="Flip a coin.",
                schema=OperationSchema(
                    inputs=(
                        OperationParameter(
                            name="call",
                            type="str",
                            required=True,
                            description=(
                                "'heads' or 'tails'."
                            ),
                        ),
                    ),
                    outputs="Whether the call was correct.",
                ),
            ),
        )

    def execute(
        self,
        operation_name: str,
        arguments: dict[str, Any],
    ) -> OperationResult:

        if operation_name != "flip":
            return OperationResult.failure_result(
                operation=f"coinflip.{operation_name}",
                error_code=OperationErrorCode.NOT_FOUND,
                error_message="Unknown coinflip operation.",
            )

        won = arguments["call"] == self._forced_result

        return OperationResult.from_state(
            operation="coinflip.flip",
            state=(
                OperationState.SUCCESS
                if won
                else OperationState.FAILED
            ),
            data={
                "result": self._forced_result,
                "won": won,
            },
            error_message=(
                None
                if won
                else f"Landed on {self._forced_result}."
            ),
        )


def test_a_brand_new_never_before_seen_capability_works_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    The property this whole file exists to prove: register a
    Capability the Agent has never seen, and a real agent.run() can
    call it, get routed through the real Controller, and see its
    OperationResult — with zero changes to jarvis/core/agent.py.
    """

    agent, _database = build_test_agent(
        monkeypatch,
        tmp_path,
        "jarvis_p15_brand_new_capability.db",
    )

    registry = CapabilityRegistry()
    registry.register(CoinFlipCapability(forced_result="heads"))
    agent.capability_registry = registry
    agent.capability_controller = CapabilityController(registry)

    # It shows up in the model's tool list automatically.
    tool_names = {
        tool["function"]["name"]
        for tool in agent._get_llm_tools()
        if isinstance(tool, dict)
        and tool.get("type") == "function"
    }
    assert "coinflip.flip" in tool_names

    llm = SingleAppsToolCallLLM(
        "coinflip.flip",
        {"call": "heads"},
    )
    agent.llm = llm

    result = agent.run("Flip a coin, I call heads.")

    assert result == "Handled."
    assert len(agent.operation_results) == 1

    operation_result = agent.operation_results[0]
    assert operation_result.status == OperationStatus.SUCCESS
    assert operation_result.state == OperationState.SUCCESS
    assert operation_result.data == {
        "result": "heads",
        "won": True,
    }


def test_build_default_registry_is_the_only_thing_that_would_need_to_change() -> None:
    """
    Documents the actual integration contract: build_default_registry
    is where a new built-in Capability gets added, and nothing about
    JarvisAgent's construction path depends on which capabilities it
    returns.
    """

    registry = build_default_registry()

    # Whatever it registers today, this call always succeeds without
    # any agent-specific wiring, and its result is a plain
    # CapabilityRegistry the Agent knows how to consume generically.
    assert isinstance(registry, CapabilityRegistry)
    assert len(registry.discover()) > 0