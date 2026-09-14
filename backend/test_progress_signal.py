"""
Test #2 — Incremental reasoning progress signal.

Goal
----

Determine whether streamed Qwen3 thinking contains measurable progress
toward an already-identifiable action, and whether that progress eventually
flattens into repetition before the structured tool call.

This is an OBSERVATION experiment.

It does not:
    - modify production code
    - modify SYSTEM_PROMPT
    - modify the Agent loop
    - stop the model early
    - inject a commit instruction
    - claim that any signal is production-safe

The experiment deliberately avoids using a task-specific "apps.launch" +
"WhatsApp" readiness marker.

Instead, it records incremental properties of the thinking stream:

    - cumulative thinking characters
    - newly added thinking characters
    - unique-character ratio
    - repeated suffix ratio
    - repeated normalized sentences
    - presence of action/tool/schema concepts
    - time between observable changes

The output gives us a trajectory rather than a single score.

Run from backend/:

    python test_progress_signal.py
"""

from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

import ollama

from jarvis.capabilities.bootstrap import build_default_registry
from jarvis.core.agent import SYSTEM_PROMPT
from jarvis.core.config import settings


TASK = "Open WhatsApp."

RUNS = 5

# Sample the accumulated thinking every N newly accumulated characters.
#
# This is only a measurement interval. It is NOT a production threshold.
SAMPLE_CHARS = 100


@dataclass
class ThinkingSample:
    run: int

    elapsed_ms: float

    total_chars: int
    new_chars: int

    unique_chars: int
    unique_ratio: float

    repeated_sentence_count: int
    repeated_sentence_ratio: float

    repeated_suffix_chars: int
    repeated_suffix_ratio: float

    action_keyword_count: int

    text_tail: str


@dataclass
class RunResult:
    run: int

    first_chunk_ms: float | None
    first_tool_ms: float | None

    thinking_chars: int

    tool_name: str | None
    tool_arguments: dict[str, Any] | None

    correct_tool: bool

    samples: list[ThinkingSample]


ACTION_TERMS = (
    "open",
    "launch",
    "start",
    "run",
    "application",
    "app",
    "tool",
    "function",
    "query",
    "argument",
    "arguments",
    "apps.launch",
)


def _tool_name(tool_call: Any) -> str | None:

    function = getattr(
        tool_call,
        "function",
        None,
    )

    return getattr(
        function,
        "name",
        None,
    )


def _tool_arguments(tool_call: Any) -> dict[str, Any]:

    function = getattr(
        tool_call,
        "function",
        None,
    )

    arguments = getattr(
        function,
        "arguments",
        None,
    )

    if isinstance(arguments, dict):
        return arguments

    return {}


def _is_correct_tool(
    name: str | None,
    arguments: dict[str, Any] | None,
) -> bool:

    return (
        name == "apps.launch"
        and isinstance(arguments, dict)
        and arguments.get("query") == "WhatsApp"
    )


def _build_tools() -> list[dict[str, Any]]:

    registry = build_default_registry()

    return [
        definition.to_llm_tool_definition()
        for definition in registry.discover()
    ]


def _normalize_text(text: str) -> str:

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _sentences(text: str) -> list[str]:

    normalized = _normalize_text(text)

    if not normalized:
        return []

    pieces = re.split(
        r"[.!?;\n]+",
        normalized,
    )

    return [
        piece.strip()
        for piece in pieces
        if piece.strip()
    ]


def _repeated_sentence_metrics(
    previous_text: str,
    current_text: str,
) -> tuple[int, float]:

    previous_sentences = _sentences(
        previous_text
    )

    current_sentences = _sentences(
        current_text
    )

    if not current_sentences:
        return 0, 0.0

    previous_counts = Counter(
        previous_sentences
    )

    repeated = sum(
        1
        for sentence in current_sentences
        if previous_counts[sentence] > 0
    )

    ratio = (
        repeated / len(current_sentences)
    )

    return repeated, ratio


