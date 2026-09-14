import sys
import time
import json

from ollama import Client
from jarvis.core.config import Settings


MODEL = "qwen3:4b"
OLLAMA_HOST = "http://127.0.0.1:11434"

TEST_INPUT = "Open WhatsApp."

# How often we sample the generated reasoning.
# Smaller = more precise boundary detection, slightly more overhead.
SAMPLE_CHARS = 100

# Candidate markers indicating that Qwen has effectively
# committed to the intended capability.
COMMIT_MARKERS = [
    "apps.launch",
    '"query": "WhatsApp"',
    '"query":"WhatsApp"',
    "launch",
    "WhatsApp",
]


def safe_print(value):
    try:
        print(value)
    except UnicodeEncodeError:
        print(
            str(value)
            .encode("utf-8", errors="replace")
            .decode("utf-8")
        )


def estimate_tokens(text):
    # Same approximation used in the previous experiments.
    return len(text) / 4


def detect_candidate(text):
    """
    Detect whether the reasoning has reached a plausible
    tool-decision boundary.

    This is deliberately conservative:
    we are NOT claiming that seeing a marker means it is
    safe to interrupt production execution.
    """
    lowered = text.lower()

    for marker in COMMIT_MARKERS:
        if marker.lower() in lowered:
            return True, marker

    return False, None


