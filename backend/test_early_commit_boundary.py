"""
TEST 3 — Synthetic Early-Commit Boundary

Purpose:
    Determine whether Qwen's reasoning reaches a stable actionable
    commitment before the actual structured tool call.

This is an observational experiment.
It does NOT modify production behavior.

Run:
    cd backend
    python test_early_commit_boundary.py
"""

from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter

import ollama

from jarvis.core.config import Settings
from jarvis.core.agent import SYSTEM_PROMPT
from jarvis.capabilities.bootstrap import build_default_registry


TASK = "Open WhatsApp."
RUNS = 5

# Sample the cumulative thinking stream at this granularity.
SAMPLE_CHARS = 100

# Generic action/commit vocabulary.
ACTION_TERMS = {
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
    "execute",
    "execution",
    "call",
}

# Terms indicating uncertainty / deliberation.
UNCERTAINTY_TERMS = {
    "maybe",
    "perhaps",
    "could",
    "might",
    "need to",
    "should",
    "i should",
    "let me",
    "possibly",
    "uncertain",
    "not sure",
    "verify",
    "check",
    "however",
    "but",
}

# Generic commitment patterns.
COMMIT_PATTERNS = [
    r"\bI(?:'ll| will)\s+(?:open|launch|start|run)\b",
    r"\b(?:use|call|invoke|execute)\s+(?:the\s+)?(?:apps\.launch|launch)\b",
    r"\b(?:tool|function)\s+(?:call|to use)\b",
    r"\b(?:the|correct)\s+(?:action|tool|function)\b",
    r"\b(?:I need to|I should)\s+(?:open|launch|start|run)\b",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def sentence_list(text: str) -> list[str]:
    parts = re.split(r"[.!?;\n]+", text)
    return [
        normalize(part)
        for part in parts
        if normalize(part)
    ]


def longest_repeated_suffix(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    count = 0

    while count < limit and a[-1 - count] == b[-1 - count]:
        count += 1

    return count


def score_sample(text: str, previous: str) -> dict:
    normalized = normalize(text)
    sentences = sentence_list(text)

    action_count = sum(
        normalized.count(term)
        for term in ACTION_TERMS
    )

    uncertainty_count = sum(
        normalized.count(term)
        for term in UNCERTAINTY_TERMS
    )

    commit_hits = sum(
        bool(re.search(pattern, normalized))
        for pattern in COMMIT_PATTERNS
    )

    counts = Counter(sentences)
    repeated_sentences = sum(
        count - 1
        for count in counts.values()
        if count > 1
    )

    repeated_suffix = longest_repeated_suffix(
        normalized,
        normalize(previous),
    ) if previous else 0

    # "Action density" is deliberately only a descriptive signal.
    action_density = (
        action_count / max(len(normalized) / 100, 1)
    )

    return {
        "chars": len(text),
        "new_chars": max(0, len(text) - len(previous)),
        "action_count": action_count,
        "uncertainty_count": uncertainty_count,
        "commit_hits": commit_hits,
        "repeated_sentences": repeated_sentences,
        "repeated_suffix_chars": repeated_suffix,
        "action_density": round(action_density, 3),
        "tail": text[-180:].replace("\n", " "),
    }


def classify_boundary(samples: list[dict]) -> dict | None:
    """
    Find the earliest sample where the reasoning appears to have
    transitioned from identifying an action to repeatedly committing
    to that action.

    This is NOT a production rule.
    It is a synthetic analysis heuristic.

    Criteria:
        - at least one generic commitment pattern
        - action evidence present
        - low uncertainty relative to action evidence
        - subsequent samples remain action-oriented
    """

    for i, sample in enumerate(samples):
        if sample["commit_hits"] < 1:
            continue

        if sample["action_count"] < 2:
            continue

        if sample["uncertainty_count"] > sample["action_count"] + 2:
            continue

        future = samples[i:min(i + 3, len(samples))]

        if len(future) < 2:
            continue

        future_action = all(
            s["action_count"] >= sample["action_count"] * 0.5
            for s in future
        )

        if not future_action:
            continue

        return {
            "sample_index": i,
            "elapsed_ms": sample["elapsed_ms"],
            "chars": sample["chars"],
            "action_count": sample["action_count"],
            "uncertainty_count": sample["uncertainty_count"],
            "commit_hits": sample["commit_hits"],
        }

    return None


def run_once(client: ollama.Client, run_number: int) -> dict:
    print(f"\nrun {run_number}/{RUNS} ...")

    start = time.perf_counter()

    thinking = ""
    samples = []
    next_sample = SAMPLE_CHARS

    first_chunk_ms = None
    first_thinking_ms = None
    first_tool_ms = None
    tool_name = None
    tool_arguments = None

    last_sample_text = ""

    stream = client.chat(
        model=Settings.llm_model,
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
        tools=[],
        stream=True,
        think=True,
        options={
            "num_ctx": Settings.context_size,
        },
    )

    for chunk in stream:
        now = time.perf_counter()
        elapsed_ms = (now - start) * 1000

        if first_chunk_ms is None:
            first_chunk_ms = elapsed_ms

        message = chunk.get("message", {})

        chunk_thinking = message.get("thinking", "") or ""
        chunk_content = message.get("content", "") or ""

        if chunk_thinking and first_thinking_ms is None:
            first_thinking_ms = elapsed_ms

        thinking += chunk_thinking

        tool_calls = message.get("tool_calls") or []

        if tool_calls and first_tool_ms is None:
            first_tool_ms = elapsed_ms

            call = tool_calls[0]

            function = call.get("function", {})

            tool_name = function.get("name")
            tool_arguments = function.get("arguments")

        while len(thinking) >= next_sample:
            metrics = score_sample(
                thinking,
                last_sample_text,
            )

            metrics["elapsed_ms"] = elapsed_ms
            metrics["sample_index"] = len(samples)

            samples.append(metrics)

            last_sample_text = thinking
            next_sample += SAMPLE_CHARS

    boundary = classify_boundary(samples)

    return {
        "run": run_number,
        "first_chunk_ms": first_chunk_ms,
        "first_thinking_ms": first_thinking_ms,
        "first_tool_ms": first_tool_ms,
        "synthetic_boundary": boundary,
        "thinking_chars": len(thinking),
        "tool_name": tool_name,
        "tool_arguments": tool_arguments,
        "samples": samples,
    }


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def main():
    print("=" * 72)
    print("TEST 3 — SYNTHETIC EARLY-COMMIT BOUNDARY")
    print("=" * 72)
    print(f"task: {TASK}")
    print(f"model: {Settings.llm_model}")
    print(f"think: True")
    print(f"runs: {RUNS}")
    print()
    print("This is NOT a production stopping rule.")
    print("It estimates where reasoning appears to stabilize.")

    build_default_registry()

    client = ollama.Client(host=Settings.ollama_host)

    results = []

    for run in range(1, RUNS + 1):
        result = run_once(client, run)
        results.append(result)

        boundary = result["synthetic_boundary"]

        if boundary:
            print(
                f"  boundary={boundary['elapsed_ms']:.1f}ms "
                f"chars={boundary['chars']} "
                f"actions={boundary['action_count']} "
                f"uncertainty={boundary['uncertainty_count']}"
            )
        else:
            print("  boundary=NOT FOUND")

        tool_ms = result["first_tool_ms"]
        tool_display = f"{tool_ms:.1f}ms" if tool_ms is not None else "NOT OBSERVED"

        print(
            f"  tool={tool_display} "
            f"thinking_chars={result['thinking_chars']} "
            f"tool={result['tool_name']}"
        )

    boundaries = [
        r["synthetic_boundary"]["elapsed_ms"]
        for r in results
        if r["synthetic_boundary"]
    ]

    tools = [
        r["first_tool_ms"]
        for r in results
        if r["first_tool_ms"] is not None
    ]

    print("\nSUMMARY")
    print("-" * 72)

    print(
        f"synthetic boundary observed: "
        f"{len(boundaries)}/{RUNS}"
    )

    if boundaries:
        print(
            f"synthetic boundary time: "
            f"median={median(boundaries):.1f}ms "
            f"min={min(boundaries):.1f}ms "
            f"max={max(boundaries):.1f}ms"
        )

    if tools:
        print(
            f"actual tool commitment: "
            f"median={median(tools):.1f}ms "
            f"min={min(tools):.1f}ms "
            f"max={max(tools):.1f}ms"
        )

    if boundaries and tools:
        gaps = []

        for r in results:
            if r["synthetic_boundary"] and r["first_tool_ms"]:
                gaps.append(
                    r["first_tool_ms"]
                    - r["synthetic_boundary"]["elapsed_ms"]
                )

        if gaps:
            print(
                f"boundary → actual tool gap: "
                f"median={median(gaps):.1f}ms "
                f"min={min(gaps):.1f}ms "
                f"max={max(gaps):.1f}ms"
            )

    print("\nRAW RESULTS")

    for result in results:
        print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()