def _repeated_suffix_length(
    previous_text: str,
    current_text: str,
    max_length: int = 500,
) -> int:

    previous = _normalize_text(
        previous_text
    )[-max_length:]

    current = _normalize_text(
        current_text
    )[-max_length:]

    max_possible = min(
        len(previous),
        len(current),
    )

    longest = 0

    for size in range(
        20,
        max_possible + 1,
    ):
        if previous[-size:] == current[-size:]:
            longest = size

    return longest


def _action_keyword_count(
    text: str,
) -> int:

    normalized = _normalize_text(
        text
    )

    return sum(
        normalized.count(term)
        for term in ACTION_TERMS
    )


def _make_sample(
    run: int,
    elapsed_ms: float,
    previous_text: str,
    current_text: str,
) -> ThinkingSample:

    total_chars = len(
        current_text
    )

    new_chars = max(
        0,
        len(current_text)
        - len(previous_text),
    )

    unique_chars = len(
        set(current_text)
    )

    unique_ratio = (
        unique_chars / total_chars
        if total_chars
        else 0.0
    )

    repeated_sentence_count, repeated_sentence_ratio = (
        _repeated_sentence_metrics(
            previous_text,
            current_text,
        )
    )

    repeated_suffix_chars = (
        _repeated_suffix_length(
            previous_text,
            current_text,
        )
    )

    repeated_suffix_ratio = (
        repeated_suffix_chars / total_chars
        if total_chars
        else 0.0
    )

    action_keyword_count = (
        _action_keyword_count(
            current_text
        )
    )

    tail = current_text[-180:]

    return ThinkingSample(
        run=run,
        elapsed_ms=elapsed_ms,
        total_chars=total_chars,
        new_chars=new_chars,
        unique_chars=unique_chars,
        unique_ratio=unique_ratio,
        repeated_sentence_count=(
            repeated_sentence_count
        ),
        repeated_sentence_ratio=(
            repeated_sentence_ratio
        ),
        repeated_suffix_chars=(
            repeated_suffix_chars
        ),
        repeated_suffix_ratio=(
            repeated_suffix_ratio
        ),
        action_keyword_count=(
            action_keyword_count
        ),
        text_tail=tail,
    )


def run_once(
    client: ollama.Client,
    tools: list[dict[str, Any]],
    run: int,
) -> RunResult:

    start = time.perf_counter()

    first_chunk_ms = None
    first_tool_ms = None

    thinking = ""
    last_sampled_text = ""

    samples: list[ThinkingSample] = []

    tool_name = None
    tool_arguments = None

    next_sample_at = SAMPLE_CHARS

    response_stream = client.chat(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": TASK,
            },
        ],
        tools=tools,
        stream=True,
        think=True,
        keep_alive=settings.keep_alive,
        options={
            "num_ctx": settings.context_size,
        },
    )

    for chunk in response_stream:

        now_ms = (
            time.perf_counter() - start
        ) * 1000.0

        if first_chunk_ms is None:
            first_chunk_ms = now_ms

        message = getattr(
            chunk,
            "message",
            None,
        )

        chunk_thinking = (
            getattr(
                message,
                "thinking",
                "",
            )
            or ""
        )

        if chunk_thinking:

            thinking += chunk_thinking

            if len(thinking) >= next_sample_at:

                sample = _make_sample(
                    run=run,
                    elapsed_ms=now_ms,
                    previous_text=last_sampled_text,
                    current_text=thinking,
                )

                samples.append(
                    sample
                )

                last_sampled_text = thinking

                while (
                    next_sample_at
                    <= len(thinking)
                ):
                    next_sample_at += SAMPLE_CHARS

        tool_calls = (
            getattr(
                message,
                "tool_calls",
                None,
            )
            or []
        )

        if tool_calls:

            first_tool_ms = now_ms

            first_tool = tool_calls[0]

            tool_name = _tool_name(
                first_tool
            )

            tool_arguments = _tool_arguments(
                first_tool
            )

            break

        if bool(
            getattr(
                chunk,
                "done",
                False,
            )
        ):
            break

    return RunResult(
        run=run,
        first_chunk_ms=first_chunk_ms,
        first_tool_ms=first_tool_ms,
        thinking_chars=len(thinking),
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        correct_tool=_is_correct_tool(
            tool_name,
            tool_arguments,
        ),
        samples=samples,
    )


