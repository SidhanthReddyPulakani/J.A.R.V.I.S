"""
P11 — Capability Registry.

Registration, lookup, and discovery for Capabilities (P9). This is
the only place that knows the full set of registered capabilities
and operations; the Controller (P12) queries it rather than holding
its own copy of that information.
"""

from __future__ import annotations

from jarvis.capabilities.contracts import (
    Capability,
    OperationDefinition,
)


class CapabilityRegistrationError(Exception):
    """
    Raised when a Capability or one of its operations cannot be
    registered — a duplicate capability name, a duplicate operation
    address, or an operation whose declared `capability_name` does
    not match the capability registering it.
    """


class CapabilityRegistry:
    """
    Holds every registered Capability and makes its operations
    discoverable by address.
    """

    def __init__(self) -> None:

        self._capabilities: dict[
            str, Capability
        ] = {}

        self._operations: dict[
            str, OperationDefinition
        ] = {}

    def register(
        self,
        capability: Capability,
    ) -> None:
        """
        Register a Capability and every operation it declares.

        Raises CapabilityRegistrationError if the capability's name
        is already registered, if any of its operations' addresses
        collide with an already-registered operation, or if an
        operation's declared `capability_name` does not match the
        capability being registered.
        """

        name = capability.metadata.name

        if name in self._capabilities:

            raise CapabilityRegistrationError(
                f"Capability '{name}' is already "
                f"registered."
            )

        definitions = capability.operations()

        for definition in definitions:

            if (
                definition.capability_name
                != name
            ):

                raise CapabilityRegistrationError(
                    f"Operation "
                    f"'{definition.operation_name}' "
                    f"declares capability_name "
                    f"'{definition.capability_name}', "
                    f"which does not match the "
                    f"registering capability '{name}'."
                )

            if definition.address in self._operations:

                raise CapabilityRegistrationError(
                    f"Operation address "
                    f"'{definition.address}' is "
                    f"already registered."
                )

        # --------------------------------------------------
        # Only commit once every operation has been validated,
        # so a bad capability never gets partially registered.
        # --------------------------------------------------

        self._capabilities[name] = capability

        for definition in definitions:

            self._operations[
                definition.address
            ] = definition

    def get_capability(
        self,
        name: str,
    ) -> Capability | None:
        """
        Return the registered Capability with this name, or None.
        """

        return self._capabilities.get(
            name
        )

    def resolve_operation(
        self,
        address: str,
    ) -> tuple[
        Capability,
        OperationDefinition,
    ] | None:
        """
        Look up the Capability and OperationDefinition that own a
        given "capability.operation" address, or None if it is not
        registered.

        This is the lookup the Controller (P12) uses to route a
        CapabilityRequest without ever parsing the address string
        itself.
        """

        definition = self._operations.get(
            address
        )

        if definition is None:
            return None

        capability = self._capabilities.get(
            definition.capability_name
        )

        if capability is None:
            # Should not happen if register() is the only way
            # operations enter the registry, but a missing
            # capability is treated as "not resolvable" rather
            # than raising, matching describe()/discover()'s
            # not-found-is-None convention.
            return None

        return capability, definition

    def discover(
        self,
    ) -> tuple[OperationDefinition, ...]:
        """
        Return every registered operation, across every registered
        capability.
        """

        return tuple(
            self._operations.values()
        )

    def describe(
        self,
        address: str,
    ) -> OperationDefinition | None:
        """
        Return the purpose/inputs/outputs/requirements for one
        operation address, or None if it is not registered.
        """

        return self._operations.get(
            address
        )


__all__ = [
    "CapabilityRegistry",
    "CapabilityRegistrationError",
]