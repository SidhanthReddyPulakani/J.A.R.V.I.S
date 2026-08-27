"""
Context compiler.

Transforms ContextRequest into an AgentContext.

The compiler is responsible for deciding how supplied
information is represented in the LLM context.

It does not perform retrieval or persistence.
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

        messages: list[
            dict[str, Any]
        ] = []

        messages.append(
            {
                "role": "system",
                "content": (
                    self._build_system_context(
                        request
                    )
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

    def _build_system_context(
        self,
        request: ContextRequest,
    ) -> str:
        """
        Build the system-level portion of context.

        Information is deliberately separated into sections
        so the LLM can distinguish persistent memory,
        retrieved information, and current state.
        """

        sections: list[str] = []

        sections.append(
            self.system_prompt
        )

        # --------------------------------------------------
        # Core Memory
        # --------------------------------------------------

        if request.core_memory:

            sections.extend(
                [
                    "",
                    "CORE MEMORY",
                    "-----------",
                    self._format_core_memory(
                        request.core_memory
                    ),
                ]
            )

        # --------------------------------------------------
        # Retrieved information
        # --------------------------------------------------

        if request.retrieval_results:

            sections.extend(
                [
                    "",
                    "RETRIEVED INFORMATION",
                    "----------------------",
                    self._format_retrieval_results(
                        request.retrieval_results
                    ),
                ]
            )

        # --------------------------------------------------
        # Agent State
        # --------------------------------------------------

        sections.extend(
            [
                "",
                "CURRENT AGENT STATE",
                "------------------",
                self._format_state(
                    request.state
                ),
            ]
        )

        return "\n".join(
            sections
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

            content = str(
                content or ""
            )

            if capacity:

                usage = len(
                    content
                )

                header = (
                    f"[{label}] "
                    f"{usage}/{capacity} characters"
                )

            else:

                header = (
                    f"[{label}]"
                )

            sections.append(
                f"{header}\n"
                f"{content}"
            )

        if not sections:
            return (
                "No Core Memory blocks."
            )

        return "\n\n".join(
            sections
        )

    @staticmethod
    def _format_retrieval_results(
        results: Iterable[Any],
    ) -> str:
        """
        Format normalized RetrievalResult objects.

        Retrieval remains a separate conceptual layer.
        The compiler only consumes its output.
        """

        sections: list[str] = []

        for result in results:

            source = getattr(
                result,
                "source",
                "unknown",
            )

            content = getattr(
                result,
                "content",
                "",
            )

            score = getattr(
                result,
                "score",
                None,
            )

            identifier = getattr(
                result,
                "identifier",
                None,
            )

            content = str(
                content or ""
            ).strip()

            if not content:
                continue

            if score is None:

                header = (
                    f"[{source}]"
                )

            else:

                header = (
                    f"[{source}] "
                    f"score={float(score):.3f}"
                )

            if identifier is not None:

                header += (
                    f" id={identifier}"
                )

            sections.append(
                f"{header}\n"
                f"{content}"
            )

        if not sections:

            return (
                "No retrieved information."
            )

        return "\n\n".join(
            sections
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

        return "\n".join(
            lines
        )

    @staticmethod
    def _normalize_messages(
        conversation: Iterable[Any],
    ) -> list[dict[str, Any]]:
        """
        Normalize conversation entries into LLM messages.

        Existing Ollama message objects are converted into
        dictionaries where possible.
        """

        normalized: list[
            dict[str, Any]
        ] = []

        for message in conversation:

            if isinstance(
                message,
                dict,
            ):

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

            item: dict[
                str,
                Any,
            ] = {
                "role": role,
                "content": content or "",
            }

            tool_calls = getattr(
                message,
                "tool_calls",
                None,
            )

            if tool_calls:

                item[
                    "tool_calls"
                ] = tool_calls

            normalized.append(
                item
            )

        return normalized