"""
Phase 1.1A — Qwen/Ollama Thinking Diagnostic

Purpose
-------
Determine exactly where Qwen reasoning appears when JARVIS is configured
with think=False versus think=True.

This test does NOT modify JarvisAgent, LLMClient, or production code.

Run from:
    backend/

Command:
    python test_qwen_thinking_diagnostic.py
"""

from __future__ import annotations

import sys
import time
from typing import Any

from ollama import Client

from jarvis.core.agent import JarvisAgent
from jarvis.core.config import Settings


# ============================================================
# CONFIGURATION
# ============================================================

TEST_INPUT = "Hey Jarvis"

# We keep this small for the first diagnostic.
# The goal is to understand the response structure, not benchmark
# long reasoning yet.
NUM_RUNS = 1


# ============================================================
# HELPERS
# ============================================================

def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """
    Safely retrieve an attribute from Ollama response/message objects.
    """
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def summarize_text(text: Any, limit: int = 500) -> str:
    """
    Produce a readable preview without dumping enormous model output.
    """
    if text is None:
        return ""

    text = str(text)

    if len(text) <= limit:
        return text

    return text[:limit] + "... [truncated]"


def count_think_tags(text: str) -> dict[str, int]:
    """
    Count explicit Qwen-style think tags in ordinary content.
    """
    return {
        "think_open": text.count("<think>"),
        "think_close": text.count("</think>"),
    }


# ============================================================
# SINGLE EXPERIMENT
# ============================================================

