import sys
import time

from ollama import Client
from jarvis.core.config import Settings


MODEL = "qwen3:4b"
OLLAMA_HOST = "http://127.0.0.1:11434"

TEST_INPUT = "Open WhatsApp."

# Experimental reasoning budgets.
# Approximate tokens using chars / 4.
BUDGETS = [256, 512, 1024]


EARLY_STOP_PROMPT = (
    "\n\nConsidering the limited time by the user, "
    "I have to give the solution based on the thinking directly now.\n"
    "</think>\n\n"
)


def safe_print(text):
    """
    Windows-safe output.
    Prevents cp1252/Unicode crashes from model output.
    """
    text = str(text)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8"))


def run_unrestricted(client):
    print("\n" + "=" * 70)
    print("BASELINE — UNRESTRICTED THINKING")
    print("=" * 70)

    messages = [
        {
            "role": "user",
            "content": TEST_INPUT,
        }
    ]

    started = time.perf_counter()

    response = client.chat(
        model=MODEL,
        messages=messages,
        think=True,
        stream=False,
        options={
            "num_ctx": 8192,
        },
    )

    elapsed = time.perf_counter() - started

    thinking = getattr(response.message, "thinking", "") or ""
    content = getattr(response.message, "content", "") or ""

    print(f"Total time:       {elapsed:.3f}s")
    print(f"Thinking chars:   {len(thinking)}")
    print(f"Approx tokens:    {len(thinking) / 4:.0f}")
    safe_print(f"Final content:    {content}")

    return {
        "elapsed": elapsed,
        "thinking": thinking,
        "content": content,
    }


def run_early_stop(client, budget):
    print("\n" + "=" * 70)
    print(f"EARLY STOP — BUDGET ≈ {budget} TOKENS")
    print("=" * 70)

    messages = [
        {
            "role": "user",
            "content": TEST_INPUT,
        }
    ]

    started = time.perf_counter()

    stream = client.chat(
        model=MODEL,
        messages=messages,
        think=True,
        stream=True,
        options={
            "num_ctx": 8192,
        },
    )

    thinking_parts = []
    chars_seen = 0

    stop_time = None

    # ------------------------------------------------------------
    # Generation 1:
    # Allow Qwen to reason until our experimental budget.
    # ------------------------------------------------------------

    for chunk in stream:
        thinking = getattr(chunk.message, "thinking", "") or ""

        if thinking:
            thinking_parts.append(thinking)
            chars_seen += len(thinking)

        # Character approximation:
        # ~4 characters ≈ 1 token.
        estimated_tokens = chars_seen / 4

        if estimated_tokens >= budget:
            stop_time = time.perf_counter()

            print(
                f"Budget reached: {estimated_tokens:.0f} "
                f"tokens / {chars_seen} chars"
            )

            # Stop consuming the stream.
            break

    partial_thinking = "".join(thinking_parts)

    print(f"Captured thinking: {len(partial_thinking)} chars")

    # ------------------------------------------------------------
    # Generation 2:
    # Experimental continuation using the accumulated reasoning.
    #
    # IMPORTANT:
    # Ollama does not expose the same token-level continuation
    # mechanism as Qwen's Transformers implementation.
    #
    # Therefore this is explicitly an experiment, not production
    # early stopping.
    # ------------------------------------------------------------

    continuation_content = (
        partial_thinking
        + EARLY_STOP_PROMPT
    )

    continuation_messages = [
        {
            "role": "user",
            "content": TEST_INPUT,
        },
        {
            "role": "assistant",
            "content": continuation_content,
        },
    ]

    second_started = time.perf_counter()

    response = client.chat(
        model=MODEL,
        messages=continuation_messages,
        think=False,
        stream=False,
        options={
            "num_ctx": 8192,
        },
    )

    second_elapsed = time.perf_counter() - second_started
    total_elapsed = time.perf_counter() - started

    content = getattr(response.message, "content", "") or ""

    print(f"Continuation time: {second_elapsed:.3f}s")
    print(f"Total time:        {total_elapsed:.3f}s")
    print(f"Final content:     {repr(content)}")

    return {
        "budget": budget,
        "thinking_chars": len(partial_thinking),
        "thinking_tokens": len(partial_thinking) / 4,
        "first_phase_time": (
            stop_time - started if stop_time else None
        ),
        "continuation_time": second_elapsed,
        "total_time": total_elapsed,
        "content": content,
    }


def main():
    # Make stdout UTF-8 tolerant on Windows.
    try:
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        pass

    settings = Settings()

    print("=" * 70)
    print("JARVIS — PHASE 1.1C")
    print("CONTROLLED ADAPTIVE EARLY-STOP EXPERIMENT")
    print("=" * 70)

    print(f"Model:       {MODEL}")
    print(f"Ollama:      {OLLAMA_HOST}")
    print(f"Input:       {TEST_INPUT}")

    client = Client(host=OLLAMA_HOST)

    # ------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------

    baseline = run_unrestricted(client)

    # ------------------------------------------------------------
    # Early-stop experiments
    # ------------------------------------------------------------

    results = []

    for budget in BUDGETS:
        result = run_early_stop(client, budget)
        results.append(result)

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("PHASE 1.1C SUMMARY")
    print("=" * 70)

    print(
        f"Baseline: "
        f"{baseline['elapsed']:.3f}s | "
        f"{len(baseline['thinking']) / 4:.0f} approx tokens"
    )

    for result in results:
        print(
            f"Budget {result['budget']:>4}: "
            f"{result['total_time']:.3f}s | "
            f"{result['thinking_tokens']:.0f} approx tokens | "
            f"output={repr(result['content'])}"
        )

    print("\nExperiment complete.")


if __name__ == "__main__":
    main()