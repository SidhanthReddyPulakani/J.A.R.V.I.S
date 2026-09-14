"""
J.A.R.V.I.S.
TEST 3 — FULL CONTEXT LIFECYCLE / MULTI-STEP TRACE

Purpose
-------
Observe the COMPLETE context lifecycle during a real Agent execution.

This is the final diagnostic test before designing the new Context Manager.

We want to empirically establish:

    Context A
       ↓
      LLM #1
       ↓
    Tool Call
       ↓
    Capability Execution
       ↓
    Operation Result
       ↓
    Conversation Recording
       ↓
    Context B
       ↓
      LLM #2
       ↓
      ...

For every reasoning step we capture:

- Agent conversation before context construction
- Retrieval invocation/results
- Diary invocation/results
- ContextRequest fields
- ContextCompiler output
- ContextWindowManager input/output
- Exact LLM messages
- Exact tool definitions
- Tool calls
- Capability execution
- Operation results
- Conversation growth
- Context-to-context deltas
- Token estimates
- Duplicate/repeated messages
- Context hashes

IMPORTANT
---------
This test is observational only.

It does NOT modify production files.

It monkey-patches runtime objects only for the duration of
this process.

The test performs a real Agent execution.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from collections import Counter
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
# PROJECT IMPORT
# ============================================================

from jarvis.core.agent import JarvisAgent


# ============================================================
# CONFIG
# ============================================================

TEST_INPUT = "Open WhatsApp."

REPORT_FILE = Path(
    "test_context_lifecycle_report.json"
)

MAX_PREVIEW = 3000


# ============================================================
# GLOBAL TRACE
# ============================================================

TRACE: dict[str, Any] = {
    "metadata": {
        "test": (
            "TEST 3 — FULL CONTEXT LIFECYCLE / "
            "MULTI-STEP TRACE"
        ),
        "timestamp": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),
        "input": TEST_INPUT,
    },

    "steps": [],

    "retrieval_calls": [],

    "diary_calls": [],

    "context_requests": [],

    "compiled_contexts": [],

    "window_manager": [],

    "llm_calls": [],

    "tool_calls": [],

    "operation_results": [],

    "conversation_snapshots": [],

    "agent_result": None,

    "errors": [],
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def estimate_tokens(value: Any) -> int:
    text = serialize_text(value)

    if not text:
        return 0

    return max(
        1,
        len(text) // 4,
    )


def serialize(value: Any) -> Any:
    """
    Convert project objects to JSON-safe structures.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(value, dict):

        return {
            str(key): serialize(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return [
            serialize(item)
            for item in value
        ]

    if hasattr(
        value,
        "model_dump",
    ):

        try:
            return serialize(
                value.model_dump()
            )
        except Exception:
            pass

    if hasattr(
        value,
        "dict",
    ):

        try:
            return serialize(
                value.dict()
            )
        except Exception:
            pass

    if hasattr(
        value,
        "__dict__",
    ):

        try:
            return {
                str(key): serialize(item)
                for key, item in vars(
                    value
                ).items()
                if not key.startswith("_")
            }
        except Exception:
            pass

    return str(value)


def serialize_text(value: Any) -> str:

    if value is None:
        return ""

    if isinstance(
        value,
        str,
    ):
        return value

    try:
        return json.dumps(
            serialize(value),
            ensure_ascii=False,
            default=str,
        )
    except Exception:

        return str(value)


def sha256(value: Any) -> str:

    text = serialize_text(value)

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def summarize(value: Any) -> dict[str, Any]:

    serialized = serialize(value)
    text = serialize_text(
        serialized
    )

    if value is None:
        count = 0

    elif isinstance(
        value,
        (
            list,
            tuple,
            dict,
            set,
        ),
    ):
        count = len(value)

    else:
        count = 1

    return {
        "count": count,
        "characters": len(text),
        "estimated_tokens": estimate_tokens(
            text
        ),
        "sha256": sha256(text),
        "data": serialized,
    }


def summarize_message(
    message: Any,
) -> dict[str, Any]:

    data = serialize(message)

    if isinstance(
        data,
        dict,
    ):

        content = data.get(
            "content",
            "",
        )

        if content is None:
            content = ""

        return {
            "role": data.get(
                "role"
            ),
            "content": content,
            "characters": len(
                str(content)
            ),
            "estimated_tokens": (
                estimate_tokens(
                    content
                )
            ),
            "sha256": sha256(
                data
            ),
            "all_fields": data,
        }

    text = serialize_text(data)

    return {
        "role": None,
        "content": text,
        "characters": len(text),
        "estimated_tokens": estimate_tokens(
            text
        ),
        "sha256": sha256(data),
        "all_fields": data,
    }


def summarize_messages(
    messages: Any,
) -> dict[str, Any]:

    messages = (
        messages
        if messages is not None
        else []
    )

    normalized = [
        summarize_message(
            message
        )
        for message in messages
    ]

    return {
        "count": len(normalized),
        "characters": sum(
            item["characters"]
            for item in normalized
        ),
        "estimated_tokens": sum(
            item["estimated_tokens"]
            for item in normalized
        ),
        "messages": normalized,
    }


def summarize_retrieval_result(
    result: Any,
) -> dict[str, Any]:

    data = serialize(result)

    if isinstance(
        data,
        dict,
    ):

        content = data.get(
            "content",
            "",
        )

        return {
            "source": data.get(
                "source"
            ),
            "identifier": data.get(
                "identifier"
            ),
            "score": data.get(
                "score"
            ),
            "content": content,
            "characters": len(
                str(content)
            ),
            "estimated_tokens": (
                estimate_tokens(
                    content
                )
            ),
            "metadata": data.get(
                "metadata"
            ),
            "all_fields": data,
        }

    text = serialize_text(data)

    return {
        "source": None,
        "identifier": None,
        "score": None,
        "content": text,
        "characters": len(text),
        "estimated_tokens": estimate_tokens(
            text
        ),
        "metadata": None,
        "all_fields": data,
    }


# ============================================================
# CONTEXT DIFFERENCE
# ============================================================

def compare_message_lists(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
) -> dict[str, Any]:

    previous_hashes = [
        item["sha256"]
        for item in previous
    ]

    current_hashes = [
        item["sha256"]
        for item in current
    ]

    previous_counter = Counter(
        previous_hashes
    )

    current_counter = Counter(
        current_hashes
    )

    new_hashes = []

    for item in current_hashes:

        if previous_counter[item] > 0:
            previous_counter[item] -= 1

        else:
            new_hashes.append(item)

    removed_hashes = []

    remaining_current = Counter(
        current_hashes
    )

    for item in previous_hashes:

        if remaining_current[item] > 0:
            remaining_current[item] -= 1

        else:
            removed_hashes.append(item)

    repeated = sum(
        min(
            Counter(
                previous_hashes
            )[key],
            Counter(
                current_hashes
            )[key],
        )
        for key in set(
            previous_hashes
            + current_hashes
        )
    )

    previous_tokens = sum(
        item["estimated_tokens"]
        for item in previous
    )

    current_tokens = sum(
        item["estimated_tokens"]
        for item in current
    )

    return {
        "previous_message_count": len(
            previous
        ),
        "current_message_count": len(
            current
        ),

        "previous_tokens": previous_tokens,
        "current_tokens": current_tokens,

        "token_delta": (
            current_tokens
            - previous_tokens
        ),

        "new_message_count": len(
            new_hashes
        ),

        "removed_message_count": len(
            removed_hashes
        ),

        "repeated_message_count": repeated,

        "new_tokens": sum(
            item["estimated_tokens"]
            for item in current
            if item["sha256"]
            in new_hashes
        ),

        "new_message_hashes": new_hashes,

        "removed_message_hashes": (
            removed_hashes
        ),
    }


# ============================================================
# STEP MANAGEMENT
# ============================================================

CURRENT_STEP = {
    "value": None
}


def ensure_step(
    step_number: int,
) -> dict[str, Any]:

    while len(
        TRACE["steps"]
    ) < step_number:

        TRACE["steps"].append(
            {
                "step": len(
                    TRACE["steps"]
                ),
            }
        )

    step = TRACE[
        "steps"
    ][step_number]

    step["step"] = step_number

    return step


# ============================================================
# AGENT CONVERSATION SNAPSHOTS
# ============================================================

def snapshot_conversation(
    agent: JarvisAgent,
    label: str,
) -> None:

    messages = list(
        getattr(
            agent,
            "messages",
            [],
        )
        or []
    )

    summary = summarize_messages(
        messages
    )

    snapshot = {
        "label": label,
        "message_count": summary[
            "count"
        ],
        "characters": summary[
            "characters"
        ],
        "estimated_tokens": summary[
            "estimated_tokens"
        ],
        "sha256": sha256(
            messages
        ),
        "messages": summary[
            "messages"
        ],
    }

    TRACE[
        "conversation_snapshots"
    ].append(
        snapshot
    )


# ============================================================
# RETRIEVAL INSTRUMENTATION
# ============================================================

def instrument_retrieval(
    agent: JarvisAgent,
) -> None:

    retrieval = agent.retrieval

    # --------------------------------------------------------
    # Providers
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

        original_search = (
            provider.search
        )

        def make_provider_wrapper(
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
                    summarize_retrieval_result(
                        result
                    )
                    for result in (
                        results or []
                    )
                ]

                TRACE[
                    "retrieval_calls"
                ].append(
                    {
                        "step": CURRENT_STEP[
                            "value"
                        ],
                        "type": "provider",
                        "provider": name,
                        "query": query,
                        "limit": limit,
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
                )

                return results

            return wrapper

        provider.search = (
            make_provider_wrapper(
                original_search,
                provider_name,
            )
        )

    # --------------------------------------------------------
    # RetrievalService
    # --------------------------------------------------------

    original_search = retrieval.search

    def retrieval_wrapper(
        query,
        sources=None,
        limit=10,
        **kwargs,
    ):

        results = original_search(
            query,
            sources=sources,
            limit=limit,
            **kwargs,
        )

        normalized = [
            summarize_retrieval_result(
                result
            )
            for result in (
                results or []
            )
        ]

        TRACE[
            "retrieval_calls"
        ].append(
            {
                "step": CURRENT_STEP[
                    "value"
                ],
                "type": "retrieval_service",
                "query": query,
                "sources": sources,
                "limit": limit,
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
        )

        return results

    retrieval.search = (
        retrieval_wrapper
    )


# ============================================================
# DIARY INSTRUMENTATION
# ============================================================

def instrument_diary(
    agent: JarvisAgent,
) -> None:

    diary = agent.diary

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if hasattr(
        diary,
        "search",
    ):

        original_search = diary.search

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

            data = serialize(
                results or []
            )

            TRACE[
                "diary_calls"
            ].append(
                {
                    "step": CURRENT_STEP[
                        "value"
                    ],
                    "type": "search",
                    "query": query,
                    "conversation_id": (
                        conversation_id
                    ),
                    "limit": limit,
                    "summary": summarize(
                        data
                    ),
                }
            )

            return results

        diary.search = (
            search_wrapper
        )

    # --------------------------------------------------------
    # Recent
    # --------------------------------------------------------

    if hasattr(
        diary,
        "recent",
    ):

        original_recent = diary.recent

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

            data = serialize(
                results or []
            )

            TRACE[
                "diary_calls"
            ].append(
                {
                    "step": CURRENT_STEP[
                        "value"
                    ],
                    "type": "recent",
                    "conversation_id": (
                        conversation_id
                    ),
                    "limit": limit,
                    "summary": summarize(
                        data
                    ),
                }
            )

            return results

        diary.recent = (
            recent_wrapper
        )


# ============================================================
# CONTEXT REQUEST INSTRUMENTATION
# ============================================================

def instrument_context(
    agent: JarvisAgent,
) -> None:

    compiler = (
        agent.context_compiler
    )

    original_compile = (
        compiler.compile
    )

    def compile_wrapper(
        request,
    ):

        request_data = {}

        fields = [
            "user_input",
            "state",
            "conversation",
            "core_memory",
            "memories",
            "diary",
            "knowledge",
            "relationships",
            "capability_information",
            "operation_results",
            "retrieval_results",
        ]

        for field in fields:

            if hasattr(
                request,
                field,
            ):

                request_data[
                    field
                ] = summarize(
                    getattr(
                        request,
                        field,
                    )
                )

        TRACE[
            "context_requests"
        ].append(
            {
                "step": CURRENT_STEP[
                    "value"
                ],
                "fields": request_data,
            }
        )

        output = original_compile(
            request
        )

        messages = getattr(
            output,
            "messages",
            [],
        ) or []

        summary = summarize_messages(
            messages
        )

        TRACE[
            "compiled_contexts"
        ].append(
            {
                "step": CURRENT_STEP[
                    "value"
                ],
                **summary,
            }
        )

        return output

    compiler.compile = (
        compile_wrapper
    )


# ============================================================
# WINDOW MANAGER
# ============================================================

def instrument_window_manager(
    agent: JarvisAgent,
) -> None:

    manager = (
        agent.context_window
    )

    # --------------------------------------------------------
    # Retrieval budget
    # --------------------------------------------------------

    if hasattr(
        manager,
        "fit_retrieval_budget",
    ):

        original_fit = (
            manager.fit_retrieval_budget
        )

        def fit_wrapper(
            results,
            *args,
            **kwargs,
        ):

            before = [
                summarize_retrieval_result(
                    result
                )
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
                summarize_retrieval_result(
                    result
                )
                for result in (
                    output or []
                )
            ]

            TRACE[
                "window_manager"
            ].append(
                {
                    "step": CURRENT_STEP[
                        "value"
                    ],
                    "operation": (
                        "fit_retrieval_budget"
                    ),

                    "before": {
                        "count": len(before),
                        "tokens": sum(
                            item[
                                "estimated_tokens"
                            ]
                            for item in before
                        ),
                    },

                    "after": {
                        "count": len(after),
                        "tokens": sum(
                            item[
                                "estimated_tokens"
                            ]
                            for item in after
                        ),
                    },

                    "removed": (
                        len(before)
                        - len(after)
                    ),
                }
            )

            return output

        manager.fit_retrieval_budget = (
            fit_wrapper
        )

    # --------------------------------------------------------
    # Prepare
    # --------------------------------------------------------

    if hasattr(
        manager,
        "prepare",
    ):

        original_prepare = (
            manager.prepare
        )

        def prepare_wrapper(
            context,
            *args,
            **kwargs,
        ):

            before = summarize_messages(
                getattr(
                    context,
                    "messages",
                    [],
                )
                or []
            )

            output = original_prepare(
                context,
                *args,
                **kwargs,
            )

            after = summarize_messages(
                getattr(
                    output,
                    "messages",
                    [],
                )
                or []
            )

            TRACE[
                "window_manager"
            ].append(
                {
                    "step": CURRENT_STEP[
                        "value"
                    ],
                    "operation": "prepare",

                    "before": before,

                    "after": after,

                    "message_delta": (
                        after["count"]
                        - before["count"]
                    ),

                    "token_delta": (
                        after[
                            "estimated_tokens"
                        ]
                        - before[
                            "estimated_tokens"
                        ]
                    ),

                    "messages_removed": max(
                        0,
                        before["count"]
                        - after["count"],
                    ),
                }
            )

            return output

        manager.prepare = (
            prepare_wrapper
        )


# ============================================================
# LLM CLIENT
# ============================================================

def instrument_llm(
    agent: JarvisAgent,
) -> None:

    llm = agent.llm

    original_chat = llm.chat

    def chat_wrapper(
        messages,
        tools=None,
        *args,
        **kwargs,
    ):

        message_summary = (
            summarize_messages(
                messages or []
            )
        )

        tool_data = serialize(
            tools or []
        )

        tool_text = serialize_text(
            tool_data
        )

        call_number = (
            len(
                TRACE["llm_calls"]
            )
            + 1
        )

        TRACE[
            "llm_calls"
        ].append(
            {
                "call_number": call_number,
                "step": CURRENT_STEP[
                    "value"
                ],

                "messages": message_summary,

                "tools": {
                    "count": (
                        len(tool_data)
                        if isinstance(
                            tool_data,
                            list,
                        )
                        else (
                            0
                            if not tool_data
                            else 1
                        )
                    ),
                    "characters": len(
                        tool_text
                    ),
                    "estimated_tokens": (
                        estimate_tokens(
                            tool_text
                        )
                    ),
                    "definitions": tool_data,
                },
            }
        )

        result = original_chat(
            messages,
            tools=tools,
            *args,
            **kwargs,
        )

        # ----------------------------------------------------
        # Capture model response / tool calls
        # ----------------------------------------------------

        response_data = serialize(
            result
        )

        TRACE[
            "llm_calls"
        ][-1][
            "response"
        ] = response_data

        # Try common tool-call locations.
        tool_calls = []

        if isinstance(
            response_data,
            dict,
        ):

            tool_calls = (
                response_data.get(
                    "tool_calls"
                )
                or []
            )

            if not tool_calls:

                message = (
                    response_data.get(
                        "message"
                    )
                )

                if isinstance(
                    message,
                    dict,
                ):

                    tool_calls = (
                        message.get(
                            "tool_calls"
                        )
                        or []
                    )

        TRACE[
            "llm_calls"
        ][-1][
            "detected_tool_calls"
        ] = serialize(
            tool_calls
        )

        return result

    llm.chat = (
        chat_wrapper
    )


# ============================================================
# CAPABILITY EXECUTION
# ============================================================

def instrument_capability_execution(
    agent: JarvisAgent,
) -> None:

    method_names = [
        "_execute_capability_request",
        "_execute_capability",
    ]

    for method_name in method_names:

        if not hasattr(
            agent,
            method_name,
        ):
            continue

        original = getattr(
            agent,
            method_name,
        )

        def make_wrapper(
            original_method,
            name,
        ):

            def wrapper(
                *args,
                **kwargs,
            ):

                record = {
                    "step": CURRENT_STEP[
                        "value"
                    ],
                    "method": name,
                    "arguments": serialize(
                        args
                    ),
                    "keyword_arguments": (
                        serialize(
                            kwargs
                        )
                    ),
                }

                try:

                    result = original_method(
                        *args,
                        **kwargs,
                    )

                    record[
                        "result"
                    ] = serialize(
                        result
                    )

                    TRACE[
                        "operation_results"
                    ].append(
                        record
                    )

                    return result

                except Exception as exc:

                    record[
                        "error"
                    ] = {
                        "type": type(
                            exc
                        ).__name__,
                        "message": str(
                            exc
                        ),
                    }

                    TRACE[
                        "operation_results"
                    ].append(
                        record
                    )

                    raise

            return wrapper

        setattr(
            agent,
            method_name,
            make_wrapper(
                original,
                method_name,
            ),
        )


# ============================================================
# AGENT RUN INSTRUMENTATION
# ============================================================

def instrument_agent_run(
    agent: JarvisAgent,
) -> None:

    original_run = agent.run

    def run_wrapper(
        *args,
        **kwargs,
    ):

        # Initial state.
        snapshot_conversation(
            agent,
            "before_agent_run",
        )

        result = original_run(
            *args,
            **kwargs,
        )

        snapshot_conversation(
            agent,
            "after_agent_run",
        )

        return result

    agent.run = (
        run_wrapper
    )


# ============================================================
# ASSIGN LLM CALLS TO STEPS
# ============================================================

def infer_step_boundaries() -> None:

    """
    We don't assume that the Agent's internal step number is
    exposed by every version of the code.

    Instead we correlate:
    - context builds
    - LLM calls
    - retrieval calls
    - operation calls

    using chronological order.

    The raw traces remain untouched.
    """

    llm_calls = TRACE[
        "llm_calls"
    ]

    for index, call in enumerate(
        llm_calls
    ):

        if call.get(
            "step"
        ) is None:

            call[
                "step"
            ] = index


# ============================================================
# BUILD LIFECYCLE SUMMARY
# ============================================================

def build_summary() -> dict[str, Any]:

    llm_calls = TRACE[
        "llm_calls"
    ]

    contexts = TRACE[
        "compiled_contexts"
    ]

    summary = {
        "llm_call_count": len(
            llm_calls
        ),

        "context_build_count": len(
            contexts
        ),

        "retrieval_call_count": len(
            TRACE[
                "retrieval_calls"
            ]
        ),

        "diary_call_count": len(
            TRACE[
                "diary_calls"
            ]
        ),

        "operation_count": len(
            TRACE[
                "operation_results"
            ]
        ),

        "conversation_snapshot_count": len(
            TRACE[
                "conversation_snapshots"
            ]
        ),

        "llm_calls": [],

        "context_growth": [],
    }

    for call in llm_calls:

        messages = call[
            "messages"
        ]

        summary[
            "llm_calls"
        ].append(
            {
                "call_number": call[
                    "call_number"
                ],
                "step": call.get(
                    "step"
                ),
                "message_count": messages[
                    "count"
                ],
                "characters": messages[
                    "characters"
                ],
                "estimated_tokens": messages[
                    "estimated_tokens"
                ],
                "tool_count": call[
                    "tools"
                ]["count"],
                "tool_estimated_tokens": call[
                    "tools"
                ]["estimated_tokens"],
                "detected_tool_call_count": len(
                    call.get(
                        "detected_tool_calls",
                        [],
                    )
                    or []
                ),
            }
        )

    previous = None

    for index, context in enumerate(
        contexts
    ):

        current_messages = context[
            "messages"
        ]

        entry = {
            "context_index": index,
            "step": context.get(
                "step"
            ),
            "message_count": context[
                "count"
            ],
            "estimated_tokens": context[
                "estimated_tokens"
            ],
        }

        if previous is not None:

            comparison = (
                compare_message_lists(
                    previous[
                        "messages"
                    ],
                    current_messages,
                )
            )

            entry[
                "delta_from_previous"
            ] = comparison

        summary[
            "context_growth"
        ].append(
            entry
        )

        previous = context

    return summary


# ============================================================
# PRINTING
# ============================================================

def header(
    title: str,
) -> None:

    print()
    print("=" * 90)
    print(title)
    print("=" * 90)


def subheader(
    title: str,
) -> None:

    print()
    print("-" * 90)
    print(title)
    print("-" * 90)


def print_retrieval() -> None:

    header(
        "1. RETRIEVAL LIFECYCLE"
    )

    calls = TRACE[
        "retrieval_calls"
    ]

    if not calls:

        print(
            "No retrieval calls captured."
        )
        return

    for index, call in enumerate(
        calls,
        start=1,
    ):

        print(
            f"\nCALL #{index}"
        )

        print(
            f"  Step       : "
            f"{call.get('step')}"
        )

        print(
            f"  Type       : "
            f"{call.get('type')}"
        )

        print(
            f"  Provider   : "
            f"{call.get('provider')}"
        )

        print(
            f"  Query      : "
            f"{call.get('query')}"
        )

        print(
            f"  Results    : "
            f"{call.get('result_count')}"
        )

        print(
            f"  Tokens ≈   : "
            f"{call.get('estimated_tokens')}"
        )

        for result_index, result in enumerate(
            call.get(
                "results",
                [],
            ),
            start=1,
        ):

            content = str(
                result.get(
                    "content",
                    "",
                )
            )

            if len(content) > MAX_PREVIEW:

                content = (
                    content[
                        :MAX_PREVIEW
                    ]
                    + "..."
                )

            print(
                f"\n    [{result_index}] "
                f"{result.get('source')} "
                f"score={result.get('score')}"
            )

            print(
                f"        {content}"
            )


def print_context_requests() -> None:

    header(
        "2. CONTEXT REQUESTS"
    )

    for index, request in enumerate(
        TRACE[
            "context_requests"
        ],
        start=1,
    ):

        print(
            f"\nCONTEXT REQUEST #{index}"
        )

        print(
            f"  Step: "
            f"{request.get('step')}"
        )

        for field, data in (
            request[
                "fields"
            ].items()
        ):

            print(
                f"\n  {field}"
            )

            print(
                f"    count   : "
                f"{data.get('count')}"
            )

            print(
                f"    chars   : "
                f"{data.get('characters')}"
            )

            print(
                f"    tokens ≈: "
                f"{data.get('estimated_tokens')}"
            )


def print_compiled_context() -> None:

    header(
        "3. COMPILED CONTEXT"
    )

    for index, context in enumerate(
        TRACE[
            "compiled_contexts"
        ],
        start=1,
    ):

        print(
            f"\nCONTEXT #{index}"
        )

        print(
            f"  Step      : "
            f"{context.get('step')}"
        )

        print(
            f"  Messages  : "
            f"{context.get('count')}"
        )

        print(
            f"  Characters: "
            f"{context.get('characters')}"
        )

        print(
            f"  Tokens ≈  : "
            f"{context.get('estimated_tokens')}"
        )


def print_window_manager() -> None:

    header(
        "4. CONTEXT WINDOW MANAGER"
    )

    for index, event in enumerate(
        TRACE[
            "window_manager"
        ],
        start=1,
    ):

        print(
            f"\nEVENT #{index}"
        )

        print(
            f"  Step      : "
            f"{event.get('step')}"
        )

        print(
            f"  Operation : "
            f"{event.get('operation')}"
        )

        if event.get(
            "operation"
        ) == "prepare":

            before = event[
                "before"
            ]

            after = event[
                "after"
            ]

            print(
                f"  Before    : "
                f"{before['count']} messages / "
                f"{before['estimated_tokens']} tokens"
            )

            print(
                f"  After     : "
                f"{after['count']} messages / "
                f"{after['estimated_tokens']} tokens"
            )

            print(
                f"  Removed   : "
                f"{event.get('messages_removed')}"
            )

        else:

            print(
                f"  Before    : "
                f"{event['before']['count']} results / "
                f"{event['before']['tokens']} tokens"
            )

            print(
                f"  After     : "
                f"{event['after']['count']} results / "
                f"{event['after']['tokens']} tokens"
            )

            print(
                f"  Removed   : "
                f"{event.get('removed')}"
            )


def print_llm() -> None:

    header(
        "5. EXACT LLM CALLS"
    )

    for call in TRACE[
        "llm_calls"
    ]:

        messages = call[
            "messages"
        ]

        tools = call[
            "tools"
        ]

        print(
            f"\nLLM CALL #{call['call_number']}"
        )

        print(
            f"  Step             : "
            f"{call.get('step')}"
        )

        print(
            f"  Messages         : "
            f"{messages['count']}"
        )

        print(
            f"  Message tokens ≈ : "
            f"{messages['estimated_tokens']}"
        )

        print(
            f"  Tools            : "
            f"{tools['count']}"
        )

        print(
            f"  Tool tokens ≈    : "
            f"{tools['estimated_tokens']}"
        )

        print(
            f"  Tool calls found : "
            f"{len(call.get('detected_tool_calls', []) or [])}"
        )

        for index, message in enumerate(
            messages[
                "messages"
            ],
            start=1,
        ):

            print(
                f"\n    MESSAGE {index}"
            )

            print(
                f"      role  : "
                f"{message.get('role')}"
            )

            print(
                f"      chars : "
                f"{message.get('characters')}"
            )

            print(
                f"      tokens: "
                f"{message.get('estimated_tokens')}"
            )

            content = str(
                message.get(
                    "content",
                    "",
                )
            )

            if len(content) > MAX_PREVIEW:

                content = (
                    content[
                        :MAX_PREVIEW
                    ]
                    + "\n        ...[TRUNCATED]..."
                )

            print(
                f"      content:\n"
                f"{content}"
            )


def print_operations() -> None:

    header(
        "6. CAPABILITY / OPERATION EXECUTION"
    )

    if not TRACE[
        "operation_results"
    ]:

        print(
            "No capability execution captured."
        )
        return

    for index, operation in enumerate(
        TRACE[
            "operation_results"
        ],
        start=1,
    ):

        print(
            f"\nOPERATION #{index}"
        )

        print(
            f"  Step   : "
            f"{operation.get('step')}"
        )

        print(
            f"  Method : "
            f"{operation.get('method')}"
        )

        print(
            "  Result:"
        )

        print(
            json.dumps(
                operation.get(
                    "result"
                ),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )


def print_context_deltas() -> None:

    header(
        "7. CONTEXT-TO-CONTEXT DELTA"
    )

    contexts = TRACE[
        "compiled_contexts"
    ]

    if len(contexts) < 2:

        print(
            "Fewer than two compiled contexts "
            "were captured."
        )

        return

    previous = None

    for index, context in enumerate(
        contexts
    ):

        if previous is not None:

            comparison = (
                compare_message_lists(
                    previous[
                        "messages"
                    ],
                    context[
                        "messages"
                    ],
                )
            )

            print(
                f"\nCONTEXT {index - 1}"
                f" → CONTEXT {index}"
            )

            print(
                f"  Previous messages : "
                f"{comparison['previous_message_count']}"
            )

            print(
                f"  Current messages  : "
                f"{comparison['current_message_count']}"
            )

            print(
                f"  Previous tokens   : "
                f"{comparison['previous_tokens']}"
            )

            print(
                f"  Current tokens    : "
                f"{comparison['current_tokens']}"
            )

            print(
                f"  Token delta       : "
                f"{comparison['token_delta']:+}"
            )

            print(
                f"  New messages      : "
                f"{comparison['new_message_count']}"
            )

            print(
                f"  Removed messages  : "
                f"{comparison['removed_message_count']}"
            )

            print(
                f"  Repeated messages : "
                f"{comparison['repeated_message_count']}"
            )

            print(
                f"  New tokens ≈      : "
                f"{comparison['new_tokens']}"
            )

        previous = context


def print_final_summary() -> None:

    header(
        "8. FINAL LIFECYCLE SUMMARY"
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


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    header(
        "J.A.R.V.I.S. — TEST 3"
    )

    print(
        "FULL CONTEXT LIFECYCLE / MULTI-STEP TRACE"
    )

    print()

    print(
        f"Input : {TEST_INPUT}"
    )

    print(
        f"Report: {REPORT_FILE}"
    )

    try:

        print(
            "\nInitializing JarvisAgent..."
        )

        agent = JarvisAgent()

        print(
            "Agent initialized."
        )

        # ----------------------------------------------------
        # Install instrumentation.
        # ----------------------------------------------------

        instrument_retrieval(
            agent
        )

        instrument_diary(
            agent
        )

        instrument_context(
            agent
        )

        instrument_window_manager(
            agent
        )

        instrument_llm(
            agent
        )

        instrument_capability_execution(
            agent
        )

        instrument_agent_run(
            agent
        )

        # ----------------------------------------------------
        # Run.
        # ----------------------------------------------------

        print(
            "\nRunning REAL Agent turn..."
        )

        result = agent.run(
            TEST_INPUT
        )

        TRACE[
            "agent_result"
        ] = serialize(
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
            "!!! TEST ERROR !!!"
        )

        print(
            traceback.format_exc()
        )

    # --------------------------------------------------------
    # Normalize step assignment.
    # --------------------------------------------------------

    infer_step_boundaries()

    # --------------------------------------------------------
    # Print report.
    # --------------------------------------------------------

    print_retrieval()

    print_context_requests()

    print_compiled_context()

    print_window_manager()

    print_llm()

    print_operations()

    print_context_deltas()

    print_final_summary()

    # --------------------------------------------------------
    # Save complete JSON.
    # --------------------------------------------------------

    TRACE[
        "summary"
    ] = build_summary()

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

    print("=" * 90)

    print(
        "COMPLETE REPORT SAVED"
    )

    print(
        REPORT_FILE.resolve()
    )

    print("=" * 90)


if __name__ == "__main__":
    main()