"""
Context compiler.

Transforms ContextRequest into an AgentContext.
"""

from typing import Any, Iterable

from jarvis.context.models import (
    AgentContext,
    ContextRequest,
)


class ContextCompiler:
    """
    Compiles selected information into LLM messages.
    """

    def __init__(
        self,
        system_prompt: str,
    ) -> None:
        self.system_prompt = system_prompt

    def compile(
        self,
        request: ContextRequest,
    ) -> AgentContext:
        """
        Compile a ContextRequest into an AgentContext.
        """

        messages: list[dict[str, Any]] = []

        messages.append(
            {
                "role": "system",
                "content": self._build_system_context(
                    request
                ),
            }
        )

        messages.extend(
            self._normalize_messages(
                request.conversation
            )
        )

        return AgentContext(
            messages=messages
        )

    @staticmethod
    def _format_core_memory(
        blocks: Iterable[Any],
    ) -> str:
        """
        Format Core Memory blocks for the LLM context.
        """

        sections: list[str] = []

        for block in blocks:

            label = getattr(
                block,
                "label",
                None,
            )

            content = getattr(
                block,
                "content",
                "",
            )

            capacity = getattr(
                block,
                "capacity",
                None,
            )

            if label is None:
                continue

            if capacity:
                usage = len(content)

                header = (
                    f"[{label}] "
                    f"{usage}/{capacity} characters"
                )

            else:
                header = f"[{label}]"

            sections.append(
                f"{header}\n"
                f"{content}"
            )

        if not sections:
            return "No Core Memory blocks."

        return "\n\n".join(
            sections
        )

    def _build_system_context(
        self,
        request: ContextRequest,
    ) -> str:
        """
        Build the system-level portion of context.

        Ordering:

            System Instructions
            Core Memory
            Current Agent State
        """

        core_memory_block = (
            self._format_core_memory(
                request.core_memory
            )
        )

        state_block = self._format_state(
            request.state
        )

        return (
            f"{self.system_prompt}\n\n"

            "CORE MEMORY\n"
            "-----------\n"
            f"{core_memory_block}\n\n"

            "CURRENT AGENT STATE\n"
            "------------------\n"
            f"{state_block}"
        )

    @staticmethod
    def _format_state(
        state: Any,
    ) -> str:
        """
        Format Agent State compactly.
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
        Normalize conversation entries into LLM messages.
        """

        normalized: list[dict[str, Any]] = []

        for message in conversation:

            if isinstance(message, dict):
                normalized.append(
                    dict(message)
                )
                continue

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