"""
P9 — Capability & Operation contracts.

This module defines the formal interfaces every future capability
implements. These are interfaces, not working code — P11 (Registry)
and P12 (Controller) build against them, and P13 (Apps) is the first
real implementation.

Nothing here executes an operation end-to-end. `Capability.execute`
is the seam a real capability fills in; the Controller (P12) is what
actually gets called by anything outside this package.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from jarvis.memory.operation_results import OperationResult


# --------------------------------------------------------
# Maps an OperationParameter's simple, human-readable type name to
# the JSON-schema type an LLM tool-calling API expects. Anything not
# in this table (including "any") falls back to "string" — safer
# for tool-calling models than omitting a type entirely, and cheap
# to extend as a real parameter type needs a more specific mapping.
# --------------------------------------------------------

_PARAMETER_TYPE_TO_JSON_SCHEMA: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


@dataclass(frozen=True)
class CapabilityMetadata:
    """
    Identity of one Capability.

    `name` is the short, stable namespace used in operation
    addressing (e.g. "apps" in "apps.launch"). It must be unique
    across every capability registered with the Capability Registry.

    `identity` is a fully-qualified, machine-stable identifier for
    the capability implementation itself (e.g.
    "jarvis.capabilities.apps"), distinct from `name` so the
    addressing namespace can stay short while the identity can
    change independently (e.g. if the implementation moves modules).

    `version` is a free-form version string the capability owns.
    Nothing in P9-P12 interprets it yet — real version-compatibility
    handling is explicitly deferred past P12 until a capability
    actually needs it.
    """

    name: str
    identity: str
    version: str


@dataclass(frozen=True)
class OperationParameter:
    """
    Describes one input parameter an operation accepts.

    `type` is a simple, human-readable type name ("str", "int",
    "bool", "float", "any") rather than a real type system. This is
    intentionally lightweight: P12's validation only checks
    presence of required parameters, not type conformance — add
    real type-checking when a capability actually needs it.
    """

    name: str
    type: str = "any"
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class OperationSchema:
    """
    Describes one operation's inputs, outputs, and requirements.

    `inputs` is the full set of parameters the operation accepts.

    `outputs` is a short, human-readable description of what a
    successful `OperationResult.data` contains — not a formal
    schema, since real capabilities don't exist yet to justify one.

    `requirements` is a list of free-form notes about preconditions
    the operation needs (e.g. "requires Windows", "requires the
    application to already be discovered"). These are descriptive
    only; P12 does not enforce them.
    """

    inputs: tuple[OperationParameter, ...] = ()
    outputs: str = ""
    requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationDefinition:
    """
    Describes one operation exposed by a Capability.

    An operation is addressed as "<capability_name>.<operation_name>"
    (e.g. "apps.launch") — the scheme settled on conceptually before
    P9 and now given a real, structured home. `address` derives this
    string from the two component parts rather than the reverse, so
    nothing has to parse a "." out of a raw string to find out which
    capability owns an operation.
    """

    capability_name: str
    operation_name: str
    description: str
    schema: OperationSchema = field(
        default_factory=OperationSchema
    )

    @property
    def address(self) -> str:
        """
        The full "capability.operation" address for this operation.
        """

        return (
            f"{self.capability_name}."
            f"{self.operation_name}"
        )


    def to_llm_tool_definition(self) -> dict[str, Any]:
        """
        Render this operation as an LLM-callable "function" tool
        definition — the same {"type": "function", ...} shape
        already used by the pre-existing memory-operation
        definitions (jarvis.memory.operation_definitions).

        This is the piece that makes "register once, forget about
        it" true end to end: once a Capability is registered
        (jarvis.capabilities.bootstrap), every operation it declares
        is automatically advertised to the model under its full
        "capability.operation" address, with no per-capability code
        anywhere in the Agent.
        """

        properties = {
            parameter.name: {
                "type": (
                    _PARAMETER_TYPE_TO_JSON_SCHEMA.get(
                        parameter.type,
                        "string",
                    )
                ),
                "description": (
                    parameter.description
                ),
            }
            for parameter in self.schema.inputs
        }

        required = [
            parameter.name
            for parameter in self.schema.inputs
            if parameter.required
        ]

        return {
            "type": "function",
            "function": {
                "name": self.address,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class Capability(ABC):
    """
    Interface every future capability implements.

    A Capability groups a set of related operations under one
    addressable namespace (`metadata.name`) and is the only thing
    the Capability Registry (P11) and Capability Controller (P12)
    know how to talk to.

    The one rule that matters most: a Capability must never call
    another Capability directly. If Capability A needs Capability
    B's operation, it must go `A -> Controller -> B`, the same as
    any other caller — never a direct import between capability
    packages. Nothing in this ABC can enforce that mechanically; it
    is a discipline every `execute()` implementation has to hold to.
    """

    @property
    @abstractmethod
    def metadata(self) -> CapabilityMetadata:
        """
        This capability's identity metadata.
        """

        raise NotImplementedError

    @abstractmethod
    def operations(self) -> tuple[OperationDefinition, ...]:
        """
        Every operation this capability exposes, for the Registry
        (P11) to make discoverable.
        """

        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        operation_name: str,
        arguments: dict[str, Any],
    ) -> OperationResult:
        """
        Execute one operation this capability owns and return its
        OperationResult.

        `operation_name` is the *local* operation name (e.g.
        "launch"), not the fully addressed "apps.launch" — splitting
        the address and routing to the right capability is the
        Controller's (P12) job, not this method's.
        """

        raise NotImplementedError


__all__ = [
    "CapabilityMetadata",
    "OperationParameter",
    "OperationSchema",
    "OperationDefinition",
    "Capability",
]