def _print_sample(
    sample: ThinkingSample,
) -> None:

    print(
        f"    "
        f"{sample.elapsed_ms:8.1f}ms "
        f"chars={sample.total_chars:4d} "
        f"new={sample.new_chars:4d} "
        f"unique={sample.unique_ratio:.2f} "
        f"repeat_sentence={sample.repeated_sentence_ratio:.2f} "
        f"repeat_suffix={sample.repeated_suffix_ratio:.2f} "
        f"action_terms={sample.action_keyword_count:2d}"
    )

    print(
        f"      tail: {sample.text_tail!r}"
    )


def _print_trajectory(
    result: RunResult,
) -> None:

    print()
    print(
        f"  trajectory for run {result.run}:"
    )

    for sample in result.samples:
        _print_sample(sample)


def main() -> None:

    print("=" * 72)
    print("INCREMENTAL REASONING PROGRESS EXPERIMENT")
    print("=" * 72)

    print(f"task: {TASK}")
    print(f"model: {settings.llm_model}")
    print("think: True")
    print(f"runs: {RUNS}")
    print(
        "prompt: production SYSTEM_PROMPT unchanged"
    )
    print(
        f"sample interval: {SAMPLE_CHARS} thinking chars"
    )

    print()
    print(
        "IMPORTANT: the measurements below are "
        "observations, not a production stopping rule."
    )

    client = ollama.Client(
        host=settings.ollama_host
    )

    tools = _build_tools()

    results: list[RunResult] = []

    for run in range(
        1,
        RUNS + 1,
    ):

        print()
        print(
            f"run {run}/{RUNS} ..."
        )

        result = run_once(
            client,
            tools,
            run,
        )

        results.append(
            result
        )

        print(
            f"  thinking chars: "
            f"{result.thinking_chars}"
        )

        print(
            f"  first tool: "
            f"{result.first_tool_ms}ms"
        )

        print(
            f"  tool: "
            f"{result.tool_name}"
        )

        print(
            f"  arguments: "
            f"{result.tool_arguments}"
        )

        print(
            f"  correct: "
            f"{result.correct_tool}"
        )

        _print_trajectory(
            result
        )

    tool_times = [
        result.first_tool_ms
        for result in results
        if result.first_tool_ms is not None
    ]

    thinking_sizes = [
        result.thinking_chars
        for result in results
    ]

    correct_count = sum(
        result.correct_tool
        for result in results
    )

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    print(
        f"correct tool calls: "
        f"{correct_count}/{RUNS}"
    )

    if tool_times:
        print(
            "first tool latency: "
            f"median={statistics.median(tool_times):.1f}ms "
            f"mean={statistics.mean(tool_times):.1f}ms "
            f"min={min(tool_times):.1f}ms "
            f"max={max(tool_times):.1f}ms"
        )

    print(
        "thinking size: "
        f"median={statistics.median(thinking_sizes):.0f} chars "
        f"mean={statistics.mean(thinking_sizes):.0f} chars "
        f"min={min(thinking_sizes)} "
        f"max={max(thinking_sizes)}"
    )

    print()
    print("WHAT WE ARE LOOKING FOR")
    print("-" * 72)

    print(
        "1. Does the action/tool vocabulary appear early?"
    )

    print(
        "2. Does new information continue appearing "
        "after the action is already identifiable?"
    )

    print(
        "3. Do repeated sentences or repeated suffixes "
        "increase near the end?"
    )

    print(
        "4. Does the trajectory flatten before the "
        "structured tool call?"
    )

    print(
        "5. Is the pattern consistent across runs?"
    )

    print()
    print("RAW RESULTS")

    for result in results:

        print(
            json.dumps(
                asdict(result),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()