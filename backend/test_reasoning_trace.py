
import json
import time

import ollama

from jarvis.capabilities.bootstrap import build_default_registry


MODEL = "qwen3:4b"
NUM_CTX = 8192
RUNS = 5

SYSTEM_PROMPT = (
    "You are Jarvis, a fast local desktop assistant.\n\n"
    "Your priorities:\n"
    "1. Be concise and conversational.\n"
    "2. Use tools whenever the user's request requires a desktop action.\n"
    "3. When the user asks you to open, launch, run, or start an application, "
    "use the `apps.launch` tool with the application's name as the `query`.\n"
    "4. Do not tell the user that you cannot launch desktop applications "
    "when an appropriate tool is available.\n"
    "5. Never claim an action was completed unless the tool result confirms it.\n"
    "6. If a tool reports failure, use that result to decide what to do next.\n"
    "7. Do not explain your internal reasoning.\n"
    "8. For simple commands, respond briefly.\n"
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


def run_once(client, tool):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": TASK,
        },
    ]

    started = time.perf_counter()

    thinking_parts = []
    content_parts = []
    tool_calls = []

    first_tool_time = None
    done_time = None

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=[tool],
        stream=True,
        think=True,
        options={
            "num_ctx": NUM_CTX,
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
                thinking_parts.append(thinking)

            if content:
                content_parts.append(content)

            if chunk_tools:
                if first_tool_time is None:
                    first_tool_time = now

                tool_calls.extend(chunk_tools)

                # The first tool call is the important boundary.
                # Stop printing/collecting reasoning after this point.
                break

        if getattr(chunk, "done", False):
            done_time = now
            break

    thinking_text = "".join(thinking_parts)
    content_text = "".join(content_parts)

    return {
        "first_tool_time": first_tool_time,
        "done_time": done_time,
        "thinking": thinking_text,
        "content": content_text,
        "thinking_chars": len(thinking_text),
        "tool_calls": tool_calls,
    }


def format_tool_calls(tool_calls):
    formatted = []

    for tc in tool_calls:
        function = getattr(tc, "function", None)

        formatted.append(
            {
                "name": getattr(function, "name", None),
                "arguments": getattr(function, "arguments", None),
            }
        )

    return formatted


def main():
    client = ollama.Client()
    tool = get_apps_launch_tool()

    print("=" * 80)
    print("JARVIS QWEN3 REASONING TRACE")
    print("=" * 80)
    print(f"model: {MODEL}")
    print(f"num_ctx: {NUM_CTX}")
    print(f"task: {TASK!r}")
    print(f"runs: {RUNS}")

    for run_number in range(1, RUNS + 1):
        print()
        print("=" * 80)
        print(f"RUN {run_number}/{RUNS}")
        print("=" * 80)

        result = run_once(client, tool)

        print()
        print("--- TIMING ---")
        print(f"first tool: {result['first_tool_time']}")
        print(f"done:       {result['done_time']}")

        print()
        print("--- THINKING BEFORE FIRST TOOL CALL ---")
        print(result["thinking"] or "<NO THINKING>")

        print()
        print("--- CONTENT BEFORE FIRST TOOL CALL ---")
        print(result["content"] or "<NO CONTENT>")

        print()
        print("--- TOOL CALL ---")
        print(
            json.dumps(
                format_tool_calls(result["tool_calls"]),
                indent=2,
            )
        )

        print()
        print("--- MEASUREMENTS ---")
        print(f"thinking chars: {result['thinking_chars']}")

        if result["first_tool_time"] is not None:
            print(
                f"thinking → tool: "
                f"{result['first_tool_time']:.3f}s"
            )

    print()
    print("=" * 80)
    print("TRACE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

