"""
J.A.R.V.I.S.
TEST 2 — RETRIEVAL → CONTEXT → LLM PIPELINE TRACE

Purpose
-------
Observe the complete runtime context pipeline without changing
production behavior.

This test traces:

    User Input
        ↓
    RetrievalService
        ↓
    Retrieval Providers
        ↓
    Diary
        ↓
    ContextRequest
        ↓
    ContextCompiler
        ↓
    ContextWindowManager
        ↓
    LLMClient
        ↓
    Exact messages/tools sent to the LLM

Important
---------
This is an observational diagnostic.

It does NOT:
- change production architecture
- change retrieval ranking
- modify ContextCompiler
- modify ContextWindowManager
- modify persistent memory
- write diagnostic data into the J.A.R.V.I.S. database

The test performs one real Agent turn so we can observe the
actual runtime path.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# WINDOWS UTF-8
# ============================================================

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ============================================================
# IMPORTS
# ============================================================

from jarvis.core.agent import JarvisAgent
from jarvis.context import ContextRequest


# ============================================================
# CONFIGURATION
# ============================================================

TEST_INPUT = "Open WhatsApp."

REPORT_FILE = Path(
    "test_retrieval_context_pipeline_report.json"
)

MAX_CONTENT_PREVIEW = 5000


# ============================================================
# GLOBAL TRACE STORAGE
# ============================================================

TRACE: dict[str, Any] = {
    "metadata": {
        "test": "TEST 2 — Retrieval → Context → LLM Pipeline",
        "timestamp": datetime.now().astimezone().isoformat(),
        "input": TEST_INPUT,
    },

    "retrieval": {
        "providers": {},
        "global_results": [],
    },

    "diary": {},

    "context_request": {},

    "compiled_context": {
        "messages": [],
    },

    "window_manager": {},

    "llm_calls": [],

    "agent_result": None,

    "errors": [],
}


# ============================================================
# HELPERS
# ============================================================

def estimate_tokens(text: str) -> int:
    """
    Same crude approximation used by the existing context-window
    implementation: approximately one token per four characters.
    """
    if not text:
        return 0

    return max(1, len(text) // 4)


def safe_json(value: Any) -> Any:
    """
    Convert arbitrary project objects into JSON-safe structures.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(k): safe_json(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            safe_json(v)
            for v in value
        ]

    if hasattr(value, "model_dump"):
        try:
            return safe_json(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            return safe_json(value.dict())
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return {
                str(k): safe_json(v)
                for k, v in vars(value).items()
                if not k.startswith("_")
            }
        except Exception:
            pass

    return str(value)


def text_from_value(value: Any) -> str:
    """
    Best-effort textual representation for size accounting.
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    try:
        return json.dumps(
            safe_json(value),
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return str(value)


def summarize_value(value: Any) -> dict[str, Any]:
    """
    Return count / character / token statistics.
    """

    serialized = text_from_value(value)

    if isinstance(value, (list, tuple, dict)):
        count = len(value)
    elif value is None:
        count = 0
    else:
        count = 1

    return {
        "count": count,
        "characters": len(serialized),
        "estimated_tokens": estimate_tokens(serialized),
        "serialized": safe_json(value),
    }


def message_summary(message: Any) -> dict[str, Any]:
    """
    Summarize an LLM message while retaining its complete content.
    """

    data = safe_json(message)

    if isinstance(data, dict):
        role = data.get("role")
        content = data.get("content", "")

        if content is None:
            content = ""

        return {
            "role": role,
            "content": content,
            "characters": len(str(content)),
            "estimated_tokens": estimate_tokens(
                str(content)
            ),
            "all_fields": data,
        }

    serialized = text_from_value(data)

    return {
        "role": None,
        "content": serialized,
        "characters": len(serialized),
        "estimated_tokens": estimate_tokens(serialized),
        "all_fields": data,
    }


def retrieval_summary(result: Any) -> dict[str, Any]:
    """
    Preserve every useful RetrievalResult field.
    """

    data = safe_json(result)

    if isinstance(data, dict):
        content = data.get("content", "")

        return {
            "source": data.get("source"),
            "identifier": data.get("identifier"),
            "score": data.get("score"),
            "content": content,
            "characters": len(str(content)),
            "estimated_tokens": estimate_tokens(
                str(content)
            ),
            "metadata": data.get("metadata"),
            "all_fields": data,
        }

    serialized = text_from_value(data)

    return {
        "source": None,
        "identifier": None,
        "score": None,
        "content": serialized,
        "characters": len(serialized),
        "estimated_tokens": estimate_tokens(serialized),
        "metadata": {},
        "all_fields": data,
    }


def print_header(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_subheader(title: str) -> None:
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def print_stat(
    name: str,
    value: Any,
) -> None:
    print(f"{name:<35}: {value}")


def print_result_table(
    results: list[dict[str, Any]],
) -> None:

    if not results:
        print("  [none]")
        return

    for index, result in enumerate(
        results,
        start=1,
    ):
        print(
            f"\n  [{index}] "
            f"source={result.get('source')} "
            f"id={result.get('identifier')} "
            f"score={result.get('score')}"
        )

        print(
            f"      chars={result.get('characters')} "
            f"tokens≈{result.get('estimated_tokens')}"
        )

        content = str(
            result.get("content", "")
        )

        if len(content) > MAX_CONTENT_PREVIEW:
            content = (
                content[:MAX_CONTENT_PREVIEW]
                + "\n      ... [TRUNCATED FOR CONSOLE] ..."
            )

        print("      content:")
        print(
            "\n".join(
                f"        {line}"
                for line in content.splitlines()
            )
        )

        metadata = result.get("metadata")

        if metadata:
            print("      metadata:")
            print(
                json.dumps(
                    metadata,
                    indent=8,
                    ensure_ascii=False,
                    default=str,
                )
            )


# ============================================================
# PROVIDER WRAPPING
# ============================================================

def instrument_retrieval(agent: JarvisAgent) -> None:
    """
    Wrap RetrievalService.search and every registered provider.

    This does not alter the returned data.

    We capture:
    - provider candidates
    - global merged results
    - source distribution
    - scores
    - sizes
    """

    retrieval = agent.retrieval

    # --------------------------------------------------------
    # Provider instrumentation
    # --------------------------------------------------------

    providers = list(
        getattr(
            retrieval,
            "_providers",
            {},
        ).values()
    )

    for provider in providers:

        provider_name = (
            getattr(
                provider,
                "name",
                None,
            )
            or provider.__class__.__name__
        )

        original_search = provider.search

        def make_wrapper(
            original,
            name,
        ):

            def wrapper(
                query,
                limit=10,
                **kwargs,
            ):

                results = original(
                    query,
                    limit=limit,
                    **kwargs,
                )

                normalized = [
                    retrieval_summary(result)
                    for result in (
                        results or []
                    )
                ]

                TRACE["retrieval"][
                    "providers"
                ][name] = {
                    "query": query,
                    "requested_limit": limit,
                    "result_count": len(
                        normalized
                    ),
                    "estimated_tokens": sum(
                        item[
                            "estimated_tokens"
                        ]
                        for item in normalized
                    ),
                    "results": normalized,
                }

                return results

            return wrapper

        provider.search = make_wrapper(
            original_search,
            provider_name,
        )

    # --------------------------------------------------------
    # RetrievalService instrumentation
    # --------------------------------------------------------

    original_retrieval_search = retrieval.search

    def retrieval_wrapper(
        query,
        sources=None,
        limit=10,
        **kwargs,
    ):

        results = original_retrieval_search(
            query,
            sources=sources,
            limit=limit,
            **kwargs,
        )

        normalized = [
            retrieval_summary(result)
            for result in (
                results or []
            )
        ]

        source_counts = Counter(
            item.get("source")
            for item in normalized
        )

        TRACE["retrieval"][
            "global_results"
        ] = normalized

        TRACE["retrieval"][
            "global_summary"
        ] = {
            "query": query,
            "sources_requested": sources,
            "limit": limit,
            "result_count": len(normalized),
            "source_distribution": dict(
                source_counts
            ),
            "characters": sum(
                item["characters"]
                for item in normalized
            ),
            "estimated_tokens": sum(
                item["estimated_tokens"]
                for item in normalized
            ),
        }

        return results

    retrieval.search = retrieval_wrapper


# ============================================================
# DIARY INSTRUMENTATION
# ============================================================

def instrument_diary(agent: JarvisAgent) -> None:

    diary = agent.diary

    original_search = diary.search
    original_recent = diary.recent

    def search_wrapper(
        query,
        conversation_id=None,
        limit=10,
        **kwargs,
    ):

        results = original_search(
            query,
            conversation_id=conversation_id,
            limit=limit,
            **kwargs,
        )

        normalized = safe_json(
            results or []
        )

        TRACE["diary"]["search"] = {
            "query": query,
            "conversation_id": conversation_id,
            "limit": limit,
            "summary": summarize_value(
                normalized
            ),
        }

        TRACE["diary"]["search"][
            "results"
        ] = normalized

        return results

    def recent_wrapper(
        conversation_id=None,
        limit=10,
        **kwargs,
    ):

        results = original_recent(
            conversation_id=conversation_id,
            limit=limit,
            **kwargs,
        )

        normalized = safe_json(
            results or []
        )

        TRACE["diary"]["recent"] = {
            "conversation_id": conversation_id,
            "limit": limit,
            "summary": summarize_value(
                normalized
            ),
        }

        TRACE["diary"]["recent"][
            "results"
        ] = normalized

        return results

    diary.search = search_wrapper
    diary.recent = recent_wrapper


# ============================================================
# CONTEXT REQUEST INSTRUMENTATION
# ============================================================

def instrument_context_build(agent: JarvisAgent) -> None:
    """
    Wrap Agent._build_context.

    This is the most useful boundary for determining exactly
    what the Agent gives to the Context subsystem.
    """

    original_build_context = agent._build_context

    def wrapper(
        user_input="",
        operation_results=None,
    ):

        # --------------------------------------------
        # Reproduce the ContextRequest inputs by
        # observing the call into ContextCompiler.
        # --------------------------------------------

        original_compile = (
            agent.context_compiler.compile
        )

        captured_request = {
            "request": None,
        }

        def compile_wrapper(request):
            captured_request[
                "request"
            ] = request

            return original_compile(
                request
            )

        agent.context_compiler.compile = (
            compile_wrapper
        )

        try:
            context = original_build_context(
                user_input=user_input,
                operation_results=operation_results,
            )

            request = captured_request[
                "request"
            ]

            if request is not None:

                request_data = {
                    "user_input": summarize_value(
                        request.user_input
                    ),
                    "state": summarize_value(
                        request.state
                    ),
                    "conversation": summarize_value(
                        request.conversation
                    ),
                    "core_memory": summarize_value(
                        request.core_memory
                    ),
                    "memories": summarize_value(
                        request.memories
                    ),
                    "diary": summarize_value(
                        request.diary
                    ),
                    "knowledge": summarize_value(
                        request.knowledge
                    ),
                    "relationships": summarize_value(
                        request.relationships
                    ),
                    "capability_information": (
                        summarize_value(
                            request.capability_information
                        )
                    ),
                    "operation_results": (
                        summarize_value(
                            request.operation_results
                        )
                    ),
                    "retrieval_results": (
                        summarize_value(
                            request.retrieval_results
                        )
                    ),
                }

                TRACE[
                    "context_request"
                ] = request_data

            return context

        finally:
            agent.context_compiler.compile = (
                original_compile
            )

    agent._build_context = wrapper


# ============================================================
# CONTEXT WINDOW INSTRUMENTATION
# ============================================================

def instrument_window_manager(
    agent: JarvisAgent,
) -> None:

    manager = agent.context_window

    # --------------------------------------------------------
    # fit_retrieval_budget
    # --------------------------------------------------------

    original_fit = (
        manager.fit_retrieval_budget
    )

    def fit_wrapper(results, *args, **kwargs):

        before = [
            retrieval_summary(result)
            for result in (
                results or []
            )
        ]

        output = original_fit(
            results,
            *args,
            **kwargs,
        )

        after = [
            retrieval_summary(result)
            for result in (
                output or []
            )
        ]

        TRACE[
            "window_manager"
        ].setdefault(
            "retrieval_budget",
            [],
        ).append(
            {
                "before": {
                    "count": len(before),
                    "tokens": sum(
                        item[
                            "estimated_tokens"
                        ]
                        for item in before
                    ),
                    "results": before,
                },
                "after": {
                    "count": len(after),
                    "tokens": sum(
                        item[
                            "estimated_tokens"
                        ]
                        for item in after
                    ),
                    "results": after,
                },
            }
        )

        return output

    manager.fit_retrieval_budget = fit_wrapper

    # --------------------------------------------------------
    # prepare
    # --------------------------------------------------------

    original_prepare = manager.prepare

    def prepare_wrapper(context, *args, **kwargs):

        before_messages = [
            message_summary(message)
            for message in (
                getattr(
                    context,
                    "messages",
                    [],
                )
                or []
            )
        ]

        output = original_prepare(
            context,
            *args,
            **kwargs,
        )

        after_messages = [
            message_summary(message)
            for message in (
                getattr(
                    output,
                    "messages",
                    [],
                )
                or []
            )
        ]

        TRACE[
            "window_manager"
        ].setdefault(
            "prepare_calls",
            [],
        ).append(
            {
                "before": {
                    "message_count": len(
                        before_messages
                    ),
                    "characters": sum(
                        item["characters"]
                        for item in before_messages
                    ),
                    "estimated_tokens": sum(
                        item[
                            "estimated_tokens"
                        ]
                        for item in before_messages
                    ),
                    "messages": before_messages,
                },

                "after": {
                    "message_count": len(
                        after_messages
                    ),
                    "characters": sum(
                        item["characters"]
                        for item in after_messages
                    ),
                    "estimated_tokens": sum(
                        item[
                            "estimated_tokens"
                        ]
                        for item in after_messages
                    ),
                    "messages": after_messages,
                },
            }
        )

        return output

    manager.prepare = prepare_wrapper


# ============================================================
# LLM CLIENT INSTRUMENTATION
# ============================================================

def instrument_llm(agent: JarvisAgent) -> None:
    """
    Capture the exact arguments passed to LLMClient.chat().

    This is the final source-of-truth for:

        WHAT ACTUALLY REACHES THE MODEL
    """

    llm = agent.llm

    original_chat = llm.chat

    def chat_wrapper(
        messages,
        tools=None,
        *args,
        **kwargs,
    ):

        normalized_messages = [
            message_summary(message)
            for message in (
                messages or []
            )
        ]

        normalized_tools = safe_json(
            tools or []
        )

        total_message_chars = sum(
            item["characters"]
            for item in normalized_messages
        )

        total_message_tokens = sum(
            item["estimated_tokens"]
            for item in normalized_messages
        )

        TRACE[
            "llm_calls"
        ].append(
            {
                "call_number": len(
                    TRACE["llm_calls"]
                ) + 1,

                "messages": {
                    "count": len(
                        normalized_messages
                    ),
                    "characters": (
                        total_message_chars
                    ),
                    "estimated_tokens": (
                        total_message_tokens
                    ),
                    "items": normalized_messages,
                },

                "tools": {
                    "count": len(
                        normalized_tools
                    )
                    if isinstance(
                        normalized_tools,
                        list,
                    )
                    else 1,

                    "characters": len(
                        text_from_value(
                            normalized_tools
                        )
                    ),

                    "estimated_tokens": (
                        estimate_tokens(
                            text_from_value(
                                normalized_tools
                            )
                        )
                    ),

                    "definitions": normalized_tools,
                },
            }
        )

        return original_chat(
            messages,
            tools=tools,
            *args,
            **kwargs,
        )

    llm.chat = chat_wrapper


# ============================================================
# CONTEXT COMPILER DIRECT INSTRUMENTATION
# ============================================================

def instrument_compiler(
    agent: JarvisAgent,
) -> None:

    compiler = agent.context_compiler

    original_compile = compiler.compile

    def compile_wrapper(request):

        output = original_compile(
            request
        )

        messages = getattr(
            output,
            "messages",
            [],
        ) or []

        normalized = [
            message_summary(message)
            for message in messages
        ]

        TRACE[
            "compiled_context"
        ].setdefault(
            "compile_calls",
            [],
        ).append(
            {
                "message_count": len(
                    normalized
                ),
                "characters": sum(
                    item["characters"]
                    for item in normalized
                ),
                "estimated_tokens": sum(
                    item[
                        "estimated_tokens"
                    ]
                    for item in normalized
                ),
                "messages": normalized,
            }
        )

        return output

    compiler.compile = compile_wrapper


# ============================================================
# PRINT RETRIEVAL
# ============================================================

def print_retrieval_report() -> None:

    print_header(
        "1. RETRIEVAL — PROVIDER-BY-PROVIDER TRACE"
    )

    providers = TRACE[
        "retrieval"
    ].get(
        "providers",
        {},
    )

    if not providers:
        print("No provider results captured.")
    else:

        for name, data in providers.items():

            print_subheader(
                f"Provider: {name}"
            )

            print_stat(
                "Query",
                data.get("query"),
            )

            print_stat(
                "Requested limit",
                data.get(
                    "requested_limit"
                ),
            )

            print_stat(
                "Result count",
                data.get(
                    "result_count"
                ),
            )

            print_stat(
                "Estimated tokens",
                data.get(
                    "estimated_tokens"
                ),
            )

            print_result_table(
                data.get(
                    "results",
                    [],
                )
            )

    print_subheader(
        "Global Retrieval Result"
    )

    summary = TRACE[
        "retrieval"
    ].get(
        "global_summary",
        {},
    )

    for key, value in summary.items():
        print_stat(
            key,
            value,
        )

    print_result_table(
        TRACE[
            "retrieval"
        ].get(
            "global_results",
            [],
        )
    )


# ============================================================
# PRINT DIARY
# ============================================================

def print_diary_report() -> None:

    print_header(
        "2. DIARY — DIRECT AGENT INPUT"
    )

    for operation_name, data in (
        TRACE["diary"].items()
    ):

        if not isinstance(data, dict):
            continue

        print_subheader(
            operation_name
        )

        summary = data.get(
            "summary",
            {},
        )

        print_stat(
            "Count",
            summary.get("count"),
        )

        print_stat(
            "Characters",
            summary.get("characters"),
        )

        print_stat(
            "Estimated tokens",
            summary.get(
                "estimated_tokens"
            ),
        )

        results = data.get(
            "results"
        )

        if results:
            print(
                json.dumps(
                    results,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            )


# ============================================================
# PRINT CONTEXT REQUEST
# ============================================================

def print_context_request_report() -> None:

    print_header(
        "3. CONTEXT REQUEST — AGENT → CONTEXT"
    )

    request = TRACE[
        "context_request"
    ]

    if not request:
        print(
            "No ContextRequest captured."
        )
        return

    for field_name, field_data in request.items():

        print_subheader(
            field_name
        )

        print_stat(
            "Count",
            field_data.get(
                "count"
            ),
        )

        print_stat(
            "Characters",
            field_data.get(
                "characters"
            ),
        )

        print_stat(
            "Estimated tokens",
            field_data.get(
                "estimated_tokens"
            ),
        )

        serialized = field_data.get(
            "serialized"
        )

        print(
            json.dumps(
                serialized,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )


# ============================================================
# PRINT COMPILER
# ============================================================

def print_compiler_report() -> None:

    print_header(
        "4. CONTEXT COMPILER — CONTEXT → AGENT CONTEXT"
    )

    calls = TRACE[
        "compiled_context"
    ].get(
        "compile_calls",
        [],
    )

    if not calls:
        print(
            "No compiler calls captured."
        )
        return

    for index, call in enumerate(
        calls,
        start=1,
    ):

        print_subheader(
            f"Compile Call #{index}"
        )

        print_stat(
            "Message count",
            call["message_count"],
        )

        print_stat(
            "Characters",
            call["characters"],
        )

        print_stat(
            "Estimated tokens",
            call["estimated_tokens"],
        )

        for message_index, message in enumerate(
            call["messages"],
            start=1,
        ):

            print(
                f"\n  MESSAGE {message_index}"
            )

            print_stat(
                "  Role",
                message.get("role"),
            )

            print_stat(
                "  Characters",
                message.get(
                    "characters"
                ),
            )

            print_stat(
                "  Estimated tokens",
                message.get(
                    "estimated_tokens"
                ),
            )

            content = message.get(
                "content",
                "",
            )

            print(
                "  Content:"
            )

            print(content)


# ============================================================
# PRINT WINDOW MANAGER
# ============================================================

def print_window_report() -> None:

    print_header(
        "5. CONTEXT WINDOW MANAGER"
    )

    retrieval_budget = TRACE[
        "window_manager"
    ].get(
        "retrieval_budget",
        [],
    )

    for index, item in enumerate(
        retrieval_budget,
        start=1,
    ):

        print_subheader(
            f"Retrieval Budget Pass #{index}"
        )

        before = item["before"]
        after = item["after"]

        print_stat(
            "Before count",
            before["count"],
        )

        print_stat(
            "Before tokens",
            before["tokens"],
        )

        print_stat(
            "After count",
            after["count"],
        )

        print_stat(
            "After tokens",
            after["tokens"],
        )

    prepare_calls = TRACE[
        "window_manager"
    ].get(
        "prepare_calls",
        [],
    )

    for index, item in enumerate(
        prepare_calls,
        start=1,
    ):

        print_subheader(
            f"Prepare Pass #{index}"
        )

        before = item["before"]
        after = item["after"]

        print_stat(
            "Before message count",
            before["message_count"],
        )

        print_stat(
            "Before characters",
            before["characters"],
        )

        print_stat(
            "Before estimated tokens",
            before["estimated_tokens"],
        )

        print_stat(
            "After message count",
            after["message_count"],
        )

        print_stat(
            "After characters",
            after["characters"],
        )

        print_stat(
            "After estimated tokens",
            after["estimated_tokens"],
        )

        removed = max(
            0,
            before["message_count"]
            - after["message_count"],
        )

        print_stat(
            "Messages removed",
            removed,
        )


# ============================================================
# PRINT LLM
# ============================================================

def print_llm_report() -> None:

    print_header(
        "6. EXACT LLM CLIENT INPUT"
    )

    calls = TRACE[
        "llm_calls"
    ]

    if not calls:
        print(
            "No LLM calls captured."
        )
        return

    for call in calls:

        print_subheader(
            f"LLM Call #{call['call_number']}"
        )

        messages = call[
            "messages"
        ]

        tools = call[
            "tools"
        ]

        print_stat(
            "Message count",
            messages["count"],
        )

        print_stat(
            "Message characters",
            messages["characters"],
        )

        print_stat(
            "Message estimated tokens",
            messages[
                "estimated_tokens"
            ],
        )

        print_stat(
            "Tool count",
            tools["count"],
        )

        print_stat(
            "Tool characters",
            tools["characters"],
        )

        print_stat(
            "Tool estimated tokens",
            tools[
                "estimated_tokens"
            ],
        )

        for index, message in enumerate(
            messages["items"],
            start=1,
        ):

            print(
                f"\n  MESSAGE {index}"
            )

            print(
                f"  ROLE: "
                f"{message.get('role')}"
            )

            print(
                f"  CHARS: "
                f"{message.get('characters')}"
            )

            print(
                f"  TOKENS≈ "
                f"{message.get('estimated_tokens')}"
            )

            print(
                "  CONTENT:"
            )

            print(
                message.get(
                    "content",
                    "",
                )
            )

        print(
            "\n  TOOL DEFINITIONS:"
        )

        print(
            json.dumps(
                tools["definitions"],
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )


# ============================================================
# SUMMARY
# ============================================================

def build_summary() -> dict[str, Any]:

    llm_calls = TRACE[
        "llm_calls"
    ]

    retrieval = TRACE[
        "retrieval"
    ]

    context_request = TRACE[
        "context_request"
    ]

    summary = {
        "retrieval": {
            "provider_count": len(
                retrieval.get(
                    "providers",
                    {},
                )
            ),
            "global_result_count": len(
                retrieval.get(
                    "global_results",
                    [],
                )
            ),
            "global_summary": retrieval.get(
                "global_summary",
                {},
            ),
        },

        "context_request": {
            field: {
                "count": data.get(
                    "count"
                ),
                "characters": data.get(
                    "characters"
                ),
                "estimated_tokens": data.get(
                    "estimated_tokens"
                ),
            }
            for field, data in (
                context_request.items()
            )
        },

        "llm": {
            "call_count": len(
                llm_calls
            ),
            "calls": [
                {
                    "call_number": call[
                        "call_number"
                    ],
                    "message_count": call[
                        "messages"
                    ]["count"],
                    "message_characters": call[
                        "messages"
                    ]["characters"],
                    "message_estimated_tokens": call[
                        "messages"
                    ]["estimated_tokens"],
                    "tool_count": call[
                        "tools"
                    ]["count"],
                    "tool_estimated_tokens": call[
                        "tools"
                    ]["estimated_tokens"],
                }
                for call in llm_calls
            ],
        },
    }

    return summary


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print_header(
        "J.A.R.V.I.S. — TEST 2"
    )

    print(
        "RETRIEVAL → CONTEXT → LLM PIPELINE TRACE"
    )

    print()

    print_stat(
        "Input",
        TEST_INPUT,
    )

    print_stat(
        "Report",
        str(REPORT_FILE),
    )

    print()
    print(
        "Initializing JarvisAgent..."
    )

    try:

        agent = JarvisAgent()

        print(
            "Agent initialized."
        )

        # ----------------------------------------------------
        # Install all instrumentation BEFORE run().
        # ----------------------------------------------------

        instrument_retrieval(
            agent
        )

        instrument_diary(
            agent
        )

        instrument_compiler(
            agent
        )

        instrument_context_build(
            agent
        )

        instrument_window_manager(
            agent
        )

        instrument_llm(
            agent
        )

        # ----------------------------------------------------
        # REAL AGENT TURN
        # ----------------------------------------------------

        print()
        print(
            "Running REAL Agent turn..."
        )

        result = agent.run(
            TEST_INPUT
        )

        TRACE[
            "agent_result"
        ] = safe_json(
            result
        )

        print(
            "Agent turn completed."
        )

    except Exception as exc:

        TRACE[
            "errors"
        ].append(
            {
                "type": type(
                    exc
                ).__name__,
                "message": str(
                    exc
                ),
                "traceback": traceback.format_exc(),
            }
        )

        print()
        print(
            "!!! TEST ENCOUNTERED AN ERROR !!!"
        )

        print(
            traceback.format_exc()
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print_retrieval_report()

    print_diary_report()

    print_context_request_report()

    print_compiler_report()

    print_window_report()

    print_llm_report()

    print_header(
        "7. EXECUTIVE SUMMARY"
    )

    summary = build_summary()

    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    # --------------------------------------------------------
    # Save complete report
    # --------------------------------------------------------

    TRACE[
        "summary"
    ] = summary

    with REPORT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            TRACE,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print()
    print("=" * 80)

    print(
        f"FULL REPORT SAVED TO:"
    )

    print(
        REPORT_FILE.resolve()
    )

    print("=" * 80)


if __name__ == "__main__":
    main()