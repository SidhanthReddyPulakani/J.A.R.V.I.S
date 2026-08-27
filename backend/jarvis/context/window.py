"""
Context window management.

Responsible for enforcing the bounded context presented to
the LLM.

Advanced pressure handling will be added later.
"""

from jarvis.context.models import AgentContext


class ContextWindowManager:
    """
    Manages the final bounded context supplied to the LLM.
    """

    def __init__(
        self,
        max_messages: int | None = None,
    ) -> None:
        self.max_messages = max_messages

    def prepare(
        self,
        context: AgentContext,
    ) -> AgentContext:
        """
        Prepare context for the LLM.

        The system message is always retained.

        Message-count limiting is intentionally simple for now.
        Token-aware management will be added later.
        """

        if self.max_messages is None:
            return context

        messages = context.as_messages()

        if len(messages) <= self.max_messages:
            return context

        system_message = messages[0]

        remaining = messages[
            -(self.max_messages - 1):
        ]

        return AgentContext(
            messages=[
                system_message,
                *remaining,
            ]
        )