"""
Experimental probe for the earliest observable commitment point in Qwen3.

Question:

    Once the model's stream contains enough observable evidence to identify
    the exact operation and arguments, how long does it continue before the
    structured tool call is emitted?

This test intentionally does NOT:
    - modify production code
    - modify SYSTEM_PROMPT
    - inject a "commit" instruction
    - impose an artificial reasoning budget
    - change the Agent loop

The candidate-readiness signal is experimental only.

It is NOT a production confidence score.

Run from backend/:

    python test_commit_readiness.py
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any

import ollama

from jarvis.capabilities.bootstrap import build_default_registry
from jarvis.core.agent import SYSTEM_PROMPT
from jarvis.core.config import settings


TASK = "Open WhatsApp."
RUNS = 10


@dataclass
class RunResult:
    run: int

    first_chunk_ms: float | None
    first_thinking_ms: float | None

    candidate_ready_ms: float | None
    first_tool_ms: float | None
    done_ms: float | None

    candidate_to_tool_ms: float | None

    thinking_chars_at_candidate: int | None
    thinking_chars_at_tool: int

    tool_name: str | None
    tool_arguments: dict[str, Any] | None

    correct_tool: bool
    candidate_seen: bool


def _tool_name(tool_call: Any) -> str | None:
    function = getattr(tool_call, "function", None)

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
    """
    Use the repository's real capability registry.

    We intentionally do not reconstruct the tool schema manually.
    """

    registry = build_default_registry()

    return [
        definition.to_llm_tool_definition()
        for definition in registry.discover()
    ]


def run_once(
    client: ollama.Client,
    tools: list[dict[str, Any]],
    run: int,
) -> RunResult:

    start = time.perf_counter()

    first_chunk_ms = None
    first_thinking_ms = None

    candidate_ready_ms = None
    first_tool_ms = None
    done_ms = None

    thinking = ""

    tool_name = None
    tool_arguments = None

    thinking_chars_at_candidate = None
    thinking_chars_at_tool = 0

    candidate_seen = False

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

        thinking += chunk_thinking

        if (
            chunk_thinking
            and first_thinking_ms is None
        ):
            first_thinking_ms = now_ms

        # --------------------------------------------------
        # Experimental candidate-readiness marker.
        #
        # We only consider the model "candidate ready" after
        # its accumulated thinking contains BOTH:
        #
        #     apps.launch
        #     WhatsApp
        #
        # This is deliberately conservative.
        #
        # It is NOT a production stopping rule.
        # --------------------------------------------------

        if (
            not candidate_seen
            and "apps.launch" in thinking
            and "WhatsApp" in thinking
        ):
            candidate_seen = True

            candidate_ready_ms = now_ms

            thinking_chars_at_candidate = len(
                thinking
            )

        tool_calls = (
            getattr(
                message,
                "tool_calls",
                None,
            )
            or []
        )

        if tool_calls:

            if first_tool_ms is None:
                first_tool_ms = now_ms

                first_tool = tool_calls[0]

                tool_name = _tool_name(
                    first_tool
                )

                tool_arguments = _tool_arguments(
                    first_tool
                )

                thinking_chars_at_tool = len(
                    thinking
                )

            # --------------------------------------------------
            # This is the commitment boundary being measured.
            #
            # Once the structured tool call exists, stop
            # consuming the stream.
            # --------------------------------------------------

            break

        if bool(
            getattr(
                chunk,
                "done",
                False,
            )
        ):
            done_ms = now_ms
            break

    candidate_to_tool_ms = None

    if (
        candidate_ready_ms is not None
        and first_tool_ms is not None
    ):
        candidate_to_tool_ms = (
            first_tool_ms
            - candidate_ready_ms
        )

    correct_tool = _is_correct_tool(
        tool_name,
        tool_arguments,
    )

    return RunResult(
        run=run,
        first_chunk_ms=first_chunk_ms,
        first_thinking_ms=first_thinking_ms,
        candidate_ready_ms=candidate_ready_ms,
        first_tool_ms=first_tool_ms,
        done_ms=done_ms,
        candidate_to_tool_ms=candidate_to_tool_ms,
        thinking_chars_at_candidate=(
            thinking_chars_at_candidate
        ),
        thinking_chars_at_tool=(
            thinking_chars_at_tool
        ),
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        correct_tool=correct_tool,
        candidate_seen=candidate_seen,
    )


def _stats(
    values: list[float],
) -> str:

    if not values:
        return "n/a"

    return (
        f"median={statistics.median(values):.1f}ms "
        f"mean={statistics.mean(values):.1f}ms "
        f"min={min(values):.1f}ms "
        f"max={max(values):.1f}ms"
    )


def main() -> None:

    print("=" * 72)
    print("COMMIT READINESS STREAM EXPERIMENT")
    print("=" * 72)

    print(f"task: {TASK}")
    print(f"model: {settings.llm_model}")
    print("think: True")
    print(f"runs: {RUNS}")

    print(
        "prompt: production SYSTEM_PROMPT unchanged"
    )

    print(
        "candidate signal: exact apps.launch + "
        "WhatsApp in thinking stream"
    )

    print(
        "candidate signal is experimental; "
        "it is NOT a confidence score"
    )

    print()

    client = ollama.Client(
        host=settings.ollama_host
    )

    tools = _build_tools()

    results: list[RunResult] = []

    for run in range(
        1,
        RUNS + 1,
    ):

        print(
            f"run {run}/{RUNS} ...",
            flush=True,
        )

        result = run_once(
            client,
            tools,
            run,
        )

        results.append(result)

        print(
            f"  candidate="
            f"{result.candidate_ready_ms!s}ms "
            f"tool="
            f"{result.first_tool_ms!s}ms "
            f"gap="
            f"{result.candidate_to_tool_ms!s}ms "
            f"thinking_at_candidate="
            f"{result.thinking_chars_at_candidate!s} "
            f"thinking_at_tool="
            f"{result.thinking_chars_at_tool} "
            f"correct="
            f"{result.correct_tool}",
            flush=True,
        )

    candidate_gaps = [
        r.candidate_to_tool_ms
        for r in results
        if r.candidate_to_tool_ms is not None
    ]

    tool_times = [
        r.first_tool_ms
        for r in results
        if r.first_tool_ms is not None
    ]

    candidate_times = [
        r.candidate_ready_ms
        for r in results
        if r.candidate_ready_ms is not None
    ]

    print()
    print("SUMMARY")
    print("-" * 72)

    print(
        f"candidate observed: "
        f"{len(candidate_times)}/{RUNS}"
    )

    print(
        f"correct tool calls: "
        f"{sum(r.correct_tool for r in results)}/{RUNS}"
    )

    print(
        "candidate readiness time: "
        f"{_stats(candidate_times)}"
    )

    print(
        "first tool-call time:     "
        f"{_stats(tool_times)}"
    )

    print(
        "candidate → tool gap:     "
        f"{_stats(candidate_gaps)}"
    )

    if candidate_gaps:

        print()
        print("INTERPRETATION")
        print("-" * 72)

        print(
            "A positive candidate→tool gap means the "
            "stream contained the experimental evidence "
            "marker before Qwen emitted the structured "
            "tool call."
        )

        print(
            "That gap is the quantity worth investigating "
            "for a runtime commitment observer."
        )

        print(
            "This experiment does NOT establish that the "
            "marker is a valid production stopping rule."
        )

        print(
            "It only establishes whether there is an "
            "observable pre-commit interval to study."
        )

    else:

        print()
        print(
            "No candidate marker was observed before "
            "the tool call in this sample."
        )

        print(
            "Do not infer that no overthinking exists. "
            "The marker may simply be too strict or "
            "absent from the thinking text."
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