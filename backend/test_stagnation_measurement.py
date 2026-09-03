from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from jarvis.core.llm import LLMClient
from jarvis.core.stagnation_detector import StagnationDetector


OUTPUT_FILE = Path("stagnation_measurement.jsonl")


# These prompts are intended to exercise multi-step generation.
# They are measurement cases, not assertions that Qwen3 must stagnate.
MEASUREMENT_CASES = [
    (
        "multi_step_planning",
        """
You are Jarvis. Work through this task carefully:
1. Determine what information is needed to complete the request.
2. Identify the appropriate action.
3. Explain what should happen next.
Do not execute anything. Continue reasoning until you have a complete answer.
""",
    ),
    (
        "ambiguous_request",
        """
Analyze this request carefully and determine what Jarvis would need to do:
"Open the application I use for messaging and get it ready."
Consider ambiguity, possible interpretations, and the action required.
Do not execute anything.
""",
    ),
    (
        "self_correction",
        """
Solve this task carefully:
A user asks Jarvis to perform a multi-step computer operation, but the
first possible approach may not work. Reason through the possible approach,
identify what could fail, correct yourself if necessary, and arrive at the
best final approach.
Do not execute anything.
""",
    ),
]


def _tool_intents(tool_calls) -> tuple[str, ...]:
    intents: list[str] = []

    for call in tool_calls or []:
        function = getattr(call, "function", None)
        if function is None:
            continue

        name = getattr(function, "name", None)

        if name:
            intents.append(str(name))

    return tuple(intents)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("case_name", "prompt"),
    MEASUREMENT_CASES,
)
def test_real_qwen3_stagnation_measurement(
    case_name: str,
    prompt: str,
):
    """
    Real Ollama/Qwen3 measurement.

    This test intentionally does NOT fail when stagnation is detected.
    Its purpose is to collect evidence for Phase 7.

    Run explicitly with:

        pytest test_stagnation_measurement.py -q -s
    """

    client = LLMClient()
    detector = StagnationDetector(window_size=3)

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    observations: list[dict] = []
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    tool_calls = []

    started = time.perf_counter()

    for chunk in client.stream(
        messages=messages,
        tools=[],
    ):
        thinking = chunk.get("thinking") or ""
        content = chunk.get("content") or ""
        chunk_tools = chunk.get("tool_calls") or []

        if thinking:
            thinking_parts.append(str(thinking))

        if content:
            content_parts.append(str(content))

        if chunk_tools:
            tool_calls.extend(chunk_tools)

        elapsed = time.perf_counter() - started

        observation = detector.observe(
            content=content,
            tool_intents=_tool_intents(chunk_tools),
            new_action_information=bool(
                content
                or chunk_tools
            ),
        )

        observations.append(
            {
                "elapsed_seconds": elapsed,
                "thinking_length": len(thinking),
                "content_length": len(content),
                "tool_intents": list(
                    _tool_intents(chunk_tools)
                ),
                "repeated_content": (
                    observation.repeated_content
                ),
                "repeated_tool_intent": (
                    observation.repeated_tool_intent
                ),
                "no_new_action_information": (
                    observation.no_new_action_information
                ),
                "repeated_self_correction": (
                    observation.repeated_self_correction
                ),
                "stagnant": observation.stagnant,
                "done": bool(chunk.get("done")),
            }
        )

    total_elapsed = (
        time.perf_counter() - started
    )

    result = {
        "case": case_name,
        "elapsed_seconds": total_elapsed,
        "thinking_length": len(
            "".join(thinking_parts)
        ),
        "content_length": len(
            "".join(content_parts)
        ),
        "tool_intents": list(
            _tool_intents(tool_calls)
        ),
        "stagnation_detected": any(
            item["stagnant"]
            for item in observations
        ),
        "observations": observations,
    }

    with OUTPUT_FILE.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                result,
                ensure_ascii=False,
            )
            + "\n"
        )

    print()
    print("=" * 72)
    print(f"CASE: {case_name}")
    print(f"Elapsed: {total_elapsed:.3f}s")
    print(
        f"Thinking chars: {result['thinking_length']}"
    )
    print(
        f"Content chars: {result['content_length']}"
    )
    print(
        f"Tool intents: {result['tool_intents']}"
    )
    print(
        "Stagnation detected: "
        f"{result['stagnation_detected']}"
    )
    print("=" * 72)

    # Measurement test: successful generation is enough.
    # Stagnation is evidence, not a test failure.
    assert observations