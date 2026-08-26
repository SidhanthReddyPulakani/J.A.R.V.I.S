"""
Jarvis Context Management.

Context is the temporary, compiled information supplied to the
LLM for a reasoning step.

It is NOT persistent storage.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable

from jarvis.core.state import AgentState


@dataclass
class AgentContext:
    """
    Compiled context for one LLM reasoning step.

    The messages field is what ultimately gets passed to the LLM.
    """

    messages: list[dict[str, Any]] = field(
        default_factory=list
    )

    def as_messages(self) -> list[dict[str, Any]]:
        """
        Return the messages to send to the LLM.

        A copy is returned so callers cannot accidentally mutate
        the compiled context.
        """
        return list(self.messages)


class ContextManager:
    """
    Builds the temporary context required by the LLM.

    Current inputs:
        - system instructions
        - Agent State
        - conversation history

    Future inputs:
        - relevant Memory
        - Diary-derived information
        - relevant project knowledge
        - capability information
        - other retrieved knowledge
    """

    def __init__(
        self,
        system_prompt: str,
    ) -> None:
        self.system_prompt = system_prompt

    def build(
        self,
        *,
        state: AgentState,
        conversation: Iterable[Any],
    ) -> AgentContext:
        """
        Build a fresh context for the current reasoning step.
        """

        messages: list[dict[str, Any]] = []

        messages.append(
            {
                "role": "system",
                "content": self._build_system_context(
                    state
                ),
            }
        )

        messages.extend(
            self._normalize_messages(
                conversation
            )
        )

        return AgentContext(
            messages=messages
        )

    def _build_system_context(
        self,
        state: AgentState,
    ) -> str:
        """
        Combine stable system instructions with the current
        Agent State.

        State is injected here rather than permanently modifying
        the system prompt.
        """

        state_block = self._format_state(
            state
        )

        return (
            f"{self.system_prompt}\n\n"
            "CURRENT AGENT STATE\n"
            "------------------\n"
            f"{state_block}"
        )

    @staticmethod
    def _format_state(
        state: AgentState,
    ) -> str:
        """
        Convert the current AgentState into compact,
        human-readable context.
        """

        lines = [
            f"Agent ID: {state.agent_id}",
            f"Mode: {state.mode}",
            (
                "Conversation ID: "
                f"{state.conversation_id}"
            ),
            (
                "Current task: "
                f"{state.current_task or 'None'}"
            ),
            (
                "Current goal: "
                f"{state.current_goal or 'None'}"
            ),
            (
                "Active project: "
                f"{state.active_project or 'None'}"
            ),
            (
                "Active operation: "
                f"{state.active_operation or 'None'}"
            ),
            (
                "Operation status: "
                f"{state.operation_status}"
            ),
        ]

        return "\n".join(lines)

    @staticmethod
    def _normalize_messages(
        conversation: Iterable[Any],
    ) -> list[dict[str, Any]]:
        """
        Normalize conversation entries into the message
        structure expected by the LLM.

        Existing Ollama message objects are converted to
        dictionaries where possible.
        """

        normalized: list[dict[str, Any]] = []

        for message in conversation:

            if isinstance(message, dict):
                normalized.append(
                    dict(message)
                )
                continue

            # Ollama Message objects expose their fields as
            # attributes rather than plain dictionaries.
            role = getattr(
                message,
                "role",
                None,
            )

            content = getattr(
                message,
                "content",
                None,
            )

            if role is None:
                continue

            item: dict[str, Any] = {
                "role": role,
                "content": content or "",
            }

            tool_calls = getattr(
                message,
                "tool_calls",
                None,
            )

            if tool_calls:
                item["tool_calls"] = tool_calls

            normalized.append(item)

        return normalized