def run_experiment(
    client: Client,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[Any],
    think: bool,
) -> None:

    print()
    print("=" * 78)
    print(f"THINK = {think}")
    print("=" * 78)

    started = time.perf_counter()

    try:
        response = client.chat(
            model=model,
            messages=messages,
            tools=tools,
            stream=False,
            think=think,
            keep_alive=Settings().keep_alive,
            options={
                "num_ctx": Settings().context_size,
            },
        )

    except Exception as exc:
        elapsed = time.perf_counter() - started

        print()
        print("[ERROR] Ollama request failed.")
        print(f"Elapsed: {elapsed:.3f}s")
        print(f"Exception: {type(exc).__name__}: {exc}")
        return

    elapsed = time.perf_counter() - started

    message = response.message

    # --------------------------------------------------------
    # Raw response fields
    # --------------------------------------------------------

    content = get_attr(message, "content", "")
    thinking = get_attr(message, "thinking", None)
    tool_calls = get_attr(message, "tool_calls", None)

    # Some Ollama/client versions may expose additional metadata.
    response_dict = None

    try:
        response_dict = dict(response)
    except Exception:
        pass

    # --------------------------------------------------------
    # Convert fields to safe strings
    # --------------------------------------------------------

    content_text = "" if content is None else str(content)

    if thinking is None:
        thinking_text = ""
    else:
        thinking_text = str(thinking)

    # --------------------------------------------------------
    # Tag inspection
    # --------------------------------------------------------

    content_tags = count_think_tags(content_text)

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print()
    print("[TIMING]")
    print(f"Total chat latency : {elapsed:.3f}s")

    print()
    print("[MESSAGE FIELDS]")
    print(
        "content present   :",
        bool(content_text),
    )
    print(
        "thinking present  :",
        bool(thinking_text),
    )
    print(
        "tool_calls present:",
        bool(tool_calls),
    )

    print()
    print("[LENGTHS]")
    print(
        "content chars     :",
        len(content_text),
    )
    print(
        "thinking chars    :",
        len(thinking_text),
    )

    print()
    print("[THINK TAGS INSIDE CONTENT]")
    print(
        "<think> count     :",
        content_tags["think_open"],
    )
    print(
        "</think> count    :",
        content_tags["think_close"],
    )

    print()
    print("[THINKING FIELD PREVIEW]")
    if thinking_text:
        print(summarize_text(thinking_text))
    else:
        print("<empty>")

    print()
    print("[CONTENT FIELD PREVIEW]")
    print(summarize_text(content_text))

    print()
    print("[TOOL CALLS]")
    if tool_calls:
        for index, call in enumerate(tool_calls, start=1):
            function = get_attr(call, "function", None)

            name = get_attr(function, "name", None)
            arguments = get_attr(function, "arguments", None)

            print(f"  Tool {index}:")
            print(f"    name      = {name}")
            print(f"    arguments = {arguments}")
    else:
        print("<none>")

    # --------------------------------------------------------
    # Additional response inspection
    #
    # We only print the top-level keys because different Ollama
    # Python-client versions expose slightly different objects.
    # --------------------------------------------------------

    if response_dict is not None:

        print()
        print("[RAW RESPONSE KEYS]")
        print(
            ", ".join(
                sorted(
                    str(key)
                    for key in response_dict.keys()
                )
            )
        )

        if "thinking" in response_dict:
            raw_thinking = response_dict.get("thinking")

            print()
            print("[RAW RESPONSE thinking FIELD]")
            print(
                summarize_text(
                    raw_thinking
                )
            )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 78)
    print("JARVIS — PHASE 1.1A QWEN THINKING DIAGNOSTIC")
    print("=" * 78)

    settings = Settings()

    print()
    print("[JARVIS CONFIG]")
    print(f"Model        : {settings.llm_model}")
    print(f"Ollama host  : {settings.ollama_host}")
    print(f"Context size : {settings.context_size}")
    print(f"JARVIS_THINK : {settings.think}")
    print(f"Keep alive   : {settings.keep_alive}")

    print()
    print("[TEST INPUT]")
    print(TEST_INPUT)

    # --------------------------------------------------------
    # Create the real Agent.
    #
    # This ensures we are using the actual current architecture
    # rather than recreating an artificial system prompt/tool set.
    # --------------------------------------------------------

    print()
    print("[AGENT]")
    print("Creating real JarvisAgent...")

    try:
        agent = JarvisAgent()
    except Exception as exc:
        print()
        print("[ERROR] Could not create JarvisAgent.")
        print(f"{type(exc).__name__}: {exc}")
        sys.exit(1)

    # --------------------------------------------------------
    # Build the actual current JARVIS context.
    #
    # This is intentionally read-only from our perspective.
    # --------------------------------------------------------

    try:
        context = agent._build_context(
            user_input=TEST_INPUT
        )
    except Exception as exc:
        print()
        print("[ERROR] Could not build Agent context.")
        print(f"{type(exc).__name__}: {exc}")
        sys.exit(1)

    messages = context.as_messages()

    try:
        tools = agent._get_llm_tools()
    except Exception as exc:
        print()
        print("[ERROR] Could not retrieve Agent tools.")
        print(f"{type(exc).__name__}: {exc}")
        sys.exit(1)

    print()
    print("[CONTEXT]")
    print(f"Messages : {len(messages)}")
    print(f"Tools    : {len(tools)}")

    # --------------------------------------------------------
    # Ollama client
    # --------------------------------------------------------

    client = Client(
        host=settings.ollama_host
    )

    # --------------------------------------------------------
    # Baseline: think=False
    # --------------------------------------------------------

    run_experiment(
        client=client,
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        think=False,
    )

    # --------------------------------------------------------
    # Comparison: think=True
    # --------------------------------------------------------

    run_experiment(
        client=client,
        model=settings.llm_model,
        messages=messages,
        tools=tools,
        think=True,
    )

    # --------------------------------------------------------
    # Conclusion
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 78)

    print()
    print("We are specifically looking for:")

    print(
        "1. Does think=False still produce a non-empty "
        "message.thinking field?"
    )

    print(
        "2. Does think=False instead place <think>...</think> "
        "inside message.content?"
    )

    print(
        "3. Does think=True move reasoning into the dedicated "
        "thinking field?"
    )

    print(
        "4. Does the tool call remain structurally separate "
        "from reasoning?"
    )

    print(
        "5. How much latency changes between think=False "
        "and think=True?"
    )

    print()
    print("No production JARVIS code was modified.")


if __name__ == "__main__":
    main()