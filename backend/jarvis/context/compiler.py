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
    
    @staticmethod
    def _format_diary(
        events: Iterable[Any],
    ) -> str:
        """
        Format Diary events for temporary LLM context.

        Diary represents historical experiences/events rather
        than semantic memory.
        """

        sections: list[str] = []

        for event in events:
            description = getattr(
                event,
                "description",
                "",
            )

            if not description:
                continue

            event_type = getattr(
                event,
                "event_type",
                None,
            )

            source = getattr(
                event,
                "source",
                None,
            )

            created_at = getattr(
                event,
                "created_at",
                None,
            )

            identifier = getattr(
                event,
                "id",
                None,
            )

            header_parts = [
                "[diary]"
            ]

            if identifier is not None:
                header_parts.append(
                    f"id={identifier}"
                )

            if event_type:
                header_parts.append(
                    f"type={event_type}"
                )

            if source:
                header_parts.append(
                    f"source={source}"
                )

            header = " ".join(
                header_parts
            )

            if created_at:
                header += (
                    f" created_at={created_at}"
                )

            sections.append(
                f"{header}\n"
                f"{description}"
            )

        return "\n\n".join(
            sections
        )
    
    @staticmethod
    def _format_relationships(
        relationships: Iterable[Any],
    ) -> str:
        """
        Format explicitly supplied relationship records.

        Relationships are association data, not another memory tier.
        """

        sections: list[str] = []

        for relationship in relationships:
            source = getattr(
                relationship,
                "source",
                "",
            )

            target_type = getattr(
                relationship,
                "target_type",
                "",
            )

            target = getattr(
                relationship,
                "target",
                "",
            )

            if not source or not target:
                continue

            identifier = getattr(
                relationship,
                "id",
                None,
            )

            confidence = getattr(
                relationship,
                "confidence",
                None,
            )

            header = "[relationship]"

            if identifier is not None:
                header += f" id={identifier}"

            if confidence is not None:
                header += (
                    f" confidence={confidence:.3f}"
                )

            content = (
                f"{source} → "
                f"{target_type}: "
                f"{target}"
            )

            sections.append(
                f"{header}\n"
                f"{content}"
            )

        return "\n\n".join(
            sections
        )
    @staticmethod
    def _format_operation_results(
        results: Iterable[Any],
    ) -> str:
        """
        Format operation results for temporary LLM context.

        Operation results describe the outcome of work performed
        during the current reasoning cycle. They are ephemeral and
        are not treated as memory.
        """

        sections: list[str] = []

        for result in results:
            operation = getattr(
                result,
                "operation",
                None,
            )

            status = getattr(
                result,
                "status",
                None,
            )

            if operation is None or status is None:
                continue

            if hasattr(status, "value"):
                status_value = status.value
            else:
                status_value = str(status)

            lines = [
                f"[operation={operation}]",
                f"status={status_value}",
            ]

            success = getattr(
                result,
                "success",
                None,
            )

            if success is not None:
                lines.append(
                    f"success={success}"
                )

            data = getattr(
                result,
                "data",
                None,
            )

            if data is not None:
                lines.append(
                    f"data={data}"
                )

            error_code = getattr(
                result,
                "error_code",
                None,
            )

            if error_code is not None:
                if hasattr(
                    error_code,
                    "value",
                ):
                    error_code = (
                        error_code.value
                    )

                lines.append(
                    f"error_code={error_code}"
                )

            error_message = getattr(
                result,
                "error_message",
                None,
            )

            if error_message is not None:
                lines.append(
                    f"error_message={error_message}"
                )

            sections.append(
                "\n".join(lines)
            )

        if not sections:
            return ""

        return "\n\n".join(
            sections
        )
    @staticmethod
    def _format_retrieval_results(
        results: Iterable[Any],
    ) -> str:
        """
        Format unified RetrievalResult objects.

        Source identity, identifier, and relevance score are
        preserved so the compiled context retains the complete
        retrieval metadata required by downstream reasoning.
        """

        sections: list[str] = []

        for result in results:
            content = getattr(
                result,
                "content",
                "",
            )

            if not content:
                continue

            source = getattr(
                result,
                "source",
                None,
            )

            identifier = getattr(
                result,
                "identifier",
                None,
            )

            score = getattr(
                result,
                "score",
                None,
            )

            if source:
                header = f"[{source}]"
            else:
                header = "[retrieval]"

            if identifier is not None:
                header += f" id={identifier}"

            if score is not None:
                header += f" score={score:.3f}"

            sections.append(
                f"{header}\n"
                f"{content}"
            )

        if not sections:
            return ""

        return "\n\n".join(
            sections
        )
    @staticmethod
    def _format_capability_information(
        information: Iterable[Any],
    ) -> str:
        """
        Format information supplied by capabilities.

        Context consumes capability-produced information but does
        not depend on or import capability implementations.
        """

        sections: list[str] = []

        for item in information:
            if item is None:
                continue

            if isinstance(item, str):
                content = item

            elif isinstance(item, dict):
                lines: list[str] = []

                for key, value in item.items():
                    lines.append(
                        f"{key}: {value}"
                    )

                content = "\n".join(lines)

            else:
                content = str(item)

            content = content.strip()

            if not content:
                continue

            sections.append(content)

        return "\n\n".join(sections)
    @staticmethod
    def _fallback_retrieval_results(
        request: ContextRequest,
    ) -> list[Any]:
        """
        Build a compatibility retrieval surface from the
        domain-specific ContextRequest fields.

        The unified retrieval_results field remains the
        authoritative path when populated.

        This fallback allows information sources that have
        already been explicitly selected for Context to remain
        usable without requiring them to be wrapped in a
        RetrievalResult first.
        """

        results: list[Any] = []

        results.extend(
            request.memories
        )

        results.extend(
            request.diary
        )

        results.extend(
            request.knowledge
        )

        results.extend(
            request.relationships
        )

        return results

    def _get_retrieval_results(
        self,
        request: ContextRequest,
    ) -> list[Any]:
        """
        Resolve the information that should appear in the
        unified Retrieved Information section.

        Priority:

        1. Explicit unified retrieval_results.
        2. Explicit domain-specific retrieval/context fields.

        This prevents duplicate rendering when both are supplied.
        """

        if request.retrieval_results:
            return list(
                request.retrieval_results
            )

        return self._fallback_retrieval_results(
            request
        )

    def _build_system_context(
        self,
        request: ContextRequest,
    ) -> str:
        """
        Build the system-level portion of context.
        """

        state_block = self._format_state(
            request.state
        )

        core_memory_block = (
            self._format_core_memory(
                request.core_memory
            )
        )
        diary_information = (
            self._format_diary(
                request.diary
            )
        )
        operation_result_information = (
            self._format_operation_results(
                request.operation_results
            )
        )
        relationship_information = (
            self._format_relationships(
                request.relationships
            )
        )
        retrieval_results = (
            self._get_retrieval_results(
                request
            )
        )
        capability_information = (
            self._format_capability_information(
                request.capability_information
            )
        )
        retrieved_information = (
            self._format_retrieval_results(
                retrieval_results
            )
        )

        sections = [
            f"{self.system_prompt}",
            "CURRENT AGENT STATE\n"
            "------------------\n"
            f"{state_block}",
            "CORE MEMORY\n"
            "-----------\n"
            f"{core_memory_block}",
        ]
        if diary_information:
            sections.append(
                "DIARY\n"
                "-----\n"
                f"{diary_information}"
            )
        if relationship_information:
            sections.append(
                "RELATIONSHIPS\n"
                "-------------\n"
                f"{relationship_information}"
            )
        if capability_information:
            sections.append(
                "CAPABILITY INFORMATION\n"
                "----------------------\n"
                f"{capability_information}"
            )
        if operation_result_information:
            sections.append(
                "OPERATION RESULTS\n"
                "-----------------\n"
                f"{operation_result_information}"
            )
        if retrieved_information:
            sections.append(
                "RETRIEVED INFORMATION\n"
                "---------------------\n"
                f"{retrieved_information}"
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

            normalized.append(
                item
            )

        return normalized