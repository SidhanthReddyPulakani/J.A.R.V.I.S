"""
P9-P13 — Capability Core.

This package holds the formal interfaces every future capability
implements (P9), the Capability Registry (P11), the Capability
Controller (P12), and the first real capability migrated behind
them (P13 — Apps).

Nothing in this package is wired into the live Agent reasoning loop
yet. That wiring is P15's job, once the Controller has proven itself
against a real capability here.
"""

from __future__ import annotations