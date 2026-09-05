"""
TEST 4 — REAL AGENT TRAJECTORY

Purpose:
    Exercise the actual JarvisAgent execution path and inspect whether
    evidence from an executed operation is followed by appropriate
    reasoning/termination behavior.

No production code is modified.

Run:
    cd backend
    python test_real_agent_trajectory.py
"""

from __future__ import annotations

import json
import time
import traceback

from jarvis.core.agent import JarvisAgent


TASKS = [
    "Open WhatsApp.",
    "Find WhatsApp on my computer.",
]


def summarize(value, limit=500):
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def inspect_agent(agent: JarvisAgent):
    print("\nAGENT INTERNAL STATE")
    print("-" * 72)

    print(
        "operation_results:",
        len(getattr(agent, "operation_results", [])),
    )

    for index, result in enumerate(
        getattr(agent, "operation_results", []),
        start=1,
    ):
        print(
            f"result {index}: "
            f"operation={getattr(result, 'operation', None)} "
            f"status={getattr(result, 'status', None)} "
            f"state={getattr(result, 'state', None)} "
            f"is_terminal={getattr(result, 'is_terminal', None)} "
            f"data={summarize(getattr(result, 'data', None))} "
            f"error={summarize(getattr(result, 'error_message', None))}"
        )

    print(
        "messages:",
        len(getattr(agent, "messages", [])),
    )

    for index, message in enumerate(
        getattr(agent, "messages", [])[-6:],
        start=max(1, len(agent.messages) - 5),
    ):
        print(
            f"message {index}: "
            f"role={message.get('role')} "
            f"content={summarize(message.get('content'))}"
        )


def find_public_run_method(agent):
    """
    Do not assume a particular run signature.

    Discover the callable public method that looks like the Agent's
    execution entry point, then report it before invocation.
    """

    candidates = []

    for name in dir(agent):
        if name.startswith("_"):
            continue

        value = getattr(agent, name)

        if callable(value):
            candidates.append(name)

    print("\nPUBLIC CALLABLES")
    print("-" * 72)

    for name in candidates:
        print(name)

    preferred = [
        "run",
        "process",
        "handle",
        "execute",
        "respond",
    ]

    for name in preferred:
        if name in candidates:
            return name

    return None


def main():
    print("=" * 72)
    print("TEST 4 — REAL AGENT TRAJECTORY")
    print("=" * 72)


    for task in TASKS:
        agent = JarvisAgent()
        agent.state.conversation_id = agent.recall.create_conversation()
        agent.messages = []
        method_name = find_public_run_method(agent)

        if method_name is None:
            print(
                "\nERROR: Could not identify the public Agent execution "
                "method automatically."
            )
            print(
                "Do not change production code. Send me this output and "
                "I will wire the exact method from the repository."
            )
            return

        method = getattr(agent, method_name)

        print(
            f"\nSelected Agent entry point: "
            f"{method_name}"
        )

        before_results = len(
            getattr(agent, "operation_results", [])
        )
        before_messages = len(
            getattr(agent, "messages", [])
        )

        start = time.perf_counter()

        try:
            # The repository's public Agent API is inspected at runtime
            # rather than assumed. Most likely this will be run(task).
            result = method(task)

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            print(
                f"\nRESULT ({elapsed_ms:.1f}ms):"
            )
            print(
                summarize(result, 3000)
            )

        except TypeError as exc:
            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            print(
                f"\nENTRY POINT INVOCATION TYPE ERROR "
                f"after {elapsed_ms:.1f}ms:"
            )
            print(exc)

            print(
                "\nThis is intentionally not hidden. "
                "It means the repository's exact public signature "
                "differs from method(task)."
            )

            traceback.print_exc()

        except Exception as exc:
            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            print(
                f"\nAGENT ERROR after {elapsed_ms:.1f}ms:"
            )
            print(
                type(exc).__name__,
                str(exc),
            )

            traceback.print_exc()

        after_results = len(
            getattr(agent, "operation_results", [])
        )
        after_messages = len(
            getattr(agent, "messages", [])
        )

        print("\nDELTA")
        print("-" * 72)
        print(
            "new operation results:",
            after_results - before_results,
        )
        print(
            "new messages:",
            after_messages - before_messages,
        )

        inspect_agent(agent)

    print("\nDONE")


if __name__ == "__main__":
    main()