def run_once(client, run_number):
    print("\n" + "=" * 70)
    print(f"RUN {run_number}")
    print("=" * 70)

    messages = [
        {
            "role": "system",
            "content": (
                "You are Jarvis, a fast local desktop assistant.\n"
                "When the user asks to open an application, "
                "use the apps.launch tool.\n"
                "Do not claim the action is complete before "
                "the tool result confirms it."
            ),
        },
        {
            "role": "user",
            "content": TEST_INPUT,
        },
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "apps.launch",
                "description": "Launch a desktop application.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Application name to launch.",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    started = time.perf_counter()

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=tools,
        think=True,
        stream=True,
        options={
            "num_ctx": 8192,
        },
    )

    thinking_parts = []
    content_parts = []

    candidate_time = None
    candidate_chars = None
    candidate_marker = None

    first_thinking_time = None
    first_tool_time = None

    last_reported_chars = 0

    for chunk in stream:
        now = time.perf_counter()

        message = chunk.message

        thinking = getattr(message, "thinking", "") or ""
        content = getattr(message, "content", "") or ""
        tool_calls = getattr(message, "tool_calls", None)

        if thinking:
            if first_thinking_time is None:
                first_thinking_time = now

            thinking_parts.append(thinking)

        if content:
            content_parts.append(content)

        accumulated_thinking = "".join(thinking_parts)

        # --------------------------------------------------------
        # Candidate commit detection
        # --------------------------------------------------------

        if candidate_time is None:
            candidate, marker = detect_candidate(
                accumulated_thinking
            )

            if candidate:
                candidate_time = now
                candidate_chars = len(accumulated_thinking)
                candidate_marker = marker

                print(
                    "\n[CANDIDATE COMMIT DETECTED]"
                )
                print(
                    f"  marker: {candidate_marker}"
                )
                print(
                    f"  time:   {candidate_time - started:.3f}s"
                )
                print(
                    f"  chars:  {candidate_chars}"
                )
                print(
                    f"  tokens: {estimate_tokens(accumulated_thinking):.0f}"
                )

        # --------------------------------------------------------
        # Actual structured tool call
        # --------------------------------------------------------

        if tool_calls:
            if first_tool_time is None:
                first_tool_time = now

                print(
                    "\n[STRUCTURED TOOL CALL DETECTED]"
                )

                for tool_call in tool_calls:
                    try:
                        safe_print(
                            json.dumps(
                                tool_call.model_dump(),
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    except Exception:
                        safe_print(tool_call)

            # We have what we need for this experiment.
            break

        # --------------------------------------------------------
        # Periodic progress output
        # --------------------------------------------------------

        if (
            len(accumulated_thinking)
            >= last_reported_chars + SAMPLE_CHARS
        ):
            last_reported_chars = len(accumulated_thinking)

            elapsed = now - started

            print(
                f"[TRACE] "
                f"{elapsed:.3f}s | "
                f"{len(accumulated_thinking)} chars | "
                f"~{estimate_tokens(accumulated_thinking):.0f} tokens"
            )

    total_time = time.perf_counter() - started

    thinking = "".join(thinking_parts)
    content = "".join(content_parts)

    candidate_gap = None

    if candidate_time is not None and first_tool_time is not None:
        candidate_gap = first_tool_time - candidate_time

    print("\n" + "-" * 70)
    print("RUN RESULT")
    print("-" * 70)

    print(f"Total time:       {total_time:.3f}s")
    print(f"Thinking chars:   {len(thinking)}")
    print(
        f"Thinking tokens:  "
        f"{estimate_tokens(thinking):.0f}"
    )

    if candidate_time is not None:
        print(
            f"Candidate time:   "
            f"{candidate_time - started:.3f}s"
        )
        print(
            f"Candidate tokens: "
            f"{estimate_tokens(thinking[:candidate_chars]):.0f}"
        )
        print(
            f"Candidate marker: "
            f"{candidate_marker}"
        )

    if first_tool_time is not None:
        print(
            f"Tool-call time:    "
            f"{first_tool_time - started:.3f}s"
        )

    if candidate_gap is not None:
        print(
            f"Candidate → tool: "
            f"{candidate_gap:.3f}s"
        )

    if content:
        safe_print(
            f"Content: {content}"
        )

    return {
        "run": run_number,
        "total_time": total_time,
        "thinking_chars": len(thinking),
        "thinking_tokens": estimate_tokens(thinking),
        "candidate_time": (
            candidate_time - started
            if candidate_time
            else None
        ),
        "candidate_tokens": (
            estimate_tokens(thinking[:candidate_chars])
            if candidate_chars
            else None
        ),
        "candidate_marker": candidate_marker,
        "tool_time": (
            first_tool_time - started
            if first_tool_time
            else None
        ),
        "candidate_gap": candidate_gap,
    }


def main():
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    settings = Settings()

    print("=" * 70)
    print("JARVIS — PHASE 1.1D")
    print("ADAPTIVE COMMIT BOUNDARY EXPERIMENT")
    print("=" * 70)

    print(f"Model:       {MODEL}")
    print(f"Ollama:      {OLLAMA_HOST}")
    print(f"Input:       {TEST_INPUT}")
    print(f"Think:       True")
    print()

    client = Client(host=OLLAMA_HOST)

    results = []

    for run_number in range(1, 6):
        result = run_once(
            client,
            run_number,
        )

        results.append(result)

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("PHASE 1.1D SUMMARY")
    print("=" * 70)

    valid_candidates = [
        r
        for r in results
        if r["candidate_time"] is not None
        and r["tool_time"] is not None
    ]

    print(
        f"Candidate detected: "
        f"{len(valid_candidates)}/{len(results)}"
    )

    if valid_candidates:
        candidate_times = [
            r["candidate_time"]
            for r in valid_candidates
        ]

        tool_times = [
            r["tool_time"]
            for r in valid_candidates
        ]

        gaps = [
            r["candidate_gap"]
            for r in valid_candidates
            if r["candidate_gap"] is not None
        ]

        candidate_tokens = [
            r["candidate_tokens"]
            for r in valid_candidates
        ]

        candidate_times.sort()
        tool_times.sort()
        gaps.sort()
        candidate_tokens.sort()

        def median(values):
            n = len(values)

            if n == 0:
                return None

            middle = n // 2

            if n % 2:
                return values[middle]

            return (
                values[middle - 1]
                + values[middle]
            ) / 2

        print(
            f"Median candidate time: "
            f"{median(candidate_times):.3f}s"
        )

        print(
            f"Median candidate tokens: "
            f"{median(candidate_tokens):.0f}"
        )

        print(
            f"Median tool-call time: "
            f"{median(tool_times):.3f}s"
        )

        print(
            f"Median candidate → tool gap: "
            f"{median(gaps):.3f}s"
        )

        print("\nInterpretation:")
        print(
            "A large candidate→tool gap means Qwen appears "
            "to have reached a stable decision before emitting "
            "the structured tool call."
        )

        print(
            "This is evidence for adaptive early commitment, "
            "NOT yet permission to interrupt production generation."
        )


if __name__ == "__main__":
    main()