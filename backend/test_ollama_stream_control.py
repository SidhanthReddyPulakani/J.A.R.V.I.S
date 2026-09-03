import json
import time

import ollama

from jarvis.capabilities.bootstrap import build_default_registry


PROMPTS = [
    (
        "strong_commit",
        (
            "Hello Jarvis.\n\n"
            "Reason only as much as necessary to identify the correct "
            "capability and arguments. For this request, once you have "
            "identified a valid operation, immediately call the capability. "
            "Do not explain, validate, reconsider, or continue reasoning "
            "after the operation is determined."
        ),
    ),
]

def get_apps_launch_tool():
    registry = build_default_registry()

    for capability in registry.discover():
        if (
            capability.capability_name == "apps"
            and capability.operation_name == "launch"
        ):
            return capability.to_llm_tool_definition()

    raise RuntimeError("apps.launch capability not found")

def run_once(client, tool, prompt):
    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS. Use available capabilities to perform the "
                "user's requested action. When an action is clear, use the "
                "appropriate capability."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    first_thinking = None
    first_tool_call = None
    done_at = None

    thinking_chars = 0
    content_chars = 0
    tool_calls = []

    started = time.perf_counter()

    stream = client.chat(
        model="qwen3:4b",
        messages=messages,
        tools=[tool],
        stream=True,
        think=True,
        options={
            "num_ctx": 8192,
        },
    )

    for chunk in stream:
        now = time.perf_counter() - started

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

            if chunk_tools:
                if first_tool_call is None:
                    first_tool_call = now

                    print("\n>>> TOOL CALL DETECTED")
                    print(
                        json.dumps(
                            [
                                {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                                for tc in chunk_tools
                            ],
                            indent=2,
                        )
                    )

                tool_calls.extend(chunk_tools)

        if getattr(chunk, "done", False):
            done_at = now

    return {
        "first_thinking": first_thinking,
        "first_tool_call": first_tool_call,
        "done": done_at,
        "total": time.perf_counter() - started,
        "thinking_chars": thinking_chars,
        "content_chars": content_chars,
        "tool_calls": tool_calls,
    }


def main():
    client = ollama.Client()

    tool = get_apps_launch_tool()

    print("=" * 70)
    print("QWEN3 THINKING CONTROL MEASUREMENT")
    print("=" * 70)

    all_results = []

    for prompt_name, prompt in PROMPTS:
        print("\n")
        print("=" * 70)
        print(f"PROMPT: {prompt_name}")
        print("=" * 70)
        print(prompt)

        results = []

        for run_number in range(1, 6):
            print("\n" + "-" * 70)
            print(f"RUN {run_number}/5")
            print("-" * 70)

            result = run_once(client, tool, prompt)

            results.append(result)

            print("\n--- RESULT ---")
            print(f"first thinking:  {result['first_thinking']}")
            print(f"first tool:      {result['first_tool_call']}")
            print(f"done:            {result['done']}")
            print(f"total:           {result['total']:.3f}s")
            print(f"thinking chars:  {result['thinking_chars']}")
            print(f"content chars:   {result['content_chars']}")

        all_results.append(
            {
                "name": prompt_name,
                "results": results,
            }
        )

    print("\n")
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for group in all_results:
        print(f"\n{group['name']}")

        for i, result in enumerate(group["results"], 1):
            print(
                f"  run {i}: "
                f"tool={result['first_tool_call']:.3f}s, "
                f"done={result['done']:.3f}s, "
                f"thinking={result['thinking_chars']}"
            )


def test_ollama_think_control():
    main()