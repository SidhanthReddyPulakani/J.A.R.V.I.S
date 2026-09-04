import json
import statistics
import time

import ollama

from jarvis.capabilities.bootstrap import build_default_registry


MODEL = "qwen3:4b"
NUM_CTX = 8192
RUNS = 5

SYSTEM_PROMPT = (
    "You are JARVIS. Use available capabilities to perform the "
    "user's requested action. When an action is clear, use the "
    "appropriate capability."
)

TASK = "Open WhatsApp."


def get_apps_launch_tool():
    registry = build_default_registry()

    for capability in registry.discover():
        if (
            capability.capability_name == "apps"
            and capability.operation_name == "launch"
        ):
            return capability.to_llm_tool_definition()

    raise RuntimeError("apps.launch capability not found")


def run_once(client, tool, think, prompt):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    started = time.perf_counter()

    first_chunk = None
    first_thinking = None
    first_content = None
    first_tool_call = None
    done_at = None

    thinking_chars = 0
    content_chars = 0
    tool_calls = []

    final_timing = {}

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=[tool],
        stream=True,
        think=think,
        options={
            "num_ctx": NUM_CTX,
        },
    )

    for chunk in stream:
        now = time.perf_counter() - started

        if first_chunk is None:
            first_chunk = now

        message = getattr(chunk, "message", None)

        if message is not None:
            thinking = getattr(message, "thinking", None)
            content = getattr(message, "content", None)
            chunk_tools = getattr(message, "tool_calls", None)

            if thinking:
                thinking_chars += len(thinking)

                if first_thinking is None:
                    first_thinking = now

            if content:
                content_chars += len(content)

                if first_content is None:
                    first_content = now

            if chunk_tools:
                if first_tool_call is None:
                    first_tool_call = now

                tool_calls.extend(chunk_tools)

        if getattr(chunk, "done", False):
            done_at = now

            for field in (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            ):
                value = getattr(chunk, field, None)

                if value is not None:
                    final_timing[field] = value

    total = (
        done_at
        if done_at is not None
        else time.perf_counter() - started
    )

    post_commit = (
        total - first_tool_call
        if first_tool_call is not None
        else None
    )

    correct_calls = 0

    for tool_call in tool_calls:
        function = getattr(tool_call, "function", None)

        if function is None:
            continue

        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)

        if (
            name == "apps.launch"
            and isinstance(arguments, dict)
            and arguments.get("query") == "WhatsApp"
        ):
            correct_calls += 1

    return {
        "first_chunk": first_chunk,
        "first_thinking": first_thinking,
        "first_content": first_content,
        "first_tool_call": first_tool_call,
        "done": done_at,
        "total": total,
        "post_commit": post_commit,
        "thinking_chars": thinking_chars,
        "content_chars": content_chars,
        "tool_calls": tool_calls,
        "correct_calls": correct_calls,
        "timing": final_timing,
    }


def summarize(results):
    def values(key):
        return [
            r[key]
            for r in results
            if r[key] is not None
        ]

    def fmt(key):
        v = values(key)

        if not v:
            return "n/a"

        return (
            f"median={statistics.median(v):.3f}s "
            f"mean={statistics.mean(v):.3f}s "
            f"min={min(v):.3f}s "
            f"max={max(v):.3f}s"
        )

    thinking = [
        r["thinking_chars"]
        for r in results
    ]

    correct = sum(
        1
        for r in results
        if r["correct_calls"] == 1
    )

    print(f"  first chunk:     {fmt('first_chunk')}")
    print(f"  first thinking:  {fmt('first_thinking')}")
    print(f"  first content:   {fmt('first_content')}")
    print(f"  first tool:      {fmt('first_tool_call')}")
    print(f"  total:           {fmt('total')}")
    print(f"  post-commit:     {fmt('post_commit')}")

    print(
        f"  thinking chars:  "
        f"median={statistics.median(thinking):.0f} "
        f"mean={statistics.mean(thinking):.0f} "
        f"min={min(thinking)} "
        f"max={max(thinking)}"
    )

    print(f"  correct calls:   {correct}/{len(results)}")


