from __future__ import annotations

import json
import statistics
import time
from typing import Any

import ollama

from jarvis.capabilities.bootstrap import build_default_registry
from jarvis.capabilities.controller import CapabilityController
from jarvis.core.capability_request import CapabilityRequest

MODEL = "qwen3:4b"

SYSTEM_PROMPT = """
You are Jarvis, a fast local desktop assistant.

Priorities:
- Be concise.
- Use tools for desktop action.
- If the user asks to open, launch, run, or start an app, use apps.launch with the app name as query.
- Do not say you can't launch something.
- Do not claim an action completed unless the tool result confirms it.
- If a tool reports failure, use the result to decide what to do next.
- Do not explain internal reasoning.
- Simple commands should be brief.
""".strip()


TASK = (
    "Find applications matching the name WhatsApp, then tell me whether "
    "the search returned exactly one match, more than one match, or no matches."
)


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def extract_tool_call(message: Any) -> tuple[str | None, dict[str, Any] | None]:
    tool_calls = getattr(message, "tool_calls", None) or []

    if not tool_calls:
        return None, None

    call = tool_calls[0]

    function = getattr(call, "function", None)
    if function is None:
        return None, None

    name = getattr(function, "name", None)
    arguments = getattr(function, "arguments", None)

    if arguments is None:
        arguments = {}

    if not isinstance(arguments, dict):
        try:
            arguments = json.loads(arguments)
        except Exception:
            arguments = {}

    return name, arguments


def stream_generation(
    client: ollama.Client,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    start = now_ms()

    first_chunk = None
    first_thinking = None
    first_content = None
    tool_call_time = None

    thinking_parts: list[str] = []
    content_parts: list[str] = []

    final_message = None

    stream = client.chat(
        model=MODEL,
        messages=messages,
        tools=build_tools(),
        stream=True,
        think=True,
    )

    for chunk in stream:
        t = now_ms()

        if first_chunk is None:
            first_chunk = t

        message = chunk.get("message")

        if message is None:
            continue

        thinking = getattr(message, "thinking", None)
        content = getattr(message, "content", None)

        if thinking:
            if first_thinking is None:
                first_thinking = t
            thinking_parts.append(thinking)

        if content:
            if first_content is None:
                first_content = t
            content_parts.append(content)

        calls = getattr(message, "tool_calls", None) or []

        if calls and tool_call_time is None:
            tool_call_time = t
            final_message = message
            break

        final_message = message

    end = now_ms()

    tool_name = None
    tool_arguments = None

    if final_message is not None:
        tool_name, tool_arguments = extract_tool_call(final_message)

    return {
        "first_chunk_ms": (
            None if first_chunk is None else first_chunk - start
        ),
        "first_thinking_ms": (
            None if first_thinking is None else first_thinking - start
        ),
        "first_content_ms": (
            None if first_content is None else first_content - start
        ),
        "tool_call_ms": (
            None if tool_call_time is None else tool_call_time - start
        ),
        "elapsed_ms": end - start,
        "thinking": "".join(thinking_parts),
        "content": "".join(content_parts),
        "tool_name": tool_name,
        "tool_arguments": tool_arguments,
        "message": final_message,
    }


def build_tools():
    registry = build_default_registry()

    return [
        {
            "type": "function",
            "function": {
                "name": definition.address,
                "description": definition.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        parameter.name: {
                            "type": "string"
                        }
                        for parameter in definition.schema.inputs
                    },
                    "required": [
                        parameter.name
                        for parameter in definition.schema.inputs
                        if parameter.required
                    ],
                },
            },
        }
        for definition in registry.discover()
    ]



def execute_capability(
    tool_name: str,
    arguments: dict[str, Any],
):
    registry = build_default_registry()
    controller = CapabilityController(registry)

    request = CapabilityRequest(
        operation=tool_name,
        arguments=arguments,
        step=1,
    )

    return controller.execute(request)

def make_result_message(result) -> dict[str, Any]:
    return {
        "role": "tool",
        "content": json.dumps(
            {
                "operation": result.operation,
                "status": result.status.value
                if hasattr(result.status, "value")
                else str(result.status),
                "state": result.state.value
                if hasattr(result.state, "value")
                else str(result.state),
                "data": result.data,
                "error_code": (
                    result.error_code.value
                    if hasattr(result.error_code, "value")
                    else str(result.error_code)
                    if result.error_code is not None
                    else None
                ),
                "error_message": result.error_message,
            },
            ensure_ascii=False,
        ),
    }


