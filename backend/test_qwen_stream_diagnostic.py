"""
Phase 1.1B — Raw Qwen/Ollama Streaming Diagnostic

Purpose
-------
Inspect the raw streaming behavior of qwen3:4b with:

    think=False
    think=True

No JarvisAgent.
No JARVIS context.
No tools.

This establishes the actual Ollama/Qwen behavior before implementing
adaptive reasoning or early stopping.

Run from:
    backend/

Command:
    python test_qwen_stream_diagnostic.py
"""

from __future__ import annotations

import sys
import time

from ollama import Client

from jarvis.core.config import Settings


# ============================================================
# CONFIGURATION
# ============================================================

TEST_INPUT = "Hey Jarvis"


# ============================================================
# HELPERS
# ============================================================

def safe_get(obj, name, default=None):
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def preview(text: str, limit: int = 120) -> str:
    text = str(text or "")

    text = text.replace("\n", "\\n")

    if len(text) > limit:
        return text[:limit] + "..."

    return text


# ============================================================
# SINGLE STREAM EXPERIMENT
# ============================================================

def run_stream_test(
    client: Client,
    model: str,
    think: bool,
) -> None:

    print()
    print("=" * 78)
    print(f"STREAM TEST — think={think}")
    print("=" * 78)

    messages = [
        {
            "role": "user",
            "content": TEST_INPUT,
        }
    ]

    started = time.perf_counter()

    chunk_count = 0
    thinking_chunks = 0
    content_chunks = 0
    tool_chunks = 0

    thinking_chars = 0
    content_chars = 0

    first_chunk_time = None
    first_thinking_time = None
    first_content_time = None

    final_response = None

    try:
        stream = client.chat(
            model=model,
            messages=messages,
            tools=[],
            stream=True,
            think=think,
            keep_alive=Settings().keep_alive,
            options={
                "num_ctx": Settings().context_size,
            },
        )

        for chunk in stream:

            chunk_count += 1

            now = time.perf_counter()
            elapsed = now - started

            if first_chunk_time is None:
                first_chunk_time = elapsed

            message = safe_get(chunk, "message")

            if message is None:
                print(
                    f"[CHUNK {chunk_count}] "
                    f"message=<none>"
                )
                continue

            thinking = safe_get(
                message,
                "thinking",
                "",
            )

            content = safe_get(
                message,
                "content",
                "",
            )

            tool_calls = safe_get(
                message,
                "tool_calls",
                None,
            )

            thinking = str(thinking or "")
            content = str(content or "")

            # ------------------------------------------------
            # THINKING
            # ------------------------------------------------

            if thinking:

                thinking_chunks += 1
                thinking_chars += len(thinking)

                if first_thinking_time is None:
                    first_thinking_time = elapsed

                print(
                    f"[CHUNK {chunk_count:03d}] "
                    f"+THINK "
                    f"{len(thinking):4d} chars "
                    f"@ {elapsed:8.3f}s | "
                    f"{preview(thinking)}"
                )

            # ------------------------------------------------
            # CONTENT
            # ------------------------------------------------

            if content:

                content_chunks += 1
                content_chars += len(content)

                if first_content_time is None:
                    first_content_time = elapsed

                print(
                    f"[CHUNK {chunk_count:03d}] "
                    f"+CONTENT "
                    f"{len(content):4d} chars "
                    f"@ {elapsed:8.3f}s | "
                    f"{preview(content)}"
                )

            # ------------------------------------------------
            # TOOL CALLS
            # ------------------------------------------------

            if tool_calls:

                tool_chunks += 1

                print(
                    f"[CHUNK {chunk_count:03d}] "
                    f"+TOOL_CALL "
                    f"@ {elapsed:8.3f}s"
                )

                for call in tool_calls:

                    function = safe_get(
                        call,
                        "function",
                    )

                    if function:

                        name = safe_get(
                            function,
                            "name",
                        )

                        arguments = safe_get(
                            function,
                            "arguments",
                        )

                        print(
                            f"    name      = {name}"
                        )

                        print(
                            f"    arguments = {arguments}"
                        )

            # ------------------------------------------------
            # FINAL CHUNK METADATA
            # ------------------------------------------------

            done = safe_get(
                chunk,
                "done",
                False,
            )

            if done:

                final_response = chunk

                print()
                print(
                    f"[FINAL CHUNK] "
                    f"done=True "
                    f"@ {elapsed:.3f}s"
                )

                done_reason = safe_get(
                    chunk,
                    "done_reason",
                    None,
                )

                eval_count = safe_get(
                    chunk,
                    "eval_count",
                    None,
                )

                eval_duration = safe_get(
                    chunk,
                    "eval_duration",
                    None,
                )

                prompt_eval_count = safe_get(
                    chunk,
                    "prompt_eval_count",
                    None,
                )

                total_duration = safe_get(
                    chunk,
                    "total_duration",
                    None,
                )

                print(
                    f"  done_reason         = {done_reason}"
                )

                print(
                    f"  eval_count          = {eval_count}"
                )

                print(
                    f"  eval_duration       = {eval_duration}"
                )

                print(
                    f"  prompt_eval_count   = {prompt_eval_count}"
                )

                print(
                    f"  total_duration      = {total_duration}"
                )

    except Exception as exc:

        elapsed = time.perf_counter() - started

        print()
        print("[ERROR]")
        print(
            f"{type(exc).__name__}: {exc}"
        )

        print(
            f"Elapsed: {elapsed:.3f}s"
        )

        return

    # ========================================================
    # SUMMARY
    # ========================================================

    total_elapsed = time.perf_counter() - started

    print()
    print("-" * 78)
    print("STREAM SUMMARY")
    print("-" * 78)

    print(
        f"think                : {think}"
    )

    print(
        f"total time            : {total_elapsed:.3f}s"
    )

    print(
        f"chunks                : {chunk_count}"
    )

    print(
        f"thinking chunks       : {thinking_chunks}"
    )

    print(
        f"content chunks        : {content_chunks}"
    )

    print(
        f"tool chunks           : {tool_chunks}"
    )

    print(
        f"thinking chars        : {thinking_chars}"
    )

    print(
        f"content chars         : {content_chars}"
    )

    print(
        f"first chunk           : "
        f"{first_chunk_time if first_chunk_time is not None else 'N/A'}"
    )

    print(
        f"first thinking       : "
        f"{first_thinking_time if first_thinking_time is not None else 'N/A'}"
    )

    print(
        f"first content        : "
        f"{first_content_time if first_content_time is not None else 'N/A'}"
    )

    # ========================================================
    # FINAL RAW RESPONSE INSPECTION
    # ========================================================

    if final_response is not None:

        print()
        print("-" * 78)
        print("FINAL RESPONSE OBJECT")
        print("-" * 78)

        message = safe_get(
            final_response,
            "message",
        )

        if message:

            print(
                "final message.thinking:"
            )

            print(
                repr(
                    safe_get(
                        message,
                        "thinking",
                        None,
                    )
                )
            )

            print()
            print(
                "final message.content:"
            )

            print(
                repr(
                    safe_get(
                        message,
                        "content",
                        None,
                    )
                )
            )

            print()
            print(
                "final message.tool_calls:"
            )

            print(
                repr(
                    safe_get(
                        message,
                        "tool_calls",
                        None,
                    )
                )
            )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 78)
    print("JARVIS — PHASE 1.1B RAW QWEN STREAM DIAGNOSTIC")
    print("=" * 78)

    settings = Settings()

    print()
    print("[CONFIG]")
    print(
        f"Model        : {settings.llm_model}"
    )
    print(
        f"Ollama host  : {settings.ollama_host}"
    )
    print(
        f"Context size : {settings.context_size}"
    )
    print(
        f"Keep alive   : {settings.keep_alive}"
    )

    print()
    print("[INPUT]")
    print(TEST_INPUT)

    client = Client(
        host=settings.ollama_host
    )

    # --------------------------------------------------------
    # Disable thinking
    # --------------------------------------------------------

    run_stream_test(
        client=client,
        model=settings.llm_model,
        think=False,
    )

    # --------------------------------------------------------
    # Enable thinking
    # --------------------------------------------------------

    run_stream_test(
        client=client,
        model=settings.llm_model,
        think=True,
    )

    print()
    print("=" * 78)
    print("RAW STREAM DIAGNOSTIC COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()