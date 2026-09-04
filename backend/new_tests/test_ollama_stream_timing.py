import time
import json
import ollama

from jarvis.capabilities.bootstrap import build_default_registry


MODEL = "qwen3:4b"


def get_apps_launch_tool():
    registry = build_default_registry()

    for capability in registry.discover():
        if (
            capability.capability_name == "apps"
            and capability.operation_name == "launch"
        ):
            return capability.to_llm_tool_definition()

    raise RuntimeError("apps.launch capability not found")

def run_stream(think: bool):
    client = ollama.Client()
    tool = get_apps_launch_tool()

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS. "
                "When the user asks to open an application, "
                "use the apps.launch tool. "
                "Do not execute the tool yourself."
            ),
        },
        {
            "role": "user",
            "content": "Open WhatsApp",
        },
    ]

    print()
    print("=" * 70)
    print(f"THINK = {think}")
    print("=" * 70)

    started = time.perf_counter()

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=[tool],
        stream=True,
        think=think,
        options={
            "num_ctx": 8192,
        },
    )

    first_chunk_at = None
    first_thinking_at = None
    first_content_at = None
    first_tool_call_at = None
    done_at = None

    chunk_count = 0
    thinking_chars = 0
    content_chars = 0

    for chunk in stream:
        now = time.perf_counter()
        elapsed = now - started

        chunk_count += 1

        message = getattr(chunk, "message", None)

        thinking = getattr(message, "thinking", None)
        content = getattr(message, "content", None)
        tool_calls = getattr(message, "tool_calls", None)
        done = getattr(chunk, "done", False)

        if first_chunk_at is None:
            first_chunk_at = elapsed

        if thinking:
            thinking_chars += len(thinking)
            if first_thinking_at is None:
                first_thinking_at = elapsed

        if content:
            content_chars += len(content)
            if first_content_at is None:
                first_content_at = elapsed

        if tool_calls and first_tool_call_at is None:
            first_tool_call_at = elapsed

            print()
            print(">>> TOOL CALL DETECTED")
            print(
                json.dumps(
                    [
                        {
                            "name": getattr(tc.function, "name", None),
                            "arguments": getattr(
                                tc.function,
                                "arguments",
                                None,
                            ),
                        }
                        for tc in tool_calls
                    ],
                    indent=2,
                    default=str,
                )
            )

        if done:
            done_at = elapsed

        print(
            f"{elapsed:8.3f}s | "
            f"chunk={chunk_count:3d} | "
            f"thinking={len(thinking or ''):4d} | "
            f"content={len(content or ''):4d} | "
            f"tools={bool(tool_calls)} | "
            f"done={done}"
        )

    total = time.perf_counter() - started

    print()
    print("--- SUMMARY ---")
    print(f"think:                 {think}")
    print(f"first chunk:           {first_chunk_at}")
    print(f"first thinking:        {first_thinking_at}")
    print(f"first content:         {first_content_at}")
    print(f"first tool call:       {first_tool_call_at}")
    print(f"done:                  {done_at}")
    print(f"total:                 {total:.3f}s")
    print(f"chunks:                {chunk_count}")
    print(f"thinking chars:        {thinking_chars}")
    print(f"content chars:         {content_chars}")

    return {
        "think": think,
        "first_chunk": first_chunk_at,
        "first_thinking": first_thinking_at,
        "first_content": first_content_at,
        "first_tool_call": first_tool_call_at,
        "done": done_at,
        "total": total,
        "chunks": chunk_count,
        "thinking_chars": thinking_chars,
        "content_chars": content_chars,
    }


def test_compare_thinking_modes():
    false_result = run_stream(False)
    true_result = run_stream(True)

    print()
    print("=" * 70)
    print("COMPARISON")
    print("=" * 70)

    for key in (
        "first_chunk",
        "first_thinking",
        "first_content",
        "first_tool_call",
        "done",
        "total",
        "chunks",
        "thinking_chars",
        "content_chars",
    ):
        print(
            f"{key:20s} | "
            f"False={false_result[key]} | "
            f"True={true_result[key]}"
        )

    assert false_result["first_tool_call"] is not None
    assert true_result["first_tool_call"] is not None