def run_once(run_number: int):
    client = ollama.Client()

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

    print()
    print("=" * 80)
    print(f"RUN {run_number}")
    print("=" * 80)

    print("\nUSER:")
    print(TASK)

    first = stream_generation(client, messages)

    print("\n--- FIRST GENERATION ---")
    print(f"tool:              {first['tool_name']}")
    print(f"arguments:         {first['tool_arguments']}")
    print(f"first chunk:       {first['first_chunk_ms']:.1f} ms")
    print(f"first thinking:    {first['first_thinking_ms']:.1f} ms")
    print(f"tool call:         {first['tool_call_ms']:.1f} ms")
    print(f"generation total:  {first['elapsed_ms']:.1f} ms")
    print(f"thinking chars:    {len(first['thinking'])}")

    print("\nTHINKING BEFORE TOOL:")
    print(first["thinking"])

    if first["tool_name"] != "apps.find":
        print("\nERROR: Expected apps.find.")
        return {
            "success": False,
            "reason": "wrong_first_tool",
            "first": first,
        }

    query = first["tool_arguments"].get("query")

    if not query:
        print("\nERROR: apps.find had no query.")
        return {
            "success": False,
            "reason": "missing_query",
            "first": first,
        }

    result = execute_capability(
        "apps.find",
        {"query": query},
    )

    print("\n--- ACTUAL TOOL RESULT ---")
    print(f"operation: {result.operation}")
    print(f"status:    {result.status}")
    print(f"state:     {result.state}")
    print(f"data:      {result.data}")
    print(f"error:     {result.error_message}")

    messages.append(
        {
            "role": "assistant",
            "content": first["content"],
            "tool_calls": [
                {
                    "function": {
                        "name": first["tool_name"],
                        "arguments": first["tool_arguments"],
                    }
                }
            ],
        }
    )

    messages.append(
        make_result_message(result)
    )

    second = stream_generation(client, messages)

    print("\n--- SECOND GENERATION ---")
    print(f"next tool:          {second['tool_name']}")
    print(f"next arguments:     {second['tool_arguments']}")
    print(f"first chunk:        {second['first_chunk_ms']:.1f} ms")
    print(f"first thinking:     {second['first_thinking_ms']:.1f} ms")
    print(f"next tool call:     {second['tool_call_ms']}")
    print(f"generation total:   {second['elapsed_ms']:.1f} ms")
    print(f"thinking chars:     {len(second['thinking'])}")

    print("\nTHINKING AFTER EVIDENCE:")
    print(second["thinking"])

    print("\nFINAL CONTENT:")
    print(second["content"])

    unnecessary_tool = second["tool_name"] is not None

    success = (
        first["tool_name"] == "apps.find"
        and bool(query)
        and not unnecessary_tool
        and bool(second["content"].strip())
    )

    print("\n--- VERDICT ---")
    print(f"correct first tool:       {first['tool_name'] == 'apps.find'}")
    print(f"tool query present:       {bool(query)}")
    print(f"final answer produced:    {bool(second['content'].strip())}")
    print(f"unnecessary second tool:  {unnecessary_tool}")
    print(f"PASS:                     {success}")

    return {
        "success": success,
        "first": first,
        "second": second,
        "result_state": str(result.state),
        "result_data": result.data,
    }


def main():
    runs = 5
    results = []

    for i in range(1, runs + 1):
        try:
            results.append(run_once(i))
        except Exception as exc:
            print()
            print("=" * 80)
            print(f"RUN {i} FAILED WITH EXCEPTION")
            print("=" * 80)
            print(repr(exc))
            results.append({
                "success": False,
                "reason": "exception",
                "error": repr(exc),
            })

    successful = [r for r in results if r.get("success")]

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"runs:          {runs}")
    print(f"successful:    {len(successful)}/{runs}")
    print(f"success rate:  {len(successful) / runs * 100:.1f}%")

    first_tools = [
        r["first"]["tool_call_ms"]
        for r in results
        if "first" in r and r["first"]["tool_call_ms"] is not None
    ]

    second_times = [
        r["second"]["elapsed_ms"]
        for r in results
        if "second" in r
    ]

    second_thinking = [
        len(r["second"]["thinking"])
        for r in results
        if "second" in r
    ]

    unnecessary = [
        r["second"]["tool_name"] is not None
        for r in results
        if "second" in r
    ]

    if first_tools:
        print(
            f"first tool median:       "
            f"{statistics.median(first_tools):.1f} ms"
        )

    if second_times:
        print(
            f"post-evidence median:    "
            f"{statistics.median(second_times):.1f} ms"
        )

    if second_thinking:
        print(
            f"post-evidence thinking:   "
            f"{statistics.median(second_thinking):.0f} chars"
        )

    if unnecessary:
        print(
            f"unnecessary tool calls:   "
            f"{sum(unnecessary)}/{len(unnecessary)}"
        )


if __name__ == "__main__":
    main()