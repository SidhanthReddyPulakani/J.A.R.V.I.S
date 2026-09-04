"""
TEST 5 — ADAPTIVE REASONING REGRESSION / STRESS SUITE

Purpose:
    Establish baseline behavior across:
      1. direct action
      2. application discovery
      3. missing application
      4. ambiguous application
      5. non-action conversational request

This is a BASELINE test.
It does NOT implement adaptive stopping.

Run:
    cd backend
    python test_adaptive_reasoning_regression.py
"""

from __future__ import annotations

import json
import statistics
import time

import ollama

from jarvis.core.config import Settings
from jarvis.core.agent import SYSTEM_PROMPT
from jarvis.capabilities.bootstrap import build_default_registry


TASKS = [
    {
        "name": "direct_launch",
        "prompt": "Open WhatsApp.",
        "expected_tool": "apps.launch",
        "expected_query": "WhatsApp",
    },
    {
        "name": "find_application",
        "prompt": "Find WhatsApp on my computer.",
        "expected_tool": "apps.find",
        "expected_query": "WhatsApp",
    },
    {
        "name": "missing_application",
        "prompt": "Open an application called DefinitelyNotInstalled123.",
        "expected_tool": "apps.launch",
        "expected_query": "DefinitelyNotInstalled123",
    },
    {
        "name": "ambiguous_request",
        "prompt": "Open the thing I use for messaging.",
        "expected_tool": None,
        "expected_query": None,
    },
    {
        "name": "conversation",
        "prompt": "Say hello to me.",
        "expected_tool": None,
        "expected_query": None,
    },
]

RUNS_PER_TASK = 3


def tool_info(tool_call):
    function = tool_call.get("function", {})

    return (
        function.get("name"),
        function.get("arguments"),
    )


def matches_expected(
    tool_name,
    arguments,
    expected_tool,
    expected_query,
):
    if expected_tool is None:
        return tool_name is None

    if tool_name != expected_tool:
        return False

    if expected_query is None:
        return True

    if not isinstance(arguments, dict):
        return False

    return (
        arguments.get("query")
        == expected_query
    )


def run_once(client, task):
    start = time.perf_counter()

    thinking = ""
    content = ""

    first_chunk_ms = None
    first_thinking_ms = None
    first_content_ms = None
    first_tool_ms = None

    tool_name = None
    tool_arguments = None

    stream = client.chat(
        model=Settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": task["prompt"],
            },
        ],
        tools=[],
        stream=True,
        think=True,
        options={
            "num_ctx": Settings.context_size,
        },
    )

    for chunk in stream:
        now = time.perf_counter()
        elapsed_ms = (
            now - start
        ) * 1000

        if first_chunk_ms is None:
            first_chunk_ms = elapsed_ms

        message = chunk.get(
            "message",
            {},
        )

        chunk_thinking = (
            message.get("thinking", "")
            or ""
        )

        chunk_content = (
            message.get("content", "")
            or ""
        )

        if (
            chunk_thinking
            and first_thinking_ms is None
        ):
            first_thinking_ms = elapsed_ms

        if (
            chunk_content
            and first_content_ms is None
        ):
            first_content_ms = elapsed_ms

        thinking += chunk_thinking
        content += chunk_content

        tool_calls = (
            message.get("tool_calls")
            or []
        )

        if (
            tool_calls
            and first_tool_ms is None
        ):
            first_tool_ms = elapsed_ms

            tool_name, tool_arguments = (
                tool_info(tool_calls[0])
            )

            # We only need the first structured action for this
            # baseline test.
            break

    correct = matches_expected(
        tool_name,
        tool_arguments,
        task["expected_tool"],
        task["expected_query"],
    )

    return {
        "task": task["name"],
        "prompt": task["prompt"],
        "first_chunk_ms": first_chunk_ms,
        "first_thinking_ms": first_thinking_ms,
        "first_content_ms": first_content_ms,
        "first_tool_ms": first_tool_ms,
        "thinking_chars": len(thinking),
        "content_chars": len(content),
        "tool_name": tool_name,
        "tool_arguments": tool_arguments,
        "expected_tool": task["expected_tool"],
        "expected_query": task["expected_query"],
        "correct": correct,
    }


def median(values):
    values = [
        value
        for value in values
        if value is not None
    ]

    return (
        statistics.median(values)
        if values
        else None
    )


def main():
    print("=" * 72)
    print("TEST 5 — ADAPTIVE REASONING REGRESSION / STRESS")
    print("=" * 72)
    print(f"model: {Settings.llm_model}")
    print("think: True")
    print(f"runs per task: {RUNS_PER_TASK}")

    build_default_registry()

    client = ollama.Client(
        host=Settings.ollama_host
    )

    all_results = []

    for task in TASKS:
        print("\n" + "=" * 72)
        print(
            f"TASK: {task['name']}"
        )
        print(
            f"prompt: {task['prompt']}"
        )
        print("=" * 72)

        task_results = []

        for run in range(
            1,
            RUNS_PER_TASK + 1,
        ):
            print(
                f"run {run}/{RUNS_PER_TASK} ..."
            )

            try:
                result = run_once(
                    client,
                    task,
                )

                task_results.append(
                    result
                )
                all_results.append(
                    result
                )

                print(
                    f"  tool={result['tool_name']} "
                    f"args={result['tool_arguments']} "
                    f"tool_ms={result['first_tool_ms']} "
                    f"thinking={result['thinking_chars']} "
                    f"correct={result['correct']}"
                )

            except Exception as exc:
                result = {
                    "task": task["name"],
                    "prompt": task["prompt"],
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    "correct": False,
                }

                task_results.append(
                    result
                )
                all_results.append(
                    result
                )

                print(
                    "  ERROR:",
                    result["error"],
                )

        tool_times = [
            r.get("first_tool_ms")
            for r in task_results
        ]

        thinking_chars = [
            r.get("thinking_chars")
            for r in task_results
        ]

        correct_count = sum(
            bool(r.get("correct"))
            for r in task_results
        )

        print("\nTASK SUMMARY")
        print("-" * 72)

        print(
            f"correct: "
            f"{correct_count}/{RUNS_PER_TASK}"
        )

        print(
            f"tool latency median: "
            f"{median(tool_times)}"
        )

        print(
            f"thinking chars median: "
            f"{median(thinking_chars)}"
        )

    print("\n" + "=" * 72)
    print("OVERALL SUMMARY")
    print("=" * 72)

    for task in TASKS:
        results = [
            r
            for r in all_results
            if r.get("task")
            == task["name"]
        ]

        correct = sum(
            bool(r.get("correct"))
            for r in results
        )

        tool_times = [
            r.get("first_tool_ms")
            for r in results
        ]

        thinking_chars = [
            r.get("thinking_chars")
            for r in results
        ]

        print(
            f"{task['name']}: "
            f"correct={correct}/{len(results)} "
            f"tool_median={median(tool_times)} "
            f"thinking_median={median(thinking_chars)}"
        )

    print("\nRAW RESULTS")

    for result in all_results:
        print(
            json.dumps(
                result,
                default=str,
            )
        )


if __name__ == "__main__":
    main()