def run_condition(client, tool, name, think, prompt):
    print()
    print("=" * 72)
    print(name)
    print("=" * 72)
    print(f"think={think}")
    print(f"task={TASK!r}")
    print()

    results = []

    for run_number in range(1, RUNS + 1):
        print(f"RUN {run_number}/{RUNS}")

        result = run_once(
            client,
            tool,
            think,
            prompt,
        )

        results.append(result)

        print(
            f"  tool={result['first_tool_call']!s:>8} "
            f"done={result['done']!s:>8} "
            f"total={result['total']:.3f}s "
            f"thinking={result['thinking_chars']} "
            f"correct={result['correct_calls']}"
        )

        if result["tool_calls"]:
            print(
                "  calls:",
                json.dumps(
                    [
                        {
                            "name": getattr(
                                getattr(tc, "function", None),
                                "name",
                                None,
                            ),
                            "arguments": getattr(
                                getattr(tc, "function", None),
                                "arguments",
                                None,
                            ),
                        }
                        for tc in result["tool_calls"]
                    ],
                    indent=2,
                ),
            )

    print()
    print("--- SUMMARY ---")
    summarize(results)

    return results


def main():
    client = ollama.Client()
    tool = get_apps_launch_tool()

    print("=" * 72)
    print("JARVIS REASONING / STREAMING BASELINE")
    print("=" * 72)
    print(f"model={MODEL}")
    print(f"num_ctx={NUM_CTX}")
    print(f"runs={RUNS}")
    print(f"task={TASK!r}")

    all_results = {}

    # A: No reasoning.
    all_results["A_think_false"] = run_condition(
        client,
        tool,
        "A — THINK FALSE",
        False,
        TASK,
    )

    # B: Normal Qwen reasoning.
    all_results["B_think_true"] = run_condition(
        client,
        tool,
        "B — THINK TRUE",
        True,
        TASK,
    )

    # C: Prompt steering control.
    strong_commit_prompt = (
        f"{TASK}\n\n"
        "Reason only as much as necessary to identify the correct "
        "capability and arguments. For this request, once you have "
        "identified a valid operation, immediately call the capability. "
        "Do not explain, validate, reconsider, or continue reasoning "
        "after the operation is determined."
    )

    all_results["C_strong_commit"] = run_condition(
        client,
        tool,
        "C — THINK TRUE + STRONG COMMIT CONTROL",
        True,
        strong_commit_prompt,
    )

    print()
    print("=" * 72)
    print("FINAL COMPARISON")
    print("=" * 72)

    for name, results in all_results.items():
        tool_times = [
            r["first_tool_call"]
            for r in results
            if r["first_tool_call"] is not None
        ]

        total_times = [
            r["total"]
            for r in results
        ]

        post_commit = [
            r["post_commit"]
            for r in results
            if r["post_commit"] is not None
        ]

        thinking = [
            r["thinking_chars"]
            for r in results
        ]

        correct = sum(
            1
            for r in results
            if r["correct_calls"] == 1
        )

        print(f"\n{name}")
        print(
            f"  TTFC:          "
            f"{statistics.median(tool_times):.3f}s median"
            if tool_times
            else "  TTFC:          n/a"
        )
        print(
            f"  total:         "
            f"{statistics.median(total_times):.3f}s median"
        )
        print(
            f"  post-commit:   "
            f"{statistics.median(post_commit):.3f}s median"
            if post_commit
            else "  post-commit:   n/a"
        )
        print(
            f"  thinking:      "
            f"{statistics.median(thinking):.0f} chars median"
        )
        print(
            f"  correct calls: {correct}/{len(results)}"
        )


if __name__ == "__main__":
    main()


def test_reasoning_stream_experiment():
    main()