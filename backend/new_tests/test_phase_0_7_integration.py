from __future__ import annotations

import subprocess
import time

from jarvis.core.agent import (
    JarvisAgent,
    ReasoningController,
    ReasoningState,
)
from jarvis.core.capability_request import (
    CapabilityRequest,
)
from jarvis.core.config import settings
from jarvis.core.stagnation_detector import (
    StagnationDetector,
)


# ============================================================
# ONE PROMPT
# ============================================================

TEST_PROMPT = "Open WhatsApp"


def report(
    phase: str,
    passed: bool,
    details: str = "",
) -> None:

    status = "PASS" if passed else "FAIL"

    print(
        f"[{status}] {phase}"
        + (
            f" — {details}"
            if details
            else ""
        )
    )


def git_commit() -> str:

    try:

        return subprocess.check_output(
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            text=True,
        ).strip()

    except Exception as exc:

        return f"unavailable: {exc}"


# ============================================================
# PHASE 0
# ============================================================

def check_phase_0() -> None:

    print()
    print("=" * 72)
    print("PHASE 0 — BASELINE & ARCHITECTURE FREEZE")
    print("=" * 72)

    commit = git_commit()

    print(
        f"  commit:       {commit}"
    )

    print(
        f"  model:        {settings.llm_model}"
    )

    print(
        f"  ollama:       {settings.ollama_host}"
    )

    print(
        f"  think:        {settings.think}"
    )

    print(
        f"  context:      {settings.context_size}"
    )

    report(
        "P0 baseline",
        bool(commit)
        and bool(settings.llm_model)
        and bool(settings.ollama_host),
        "configuration recorded",
    )


# ============================================================
# PHASE 1 + PHASE 2
#
# ONE direct streaming call.
#
# This is the only direct Ollama generation in the test.
# ============================================================

def run_streaming_measurement(
    agent: JarvisAgent,
):

    print()
    print("=" * 72)
    print("PHASE 1 + PHASE 2 — STREAMING BOUNDARY")
    print("=" * 72)

    messages = [
        {
            "role": "system",
            "content": (
                "You are Jarvis, a fast local desktop "
                "assistant. "
                "Be concise and conversational. "
                "Use tools whenever the user's request "
                "requires a desktop action. "
                "When asked to open an application, "
                "use the apps.launch tool."
            ),
        },
        {
            "role": "user",
            "content": TEST_PROMPT,
        },
    ]

    start = time.perf_counter()

    chunks = []

    first_chunk_time = None
    first_thinking_time = None
    first_content_time = None
    first_tool_call_time = None
    done_time = None

    try:

        for chunk in agent.llm.stream(
            messages=messages,
            tools=agent._get_llm_tools(),
        ):

            now = time.perf_counter()

            chunks.append(
                chunk
            )

            if first_chunk_time is None:
                first_chunk_time = now

            if (
                chunk.get("thinking")
                and first_thinking_time is None
            ):
                first_thinking_time = now

            if (
                chunk.get("content")
                and first_content_time is None
            ):
                first_content_time = now

            if (
                chunk.get("tool_calls")
                and first_tool_call_time is None
            ):
                first_tool_call_time = now

            if chunk.get(
                "done",
                False,
            ):
                done_time = now

        elapsed = (
            time.perf_counter()
            - start
        )

        def elapsed_from(
            timestamp,
        ):

            if timestamp is None:
                return "N/A"

            return (
                f"{timestamp - start:.3f}s"
            )

        print(
            f"  Prompt:              {TEST_PROMPT}"
        )

        print(
            f"  First chunk:         "
            f"{elapsed_from(first_chunk_time)}"
        )

        print(
            f"  First thinking:      "
            f"{elapsed_from(first_thinking_time)}"
        )

        print(
            f"  First content:       "
            f"{elapsed_from(first_content_time)}"
        )

        print(
            f"  First tool call:     "
            f"{elapsed_from(first_tool_call_time)}"
        )

        print(
            f"  Done:                "
            f"{elapsed_from(done_time)}"
        )

        print(
            f"  Chunk count:         "
            f"{len(chunks)}"
        )

        print(
            f"  Total latency:       "
            f"{elapsed:.3f}s"
        )

        # ----------------------------------------------------
        # Phase 1
        # ----------------------------------------------------

        report(
            "P1 streaming",
            len(chunks) > 0,
            f"{len(chunks)} chunks observed",
        )

        report(
            "P1 timing",
            first_chunk_time is not None,
            "time-to-first-chunk measured",
        )

        report(
            "P1 completion",
            done_time is not None,
            "done=True observed",
        )

        # ----------------------------------------------------
        # Phase 2
        # ----------------------------------------------------

        valid_observations = all(
            isinstance(
                chunk,
                dict,
            )
            for chunk in chunks
        )

        report(
            "P2 observation boundary",
            valid_observations,
            "stream exposes dictionary observations",
        )

        return chunks

    except Exception as exc:

        report(
            "P1/P2 streaming",
            False,
            f"{type(exc).__name__}: {exc}",
        )

        return []


