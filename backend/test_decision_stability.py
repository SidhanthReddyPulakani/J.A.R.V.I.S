import sys
import time
import json
import re

from ollama import Client


MODEL = "qwen3:4b"
OLLAMA_HOST = "http://127.0.0.1:11434"

# ------------------------------------------------------------
# Test cases
# ------------------------------------------------------------

TESTS = [
    {
        "name": "simple",
        "input": "Open WhatsApp.",
    },
    {
        "name": "ambiguous",
        "input": "Open the messaging app.",
    },
    {
        "name": "multi_step",
        "input": "Find WhatsApp, then open it.",
    },
    {
        "name": "evidence",
        "input": (
            "Find applications matching the name WhatsApp, "
            "then tell me whether search returned exactly one "
            "match, more than one match, or no matches."
        ),
    },
]


# ------------------------------------------------------------
# Tool definition
# ------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apps.find",
            "description": "Find desktop applications matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                    }
                },
                "required": ["query"],
            },
        },
    },
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
                    }
                },
                "required": ["query"],
            },
        },
    },
]


SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Use desktop tools when the user's request requires an action.

Available tools:
- apps.find: find applications
- apps.launch: launch an application

Do not claim an action was completed before the tool result confirms it.

Think through the task before selecting a tool.
"""


def safe_print(value):
    try:
        print(value)
    except UnicodeEncodeError:
        print(
            str(value)
            .encode("utf-8", errors="replace")
            .decode("utf-8")
        )


# ------------------------------------------------------------
# Candidate extraction
# ------------------------------------------------------------

def normalize_candidate(text):
    """
    Convert reasoning text into a coarse candidate action.

    This is intentionally experimental. We want to observe
    whether the model's intended action changes over time.
    """

    lowered = text.lower()

    # launch WhatsApp
    if (
        "apps.launch" in lowered
        and "whatsapp" in lowered
    ):
        return "apps.launch(WhatsApp)"

    # find WhatsApp
    if (
        "apps.find" in lowered
        and "whatsapp" in lowered
    ):
        return "apps.find(WhatsApp)"

    # generic launch
    if "launch" in lowered:
        return "apps.launch(?)"

    # generic find
    if "find" in lowered:
        return "apps.find(?)"

    return None


def extract_tool_call(tool_calls):
    if not tool_calls:
        return None

    for call in tool_calls:
        try:
            function = call.function

            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", None)

            if hasattr(arguments, "model_dump"):
                arguments = arguments.model_dump()

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    pass

            return {
                "name": name,
                "arguments": arguments,
            }

        except Exception:
            return str(call)

    return None


# ------------------------------------------------------------
# Stability experiment
# ------------------------------------------------------------

def run_test(client, test_number, test):
    print("\n" + "=" * 75)
    print(f"TEST {test_number}: {test['name']}")
    print("=" * 75)
    print(f"Input: {test['input']}")

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": test["input"],
        },
    ]

    started = time.perf_counter()

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        think=True,
        stream=True,
        options={
            "num_ctx": 8192,
        },
    )

    thinking_parts = []

    observations = []

    current_candidate = None
    candidate_since = None

    first_candidate_time = None
    stable_candidate_time = None
    stable_candidate = None

    first_tool_time = None
    final_tool = None

    # --------------------------------------------------------
    # Stability parameters
    # --------------------------------------------------------

    # Number of consecutive observations required before
    # considering a candidate stable.
    STABILITY_COUNT = 3

    consecutive_count = 0

    # --------------------------------------------------------
    # Stream
    # --------------------------------------------------------

    for chunk in stream:
        now = time.perf_counter()

        message = chunk.message

        thinking = getattr(message, "thinking", "") or ""
        tool_calls = getattr(message, "tool_calls", None)

        if thinking:
            thinking_parts.append(thinking)

        accumulated = "".join(thinking_parts)

        candidate = normalize_candidate(accumulated)

        # ----------------------------------------------------
        # Candidate tracking
        # ----------------------------------------------------

        if candidate:

            if first_candidate_time is None:
                first_candidate_time = now

                print(
                    "\n[FIRST CANDIDATE]"
                )
                print(
                    f"  {candidate}"
                )
                print(
                    f"  t={now - started:.3f}s"
                )

            if candidate == current_candidate:
                consecutive_count += 1
            else:
                current_candidate = candidate
                consecutive_count = 1
                candidate_since = now

                print(
                    f"[CANDIDATE CHANGE] "
                    f"{candidate}"
                )

            observations.append(
                {
                    "time": now - started,
                    "candidate": candidate,
                    "count": consecutive_count,
                }
            )

            # ------------------------------------------------
            # Stability threshold
            # ------------------------------------------------

            if (
                consecutive_count >= STABILITY_COUNT
                and stable_candidate_time is None
            ):
                stable_candidate_time = now
                stable_candidate = candidate

                print(
                    "\n[STABLE DECISION DETECTED]"
                )
                print(
                    f"  candidate: {stable_candidate}"
                )
                print(
                    f"  t={now - started:.3f}s"
                )
                print(
                    f"  consecutive observations: "
                    f"{consecutive_count}"
                )
                print(
                    f"  thinking chars: "
                    f"{len(accumulated)}"
                )

        # ----------------------------------------------------
        # Structured tool call
        # ----------------------------------------------------

        tool = extract_tool_call(tool_calls)

        if tool:
            first_tool_time = now
            final_tool = tool

            print(
                "\n[STRUCTURED TOOL CALL]"
            )
            safe_print(
                json.dumps(
                    tool,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            break

    total_time = time.perf_counter() - started

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print("\n" + "-" * 75)
    print("RESULT")
    print("-" * 75)

    print(f"Total time: {total_time:.3f}s")

    if first_candidate_time:
        print(
            f"First candidate: "
            f"{first_candidate_time - started:.3f}s"
        )

    if stable_candidate_time:
        print(
            f"Stable candidate: "
            f"{stable_candidate_time - started:.3f}s"
        )
        print(
            f"Stable decision: "
            f"{stable_candidate}"
        )

    if first_tool_time:
        print(
            f"Structured tool: "
            f"{first_tool_time - started:.3f}s"
        )

    if (
        stable_candidate_time is not None
        and first_tool_time is not None
    ):
        print(
            f"Stable → tool gap: "
            f"{first_tool_time - stable_candidate_time:.3f}s"
        )

    print(
        f"Thinking chars: "
        f"{len(''.join(thinking_parts))}"
    )

    return {
        "name": test["name"],
        "total_time": total_time,
        "first_candidate": (
            first_candidate_time - started
            if first_candidate_time
            else None
        ),
        "stable_candidate": (
            stable_candidate_time - started
            if stable_candidate_time
            else None
        ),
        "stable_decision": stable_candidate,
        "tool_time": (
            first_tool_time - started
            if first_tool_time
            else None
        ),
        "tool": final_tool,
        "thinking_chars": len(
            "".join(thinking_parts)
        ),
        "observations": observations,
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    print("=" * 75)
    print("JARVIS — PHASE 1.1E")
    print("DECISION STABILITY DETECTION")
    print("=" * 75)

    print(f"Model: {MODEL}")
    print(f"Ollama: {OLLAMA_HOST}")
    print(
        "Stability threshold: "
        "3 consecutive observations"
    )

    client = Client(
        host=OLLAMA_HOST
    )

    results = []

    for index, test in enumerate(TESTS, start=1):
        result = run_test(
            client,
            index,
            test,
        )

        results.append(result)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 75)
    print("PHASE 1.1E SUMMARY")
    print("=" * 75)

    for result in results:
        print("\n" + result["name"])

        print(
            f"  total: "
            f"{result['total_time']:.3f}s"
        )

        if result["first_candidate"] is not None:
            print(
                f"  first candidate: "
                f"{result['first_candidate']:.3f}s"
            )

        if result["stable_candidate"] is not None:
            print(
                f"  stable candidate: "
                f"{result['stable_candidate']:.3f}s"
            )

        if result["tool_time"] is not None:
            print(
                f"  tool call: "
                f"{result['tool_time']:.3f}s"
            )

        if (
            result["stable_candidate"] is not None
            and result["tool_time"] is not None
        ):
            print(
                f"  stable → tool: "
                f"{result['tool_time'] - result['stable_candidate']:.3f}s"
            )

        print(
            f"  decision: "
            f"{result['stable_decision']}"
        )

        print(
            f"  final tool: "
            f"{result['tool']}"
        )

    print("\n" + "=" * 75)
    print("IMPORTANT")
    print("=" * 75)
    print(
        "This experiment does NOT interrupt generation."
    )
    print(
        "It only measures whether a decision becomes "
        "stable before the structured tool call."
    )
    print(
        "A stable decision is evidence for an adaptive "
        "commit controller, not yet a safe execution rule."
    )


if __name__ == "__main__":
    main()