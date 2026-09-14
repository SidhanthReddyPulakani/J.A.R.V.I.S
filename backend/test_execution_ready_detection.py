"""
JARVIS Speed Experiment
Phase 1.1F-A — Execution-Ready Decision Detection

Purpose:
    Determine how early Qwen produces a concrete, executable tool decision
    during reasoning, and how long it takes before Ollama emits the actual
    structured tool call.

IMPORTANT:
    Diagnostic only.
    This file must NOT modify production Agent/LLM behavior.

Experiments:
    1. Open WhatsApp.
    2. Open the messaging app.
    3. Find WhatsApp, then open it.
    4. Find applications matching the name WhatsApp, then report whether
       the result count is exactly one, more than one, or zero.

We distinguish:

    INCOMPLETE CANDIDATE
        apps.find(?)

    CONCRETE CANDIDATE
        apps.find(WhatsApp)

    EXECUTION-READY
        A concrete candidate that represents a valid next tool action.

    ACTUAL TOOL CALL
        The structured tool call emitted by Ollama.

The experiment measures the gap between execution-ready and actual tool
emission. That gap is the potential latency available for optimization.

This test deliberately uses:
    - real JarvisAgent context
    - real JARVIS tool definitions
    - direct Ollama streaming

It does NOT modify production JARVIS behavior.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Any

from ollama import Client

from jarvis.core.agent import JarvisAgent
from jarvis.core.config import Settings


# ---------------------------------------------------------------------------
# Windows UTF-8 console compatibility
# ---------------------------------------------------------------------------

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RUNS_PER_TASK = 5

TEST_TASKS = [
    (
        "simple",
        "Open WhatsApp.",
    ),
    (
        "ambiguous",
        "Open the messaging app.",
    ),
    (
        "multi_step",
        "Find WhatsApp, then open it.",
    ),
    (
        "evidence",
        (
            "Find applications matching the name WhatsApp, then tell me "
            "whether the search returned exactly one match, more than one "
            "match, or no matches."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Candidate representation
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    operation: str
    argument: str
    first_seen_time: float
    first_seen_chars: int
    last_seen_chars: int
    occurrences: int = 1

    @property
    def signature(self) -> str:
        return f"{self.operation}({self.argument})"


@dataclass
class RunResult:
    task_name: str
    task: str

    first_candidate_time: float | None
    execution_ready_time: float | None
    actual_tool_time: float | None

    first_candidate: str | None
    execution_ready_candidate: str | None
    actual_tool: str | None

    candidate_to_tool_gap: float | None
    execution_ready_to_tool_gap: float | None

    persistence_chars: int
    contradiction_count: int

    tool_call_correct: bool

    stream_valid: bool
    stream_chunks: int
    thinking_chars: int
    content_chars: int
    prompt_eval_count: int | None
    eval_count: int | None
    done_reason: str | None


# ---------------------------------------------------------------------------
# Generic Ollama object access
# ---------------------------------------------------------------------------

def _get_field(
    obj: Any,
    field: str,
    default: Any = None,
) -> Any:
    """
    Read a field from:
        - dictionaries
        - Ollama SDK objects
        - Pydantic-like objects

    This keeps the diagnostic tolerant of Ollama SDK representation
    differences.
    """

    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(field, default)

    value = getattr(obj, field, None)

    if value is not None:
        return value

    model_dump = getattr(obj, "model_dump", None)

    if callable(model_dump):
        try:
            data = model_dump()

            if isinstance(data, dict):
                return data.get(field, default)

        except Exception:
            pass

    return default


# ---------------------------------------------------------------------------
# Candidate extraction
# ---------------------------------------------------------------------------

TOOL_PATTERNS = [
    re.compile(
        r"(?:apps\.)?(find)\s*"
        r"\(\s*['\"]?([^'\"\)\n]+?)['\"]?\s*\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:apps\.)?(launch)\s*"
        r"\(\s*['\"]?([^'\"\)\n]+?)['\"]?\s*\)",
        re.IGNORECASE,
    ),
]

JSON_TOOL_PATTERN = re.compile(
    r"""
    ["']?(apps\.(?:find|launch))["']?
    \s*
    [(:]
    .*?
    ["']query["']
    \s*[:=]
    \s*
    ["']([^"']+)["']
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def normalize_argument(argument: str) -> str:
    argument = argument.strip()
    argument = argument.strip("'\"")
    argument = re.sub(r"\s+", " ", argument)

    return argument


def extract_candidates(
    text: str,
) -> list[tuple[str, str]]:
    """
    Extract concrete operation + argument candidates.

    Deliberately ignores:

        apps.find(?)
        apps.find()
        apps.launch(?)

    because those are not execution-ready decisions.
    """

    candidates: list[tuple[str, str]] = []

    for pattern in TOOL_PATTERNS:

        for match in pattern.finditer(text):

            operation = match.group(1).lower()

            argument = normalize_argument(
                match.group(2)
            )

            if not argument:
                continue

            if argument.lower() in {
                "?",
                "unknown",
                "the app",
                "application",
            }:
                continue

            candidates.append(
                (
                    f"apps.{operation}",
                    argument,
                )
            )

    for match in JSON_TOOL_PATTERN.finditer(text):

        operation = match.group(1).lower()

        argument = normalize_argument(
            match.group(2)
        )

        if argument:
            candidates.append(
                (
                    operation,
                    argument,
                )
            )

    # Preserve first occurrence while removing duplicates.
    seen: set[tuple[str, str]] = set()

    unique: list[tuple[str, str]] = []

    for candidate in candidates:

        if candidate in seen:
            continue

        seen.add(candidate)
        unique.append(candidate)

    return unique


# ---------------------------------------------------------------------------
# Task-aware execution readiness
# ---------------------------------------------------------------------------

def is_execution_ready(
    operation: str,
    argument: str,
    task_name: str,
) -> bool:
    """
    Determine whether a concrete candidate represents the valid
    NEXT execution step.

    This evaluates STEP readiness, not TASK completion.

    Examples:

        simple:
            apps.launch(WhatsApp) -> ready

        ambiguous:
            apps.find(messaging) -> ready

        multi_step:
            apps.find(WhatsApp) -> ready

        evidence:
            apps.find(WhatsApp) -> ready
    """

    if operation not in {
        "apps.find",
        "apps.launch",
    }:
        return False

    if not argument.strip():
        return False

    if argument.strip().lower() in {
        "?",
        "unknown",
    }:
        return False

    expected_first_operations = {
        "simple": "apps.launch",
        "ambiguous": "apps.find",
        "multi_step": "apps.find",
        "evidence": "apps.find",
    }

    expected = expected_first_operations.get(
        task_name
    )

    if expected is None:
        return False

    return operation == expected


# ---------------------------------------------------------------------------
# Structured tool-call extraction
# ---------------------------------------------------------------------------

def extract_structured_tool_calls(
    response: Any,
) -> list[dict[str, Any]]:
    """
    Extract structured tool calls from one streamed Ollama response chunk.
    """

    message = _get_field(
        response,
        "message",
    )

    if message is None:
        return []

    raw_calls = _get_field(
        message,
        "tool_calls",
    )

    if not raw_calls:
        return []

    calls: list[dict[str, Any]] = []

    for call in raw_calls:

        function = _get_field(
            call,
            "function",
        )

        if function is None:
            continue

        name = _get_field(
            function,
            "name",
        )

        arguments = _get_field(
            function,
            "arguments",
        )

        if isinstance(arguments, str):

            try:
                arguments = json.loads(
                    arguments
                )

            except Exception:
                pass

        calls.append(
            {
                "name": name,
                "arguments": arguments,
            }
        )

    return calls


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def build_context(
    agent: JarvisAgent,
    user_input: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Use the real JARVIS context and real registered tools.

    No production behavior is changed.
    """

    context = agent._build_context(
        user_input=user_input
    )

    tools = agent._get_llm_tools()

    return (
        context.as_messages(),
        tools,
    )


# ---------------------------------------------------------------------------
# Raw chunk diagnostic
# ---------------------------------------------------------------------------

def dump_chunk(
    chunk: Any,
    label: str,
) -> None:
    """
    Print one raw Ollama chunk in a representation-independent way.
    """

    print()
    print(f"[{label}]")
    print(
        f"type: {type(chunk)!r}"
    )

    try:

        if hasattr(chunk, "model_dump"):

            print(
                json.dumps(
                    chunk.model_dump(),
                    ensure_ascii=False,
                    default=str,
                    indent=2,
                )
            )

        elif isinstance(chunk, dict):

            print(
                json.dumps(
                    chunk,
                    ensure_ascii=False,
                    default=str,
                    indent=2,
                )
            )

        else:

            print(
                repr(chunk)
            )

    except Exception as exc:

        print(
            f"chunk dump failed: "
            f"{type(exc).__name__}: {exc}"
        )

    print(
        f"[END {label}]"
    )
    print()


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_once(
    client: Client,
    agent: JarvisAgent,
    task_name: str,
    task: str,
    settings: Settings,
) -> RunResult:

    messages, tools = build_context(
        agent,
        task,
    )

    print()
    print(
        f"[CONTEXT] messages={len(messages)} "
        f"tools={len(tools)}"
    )

    if not tools:

        raise RuntimeError(
            "JARVIS returned zero LLM tools. "
            "This diagnostic cannot continue."
        )

    started = time.perf_counter()

    stream = client.chat(
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        stream=True,
        think=True,
        keep_alive=settings.keep_alive,
        options={
            "num_ctx": settings.context_size,
        },
    )

    reasoning_text = ""
    content_text = ""

    first_candidate: Candidate | None = None
    ready_candidate: Candidate | None = None

    last_signature: str | None = None

    contradiction_count = 0

    actual_tool_time: float | None = None
    actual_tool: str | None = None

    total_chars = 0

    stream_chunks = 0

    thinking_chars = 0
    content_chars = 0

    prompt_eval_count: int | None = None
    eval_count: int | None = None
    done_reason: str | None = None

    first_chunk_dumped = False
    last_chunk: Any = None

    structured_call_count = 0

    for chunk in stream:

        stream_chunks += 1

        now = time.perf_counter()

        elapsed = (
            now - started
        )

        last_chunk = chunk

        # ---------------------------------------------------------------
        # First raw chunk
        # ---------------------------------------------------------------

        if not first_chunk_dumped:

            dump_chunk(
                chunk,
                "RAW OLLAMA FIRST CHUNK",
            )

            first_chunk_dumped = True

        # ---------------------------------------------------------------
        # Top-level Ollama metadata
        # ---------------------------------------------------------------

        chunk_prompt_eval = _get_field(
            chunk,
            "prompt_eval_count",
        )

        if chunk_prompt_eval is not None:

            prompt_eval_count = (
                chunk_prompt_eval
            )

        chunk_eval_count = _get_field(
            chunk,
            "eval_count",
        )

        if chunk_eval_count is not None:

            eval_count = (
                chunk_eval_count
            )

        chunk_done_reason = _get_field(
            chunk,
            "done_reason",
        )

        if chunk_done_reason is not None:

            done_reason = (
                str(chunk_done_reason)
            )

        # ---------------------------------------------------------------
        # Message
        # ---------------------------------------------------------------

        message = _get_field(
            chunk,
            "message",
        )

        if message is None:

            # Some SDK responses may expose message-like data directly.
            message = chunk

        thinking = _get_field(
            message,
            "thinking",
        )

        content = _get_field(
            message,
            "content",
        )

        if thinking:

            thinking_piece = str(
                thinking
            )

            reasoning_text += (
                thinking_piece
            )

            thinking_chars += len(
                thinking_piece
            )

            total_chars += len(
                thinking_piece
            )

        if content:

            content_piece = str(
                content
            )

            content_text += (
                content_piece
            )

            content_chars += len(
                content_piece
            )

            total_chars += len(
                content_piece
            )

        # ---------------------------------------------------------------
        # Candidate analysis
        # ---------------------------------------------------------------

        combined = (
            reasoning_text
            + "\n"
            + content_text
        )

        candidates = extract_candidates(
            combined
        )

        if candidates:

            # We inspect ALL discovered candidates rather than blindly
            # assuming candidates[0] is the current decision.
            for operation, argument in candidates:

                signature = (
                    f"{operation}({argument})"
                )

                # First concrete candidate.
                if first_candidate is None:

                    first_candidate = Candidate(
                        operation=operation,
                        argument=argument,
                        first_seen_time=elapsed,
                        first_seen_chars=total_chars,
                        last_seen_chars=total_chars,
                    )

                    last_signature = signature

                elif (
                    signature
                    != last_signature
                ):

                    contradiction_count += 1

                    last_signature = (
                        signature
                    )

                # -------------------------------------------------------
                # Execution-ready candidate
                # -------------------------------------------------------

                if not is_execution_ready(
                    operation,
                    argument,
                    task_name,
                ):
                    continue

                if ready_candidate is None:

                    ready_candidate = Candidate(
                        operation=operation,
                        argument=argument,
                        first_seen_time=elapsed,
                        first_seen_chars=total_chars,
                        last_seen_chars=total_chars,
                    )

                elif (
                    ready_candidate.signature
                    == signature
                ):

                    ready_candidate.last_seen_chars = (
                        total_chars
                    )

                    ready_candidate.occurrences += 1

                break

        # ---------------------------------------------------------------
        # Structured tool call
        # ---------------------------------------------------------------

        calls = extract_structured_tool_calls(
            chunk
        )

        if calls:

            structured_call_count += len(
                calls
            )

            if actual_tool_time is None:

                actual_tool_time = (
                    elapsed
                )

                first_call = calls[0]

                actual_tool = (
                    f"{first_call['name']}"
                    f"({first_call['arguments']})"
                )

    # -------------------------------------------------------------------
    # Final stream diagnostic
    # -------------------------------------------------------------------

    dump_chunk(
        last_chunk,
        "STREAM FINAL CHUNK",
    )

    # -------------------------------------------------------------------
    # Detect invalid/no-generation streams
    # -------------------------------------------------------------------

    stream_valid = bool(
        thinking_chars
        or content_chars
        or structured_call_count
        or eval_count not in {None, 0}
    )

    if not stream_valid:

        print()
        print(
            "[WARNING] Ollama produced no usable "
            "thinking, content, or structured tool output."
        )

        print(
            f"[WARNING] stream_chunks={stream_chunks}"
        )

        print(
            f"[WARNING] prompt_eval_count="
            f"{prompt_eval_count}"
        )

        print(
            f"[WARNING] eval_count="
            f"{eval_count}"
        )

        print(
            f"[WARNING] done_reason="
            f"{done_reason}"
        )

        print(
            "[WARNING] This run is INVALID for "
            "execution-readiness measurement."
        )

    # -------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------

    first_candidate_time = (
        first_candidate.first_seen_time
        if first_candidate
        else None
    )

    execution_ready_time = (
        ready_candidate.first_seen_time
        if ready_candidate
        else None
    )

    candidate_to_tool_gap = None

    if (
        first_candidate_time is not None
        and actual_tool_time is not None
    ):

        candidate_to_tool_gap = (
            actual_tool_time
            - first_candidate_time
        )

    execution_ready_to_tool_gap = None

    if (
        execution_ready_time is not None
        and actual_tool_time is not None
    ):

        execution_ready_to_tool_gap = (
            actual_tool_time
            - execution_ready_time
        )

    expected_tools = {
        "simple": "apps.launch",
        "ambiguous": "apps.find",
        "multi_step": "apps.find",
        "evidence": "apps.find",
    }

    expected_operation = (
        expected_tools[task_name]
    )

    tool_call_correct = (
        actual_tool is not None
        and actual_tool.startswith(
            expected_operation
        )
    )

    persistence_chars = 0

    if ready_candidate is not None:

        persistence_chars = max(
            0,
            (
                ready_candidate.last_seen_chars
                - ready_candidate.first_seen_chars
            ),
        )

    return RunResult(
        task_name=task_name,
        task=task,
        first_candidate_time=(
            first_candidate_time
        ),
        execution_ready_time=(
            execution_ready_time
        ),
        actual_tool_time=(
            actual_tool_time
        ),
        first_candidate=(
            first_candidate.signature
            if first_candidate
            else None
        ),
        execution_ready_candidate=(
            ready_candidate.signature
            if ready_candidate
            else None
        ),
        actual_tool=actual_tool,
        candidate_to_tool_gap=(
            candidate_to_tool_gap
        ),
        execution_ready_to_tool_gap=(
            execution_ready_to_tool_gap
        ),
        persistence_chars=(
            persistence_chars
        ),
        contradiction_count=(
            contradiction_count
        ),
        tool_call_correct=(
            tool_call_correct
        ),
        stream_valid=stream_valid,
        stream_chunks=stream_chunks,
        thinking_chars=thinking_chars,
        content_chars=content_chars,
        prompt_eval_count=(
            prompt_eval_count
        ),
        eval_count=eval_count,
        done_reason=done_reason,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt(
    value: float | None,
) -> str:

    if value is None:
        return "N/A"

    return f"{value:.3f}s"


def print_result(
    index: int,
    result: RunResult,
) -> None:

    print()
    print(
        f"RUN {index}"
    )

    print(
        "-" * 70
    )

    print(
        f"stream valid             : "
        f"{result.stream_valid}"
    )

    print(
        f"stream chunks            : "
        f"{result.stream_chunks}"
    )

    print(
        f"thinking chars           : "
        f"{result.thinking_chars}"
    )

    print(
        f"content chars            : "
        f"{result.content_chars}"
    )

    print(
        f"prompt eval count        : "
        f"{result.prompt_eval_count}"
    )

    print(
        f"eval count               : "
        f"{result.eval_count}"
    )

    print(
        f"done reason              : "
        f"{result.done_reason}"
    )

    print()

    print(
        f"first concrete candidate : "
        f"{fmt(result.first_candidate_time)}"
    )

    print(
        f"execution-ready          : "
        f"{fmt(result.execution_ready_time)}"
    )

    print(
        f"actual structured tool   : "
        f"{fmt(result.actual_tool_time)}"
    )

    print(
        f"candidate                : "
        f"{result.first_candidate}"
    )

    print(
        f"execution-ready action   : "
        f"{result.execution_ready_candidate}"
    )

    print(
        f"actual tool              : "
        f"{result.actual_tool}"
    )

    print()

    print(
        f"candidate → tool         : "
        f"{fmt(result.candidate_to_tool_gap)}"
    )

    print(
        f"ready → tool             : "
        f"{fmt(result.execution_ready_to_tool_gap)}"
    )

    print(
        f"candidate persistence    : "
        f"{result.persistence_chars} chars"
    )

    print(
        f"contradictions           : "
        f"{result.contradiction_count}"
    )

    print(
        f"tool correct             : "
        f"{result.tool_call_correct}"
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize(
    task_name: str,
    results: list[RunResult],
) -> None:

    def median(
        values: list[float],
    ) -> float | None:

        return (
            statistics.median(values)
            if values
            else None
        )

    valid_results = [
        result
        for result in results
        if result.stream_valid
    ]

    candidate_times = [
        result.first_candidate_time
        for result in valid_results
        if result.first_candidate_time
        is not None
    ]

    ready_times = [
        result.execution_ready_time
        for result in valid_results
        if result.execution_ready_time
        is not None
    ]

    tool_times = [
        result.actual_tool_time
        for result in valid_results
        if result.actual_tool_time
        is not None
    ]

    ready_gaps = [
        result.execution_ready_to_tool_gap
        for result in valid_results
        if result.execution_ready_to_tool_gap
        is not None
    ]

    contradictions = [
        result.contradiction_count
        for result in valid_results
    ]

    correct = sum(
        1
        for result in valid_results
        if result.tool_call_correct
    )

    print()
    print(
        "=" * 70
    )

    print(
        f"SUMMARY — {task_name}"
    )

    print(
        "=" * 70
    )

    print(
        f"total runs               : "
        f"{len(results)}"
    )

    print(
        f"valid runs               : "
        f"{len(valid_results)}/{len(results)}"
    )

    print(
        f"candidate detected       : "
        f"{len(candidate_times)}/{len(valid_results)}"
        if valid_results
        else
        "candidate detected       : N/A"
    )

    print(
        f"execution-ready detected : "
        f"{len(ready_times)}/{len(valid_results)}"
        if valid_results
        else
        "execution-ready detected : N/A"
    )

    print(
        f"correct tool calls       : "
        f"{correct}/{len(valid_results)}"
        if valid_results
        else
        "correct tool calls       : N/A"
    )

    print()

    print(
        f"median candidate time    : "
        f"{fmt(median(candidate_times))}"
    )

    print(
        f"median ready time        : "
        f"{fmt(median(ready_times))}"
    )

    print(
        f"median actual tool time  : "
        f"{fmt(median(tool_times))}"
    )

    print(
        f"median ready → tool      : "
        f"{fmt(median(ready_gaps))}"
    )

    if contradictions:

        print(
            f"median contradictions    : "
            f"{statistics.median(contradictions):.1f}"
        )

    if ready_gaps:

        print()

        print(
            "INTERPRETATION:"
        )

        print(
            "  The ready → tool gap is the observed "
            "latency between detecting a concrete"
        )

        print(
            "  execution-ready decision and Ollama's "
            "structured tool emission."
        )

        print(
            "  It is NOT yet evidence that the Agent can "
            "safely interrupt generation."
        )

    if len(valid_results) < len(results):

        print()

        print(
            "WARNING:"
        )

        print(
            "  One or more runs produced no usable "
            "generation and were excluded from latency"
        )

        print(
            "  statistics. Investigate the Ollama/context "
            "interaction before drawing conclusions."
        )

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:

    print(
        "=" * 70
    )

    print(
        "JARVIS — 1.1F-A EXECUTION-READY "
        "DECISION DETECTION"
    )

    print(
        "=" * 70
    )

    settings = Settings()

    print()

    print(
        f"Model       : "
        f"{settings.llm_model}"
    )

    print(
        f"Ollama      : "
        f"{settings.ollama_host}"
    )

    print(
        f"Context     : "
        f"{settings.context_size}"
    )

    print(
        f"Keep alive  : "
        f"{settings.keep_alive}"
    )

    print(
        "Thinking    : True"
    )

    print(
        f"Runs/task   : "
        f"{RUNS_PER_TASK}"
    )

    print()

    print(
        "IMPORTANT: diagnostic only — "
        "no production code changes."
    )

    agent = JarvisAgent()

    client = Client(
        host=settings.ollama_host,
    )

    all_results: dict[
        str,
        list[RunResult],
    ] = {}

    for task_name, task in TEST_TASKS:

        print()
        print()

        print(
            "#" * 70
        )

        print(
            f"TASK: {task_name}"
        )

        print(
            f"INPUT: {task}"
        )

        print(
            "#" * 70
        )

        results: list[RunResult] = []

        for run_index in range(
            1,
            RUNS_PER_TASK + 1,
        ):

            print()

            print(
                f"Running "
                f"{run_index}/{RUNS_PER_TASK} ..."
            )

            try:

                result = run_once(
                    client=client,
                    agent=agent,
                    task_name=task_name,
                    task=task,
                    settings=settings,
                )

                results.append(
                    result
                )

                print_result(
                    run_index,
                    result,
                )

            except Exception as exc:

                print(
                    f"ERROR in run "
                    f"{run_index}: "
                    f"{type(exc).__name__}: "
                    f"{exc}",
                    file=sys.stderr,
                )

        all_results[
            task_name
        ] = results

        if results:

            summarize(
                task_name,
                results,
            )

    # -------------------------------------------------------------------
    # Overall summary
    # -------------------------------------------------------------------

    print()
    print()

    print(
        "=" * 70
    )

    print(
        "1.1F-A OVERALL RESULT"
    )

    print(
        "=" * 70
    )

    all_valid = [
        result
        for results in all_results.values()
        for result in results
        if result.stream_valid
    ]

    all_gaps = [
        result.execution_ready_to_tool_gap
        for result in all_valid
        if result.execution_ready_to_tool_gap
        is not None
    ]

    all_ready = [
        result
        for result in all_valid
        if result.execution_ready_time
        is not None
    ]

    all_correct = [
        result
        for result in all_valid
        if result.tool_call_correct
    ]

    total_runs = sum(
        len(results)
        for results in all_results.values()
    )

    print()

    print(
        f"total runs                : "
        f"{total_runs}"
    )

    print(
        f"valid runs                : "
        f"{len(all_valid)}/{total_runs}"
    )

    print(
        f"execution-ready detected  : "
        f"{len(all_ready)}/{len(all_valid)}"
        if all_valid
        else
        "execution-ready detected  : N/A"
    )

    print(
        f"correct structured calls  : "
        f"{len(all_correct)}/{len(all_valid)}"
        if all_valid
        else
        "correct structured calls  : N/A"
    )

    if all_gaps:

        print()

        print(
            f"median ready → tool       : "
            f"{statistics.median(all_gaps):.3f}s"
        )

        print(
            f"mean ready → tool         : "
            f"{statistics.mean(all_gaps):.3f}s"
        )

        print(
            f"min ready → tool          : "
            f"{min(all_gaps):.3f}s"
        )

        print(
            f"max ready → tool          : "
            f"{max(all_gaps):.3f}s"
        )

    print()

    if not all_valid:

        print(
            "RESULT: INVALID EXPERIMENT"
        )

        print(
            "No usable Ollama generations were observed."
        )

        print(
            "Do NOT interpret this as failure of "
            "execution-ready detection."
        )

    else:

        print(
            "RESULT: VALID DIAGNOSTIC DATA"
        )

        print(
            "Do NOT change production code based on "
            "this run alone."
        )

    print()

    print(
        "The next decision depends on whether the "
        "execution-ready boundary is both"
    )

    print(
        "observable and sufficiently reliable across "
        "the four task classes."
    )

    print()


if __name__ == "__main__":
    main()

