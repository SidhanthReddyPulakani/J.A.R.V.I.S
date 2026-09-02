"""
Central registration point for every built-in Capability.

This is the ONE place that changes when a new Capability is added
to Jarvis. Nothing in `JarvisAgent`, the Capability Controller, or
the Capability Registry needs to change — register the Capability
here and it is immediately:

    - discoverable (CapabilityRegistry.discover() / .describe()),
    - callable by the model (JarvisAgent._get_llm_tools() advertises
      every registered operation automatically), and
    - routed correctly at execution time
      (JarvisAgent._execute_capability_request() checks the registry
      before falling back to the legacy tool path).

To add a new Capability:

    1. Implement it against the `Capability` interface
       (jarvis.capabilities.contracts).
    2. Instantiate it and add one `registry.register(...)` call
       below.

That is the entire integration surface. This is the concrete answer
to "connect it to the Controller and forget about it."
"""

from __future__ import annotations

from jarvis.capabilities.apps_capability import (
    ApplicationsCapability,
)
from jarvis.capabilities.registry import CapabilityRegistry


def build_default_registry() -> CapabilityRegistry:
    """
    Build a CapabilityRegistry with every built-in Capability
    already registered.

    Each JarvisAgent instance gets its own registry (mirroring how
    every other Agent-owned service is constructed fresh in
    JarvisAgent.__init__), so tests can freely replace
    `agent.capability_registry` / `agent.capability_controller` with
    fakes without touching global state.
    """

    registry = CapabilityRegistry()

    # --------------------------------------------------
    # apps — P13/P15. Add future built-in capabilities below this
    # line, one `registry.register(...)` call each.
    # --------------------------------------------------

    registry.register(
        ApplicationsCapability()
    )

    return registry


__all__ = [
    "build_default_registry",
]