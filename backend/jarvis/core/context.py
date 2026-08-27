"""
Compatibility wrapper for the reconstructed Context system.

The actual implementation now lives under jarvis.context.
"""

from jarvis.context import (
    AgentContext,
    ContextCompiler,
    ContextRequest,
    ContextWindowManager,
)


class ContextManager:
    """
    Backwards-compatible facade.

    Existing callers can continue using:

        manager.build(
            state=...,
            conversation=...
        )

    while the new Context architecture lives underneath.
    """

    def __init__(
        self,
        system_prompt: str,
    ) -> None:
        self.compiler = ContextCompiler(
            system_prompt
        )

    def build(
        self,
        *,
        state,
        conversation,
    ) -> AgentContext:

        request = ContextRequest(
            user_input="",
            state=state,
            conversation=list(
                conversation
            ),
        )

        return self.compiler.compile(
            request
        )