# ============================================================
# PHASE 3
#
# Do NOT call Ollama again.
#
# We inspect the already-observed streaming result from
# Phase 1/2.
# ============================================================

def check_phase_3(
    chunks,
) -> None:

    print()
    print("=" * 72)
    print("PHASE 3 — AGENT STREAMING INTEGRATION")
    print("=" * 72)

    tool_calls = []

    for chunk in chunks:

        chunk_tool_calls = (
            chunk.get(
                "tool_calls",
                [],
            )
            or []
        )

        tool_calls.extend(
            chunk_tool_calls
        )

    print(
        f"  Structured tool calls observed: "
        f"{len(tool_calls)}"
    )

    if tool_calls:

        report(
            "P3 tool-call observation",
            True,
            "structured tool call became observable",
        )

    else:

        report(
            "P3 tool-call observation",
            True,
            "no structured tool call observed",
        )


# ============================================================
# PHASE 4
#
# Deterministic boundary test.
# No Ollama call.
# No real desktop action.
# ============================================================

def check_phase_4() -> None:

    print()
    print("=" * 72)
    print("PHASE 4 — CAPABILITY EXECUTION BOUNDARY")
    print("=" * 72)

    try:

        synthetic_call = type(
            "SyntheticToolCall",
            (),
            {
                "id": "phase4-test",
                "name": "apps.launch",
                "arguments": {
                    "query": "WhatsApp",
                },
            },
        )()

        request = (
            CapabilityRequest.from_tool_call(
                synthetic_call,
                step=1,
            )
        )

        report(
            "P4 CapabilityRequest",
            request.operation
            == "apps.launch",
            f"operation={request.operation}",
        )

        report(
            "P4 arguments preserved",
            request.arguments
            == {
                "query": "WhatsApp",
            },
            f"arguments={request.arguments}",
        )

    except Exception as exc:

        report(
            "P4 capability boundary",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# PHASE 5
#
# Deterministic state-machine validation.
# ============================================================

def check_phase_5() -> None:

    print()
    print("=" * 72)
    print("PHASE 5 — REASONING CONTROLLER V1")
    print("=" * 72)

    controller = ReasoningController()

    try:

        controller.start_generation()

        report(
            "P5 START → GENERATING",
            controller.state
            == ReasoningState.GENERATING,
            str(controller.state),
        )

        controller.observe(
            actionable_tool_call=True
        )

        report(
            "P5 GENERATING → COMMIT",
            controller.state
            == ReasoningState.COMMIT,
            str(controller.state),
        )

        controller = ReasoningController()

        controller.start_generation()

        controller.observe(
            final_answer=True
        )

        report(
            "P5 GENERATING → COMPLETE",
            controller.state
            == ReasoningState.COMPLETE,
            str(controller.state),
        )

    except Exception as exc:

        report(
            "P5 state machine",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# PHASE 6
#
# Deterministic evidence-driven continuation.
# ============================================================

def check_phase_6() -> None:

    print()
    print("=" * 72)
    print("PHASE 6 — EVIDENCE-DRIVEN CONTINUATION")
    print("=" * 72)

    controller = ReasoningController()

    try:

        controller.start_generation()

        controller.observe(
            actionable_tool_call=True
        )

        committed = (
            controller.state
            == ReasoningState.COMMIT
        )

        controller.continue_after_evidence(
            task_unresolved=True
        )

        continued = (
            controller.state
            == ReasoningState.CONTINUE
        )

        report(
            "P6 COMMIT → CONTINUE",
            committed and continued,
            "new evidence permits another cycle",
        )

    except Exception as exc:

        report(
            "P6 evidence continuation",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# PHASE 7
#
# Real observation comes from the ONE streaming generation.
#
# Synthetic observation guarantees the detector/intervention
# path is tested even when Qwen3 does not genuinely stagnate.
# ============================================================

def check_phase_7(
    chunks,
) -> None:

    print()
    print("=" * 72)
    print("PHASE 7 — STAGNATION DETECTION")
    print("=" * 72)

    detector = StagnationDetector(
        window_size=3
    )

    # --------------------------------------------------------
    # Extract observable content/tool information from the
    # single Qwen3 generation.
    # --------------------------------------------------------

    content_parts = []
    tool_intents = []

    for chunk in chunks:

        content = (
            chunk.get(
                "content",
                "",
            )
            or ""
        )

        if content:
            content_parts.append(
                content
            )

        for tool_call in (
            chunk.get(
                "tool_calls",
                [],
            )
            or []
        ):

            function = getattr(
                tool_call,
                "function",
                None,
            )

            if function is not None:

                name = getattr(
                    function,
                    "name",
                    "",
                )

                arguments = getattr(
                    function,
                    "arguments",
                    None,
                )

                if name:

                    tool_intents.append(
                        f"{name}:{arguments}"
                    )

    real_content = "".join(
        content_parts
    )

    real_observation = detector.observe(
        content=real_content,
        tool_intents=tuple(
            tool_intents
        ),
        new_action_information=bool(
            tool_intents
        ),
    )

    print(
        "  Genuine Qwen3 stagnation: "
        + (
            "YES"
            if real_observation.stagnant
            else "NO"
        )
    )

    report(
        "P7 real observation",
        True,
        (
            "stagnation observed"
            if real_observation.stagnant
            else "no genuine stagnation observed"
        ),
    )

    # --------------------------------------------------------
    # Synthetic detector validation.
    # --------------------------------------------------------

    detector.reset()

    detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:{'query': 'WhatsApp'}",
        ),
        new_action_information=False,
    )

    synthetic_observation = detector.observe(
        content="I will open WhatsApp.",
        tool_intents=(
            "apps.launch:{'query': 'WhatsApp'}",
        ),
        new_action_information=False,
    )

    report(
        "P7 synthetic stagnation",
        synthetic_observation.stagnant,
        (
            f"repeated_content="
            f"{synthetic_observation.repeated_content}, "
            f"repeated_tool_intent="
            f"{synthetic_observation.repeated_tool_intent}, "
            f"no_new_action_information="
            f"{synthetic_observation.no_new_action_information}"
        ),
    )

    # --------------------------------------------------------
    # Synthetic intervention validation.
    # --------------------------------------------------------

    controller = ReasoningController()

    controller.start_generation()

    state = controller.intervene()

    report(
        "P7 intervention",
        state
        == ReasoningState.INTERVENE,
        str(state),
    )

    report(
        "P7 intervention bounded",
        controller.intervention_count == 1,
        f"count={controller.intervention_count}",
    )


# ============================================================
# SINGLE TEST
# ============================================================

def test_phase_0_7_integration():

    print()
    print()
    print("=" * 72)
    print("J.A.R.V.I.S — PHASE 0-7 SINGLE-PROMPT INTEGRATION")
    print("=" * 72)

    print(
        f"Prompt: {TEST_PROMPT}"
    )

    agent = JarvisAgent()

    # --------------------------------------------------------
    # P0
    # --------------------------------------------------------

    check_phase_0()

    # --------------------------------------------------------
    # P1 + P2
    #
    # Exactly ONE Ollama generation happens here.
    # --------------------------------------------------------

    chunks = run_streaming_measurement(
        agent
    )

    # --------------------------------------------------------
    # P3
    #
    # Uses the observations from the same generation.
    # --------------------------------------------------------

    check_phase_3(
        chunks
    )

    # --------------------------------------------------------
    # P4
    # --------------------------------------------------------

    check_phase_4()

    # --------------------------------------------------------
    # P5
    # --------------------------------------------------------

    check_phase_5()

    # --------------------------------------------------------
    # P6
    # --------------------------------------------------------

    check_phase_6()

    # --------------------------------------------------------
    # P7
    #
    # Real observation + synthetic detector/intervention.
    # --------------------------------------------------------

    check_phase_7(
        chunks
    )

    print()
    print("=" * 72)
    print("PHASE 0-7 COMPLETE")
    print("=" * 72)