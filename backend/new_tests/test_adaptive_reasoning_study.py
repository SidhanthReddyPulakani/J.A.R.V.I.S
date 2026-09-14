"""
JARVIS — Comprehensive Adaptive Reasoning Study

Diagnostic/research harness only.

IMPORTANT
---------
This file intentionally does NOT modify JarvisAgent or implement adaptive
stopping.

It observes complete Ollama generations and retrospectively evaluates:

    reasoning
        ↓
    candidate action
        ↓
    candidate stability
        ↓
    final structured tool call

We do NOT interrupt generation and re-prompt using partial reasoning.

That approach was already experimentally shown to be unsafe because a
partial reasoning trace is not equivalent to a continuation state.

The purpose of this file is to gather enough evidence to decide whether
JARVIS should eventually use:

    - adaptive reasoning
    - adaptive commit
    - selective context
    - prompt-level routing
    - or some combination

Run from:

    backend/

Example:

    python test_adaptive_reasoning_study.py

Recommended first run:

    set JARVIS_STUDY_RUNS=3
    python test_adaptive_reasoning_study.py

For a faster initial diagnostic:

    set JARVIS_STUDY_RUNS=1
    python test_adaptive_reasoning_study.py

Output:

    adaptive_reasoning_study.json

You can redirect console output:

    python test_adaptive_reasoning_study.py > adaptive_reasoning_study.txt
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
    
from ollama import Client


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = os.getenv(
    "JARVIS_STUDY_MODEL",
    "qwen3:4b",
)

OLLAMA_HOST = os.getenv(
    "JARVIS_STUDY_HOST",
    "http://127.0.0.1:11434",
)

CONTEXT_SIZE = int(
    os.getenv(
        "JARVIS_STUDY_CONTEXT",
        "8192",
    )
)

RUNS = int(
    os.getenv(
        "JARVIS_STUDY_RUNS",
        "3",
    )
)

KEEP_ALIVE = os.getenv(
    "JARVIS_KEEP_ALIVE",
    "10m",
)

OUTPUT_JSON = os.getenv(
    "JARVIS_STUDY_OUTPUT",
    "adaptive_reasoning_study.json",
)


# ============================================================
# JARVIS SYSTEM PROMPTS
# ============================================================

BASE_SYSTEM_PROMPT = """You are Jarvis, a fast local desktop assistant.

Your priorities:
1. Be concise and conversational.
2. Use tools whenever the user's request requires a desktop action.
3. When the user asks you to open, launch, run, or start an application,
   use the `apps.launch` tool with the application's name as the `query`.
4. Do not claim an action was completed unless a tool result confirms it.
5. If a tool is required, produce the appropriate structured tool call.
6. Do not explain your internal reasoning to the user.
7. For simple commands, respond briefly.
"""


STRONG_COMMIT_PROMPT = BASE_SYSTEM_PROMPT + """

Execution discipline:

For simple, unambiguous requests:

- identify the requested action;
- identify the target;
- ensure the required tool arguments are complete;
- then emit the structured tool call.

Do not repeatedly reconsider an already-supported decision.

Do not invent unnecessary intermediate operations.

Do not perform a search or resolution step when the requested operation can
already be represented directly by an available tool.

Continue reasoning only when there is genuine ambiguity, missing information,
conflicting requirements, tool-result evidence, or another concrete reason
that changes what should happen.

Once the operation and required arguments are complete and consistent with
the user's request, commit to the structured tool call.
"""


# ============================================================
# REAL JARVIS TOOL DEFINITIONS
#
# These mirror the currently exposed P13 capability surface:
#
#   apps.find
#   apps.resolve
#   apps.launch
#
# The diagnostic does NOT execute these tools.
# Ollama only sees their definitions.
# ============================================================

JARVIS_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "apps.find",
            "description": (
                "Search discovered applications by name, without resolving "
                "to a single result or launching anything."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Application name, alias, or user-provided "
                            "description."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apps.resolve",
            "description": (
                "Resolve a query to exactly one application, or report "
                "ambiguous or not-found candidates without launching."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Application name, alias, or user-provided "
                            "description."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apps.launch",
            "description": (
                "Resolve and launch an application. Returns confirmation "
                "after launch and verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Application name, alias, or user-provided "
                            "description."
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# ============================================================
# TASKS
# ============================================================

@dataclass(frozen=True)
class Task:
    name: str
    prompt: str
    category: str
    expected_operation: str | None
    expected_target: str | None


TASKS: tuple[Task, ...] = (
    Task(
        name="simple_conversation",
        prompt="Hey Jarvis.",
        category="conversation",
        expected_operation=None,
        expected_target=None,
    ),

    Task(
        name="simple_launch",
        prompt="Open WhatsApp.",
        category="simple_action",
        expected_operation="apps.launch",
        expected_target="WhatsApp",
    ),

    Task(
        name="launch_and_confirm",
        prompt=(
            "Open WhatsApp and tell me when it is done."
        ),
        category="simple_action",
        expected_operation="apps.launch",
        expected_target="WhatsApp",
    ),

    Task(
        name="multi_step",
        prompt=(
            "Find WhatsApp, then open it."
        ),
        category="multi_step",
        expected_operation="apps.launch",
        expected_target="WhatsApp",
    ),

    Task(
        name="ambiguous",
        prompt=(
            "Open the messaging app."
        ),
        category="ambiguous",
        expected_operation=None,
        expected_target=None,
    ),

    Task(
        name="evidence_dependent",
        prompt=(
            "Find applications matching the name WhatsApp, then tell me "
            "whether the search returned exactly one match, more than one "
            "match, or no matches."
        ),
        category="evidence",
        expected_operation="apps.find",
        expected_target="WhatsApp",
    ),

    Task(
        name="missing_application",
        prompt=(
            "Open an application called "
            "DefinitelyNotInstalledJarvisTest."
        ),
        category="missing_target",
        expected_operation="apps.launch",
        expected_target="DefinitelyNotInstalledJarvisTest",
    ),

    Task(
        name="explicit_find_resolve_launch",
        prompt=(
            "Find WhatsApp, resolve it to one application if possible, "
            "and only then open it."
        ),
        category="multi_step",
        expected_operation="apps.find",
        expected_target="WhatsApp",
    ),
)


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class PrefixObservation:
    sequence: int
    elapsed_seconds: float

    thinking_chars: int
    content_chars: int
    total_chars: int

    candidate_operations: list[str]
    candidate_targets: list[str]

    uncertainty: bool
    self_correction: bool
    repetition: bool
    terminal_language: bool

    action_completeness: float
    target_completeness: float
    consistency: float
    readiness_score: float

    final_operation_match: bool
    final_target_match: bool
    retrospectively_safe: bool


@dataclass
class RunResult:
    task: str
    category: str
    mode: str
    run_index: int

    total_seconds: float

    first_chunk_seconds: float | None
    first_thinking_seconds: float | None
    first_content_seconds: float | None
    first_tool_call_seconds: float | None

    post_commit_seconds: float | None

    thinking_chars: int
    content_chars: int
    total_chars: int

    tool_calls: list[dict[str, Any]]

    correct_operation: bool
    correct_target: bool
    correct_call: bool

    first_candidate_seconds: float | None
    first_safe_prefix_seconds: float | None

    candidate_to_tool_gap_seconds: float | None
    safe_to_tool_gap_seconds: float | None

    max_readiness_before_tool: float | None
    median_readiness_before_tool: float | None

    reversal_count: int
    self_correction_count: int
    repeated_prefix_count: int
    stagnation_indicator_count: int

    prefix_count: int

    observations: list[PrefixObservation] = field(
        default_factory=list
    )


# ============================================================
# UTILITY
# ============================================================

def clock() -> float:
    return time.perf_counter()


def normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9_.]",
        "",
        value.lower(),
    )


def contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    lowered = text.lower()

    return any(
        term in lowered
        for term in terms
    )


def median_or_none(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return statistics.median(values)


def percentile(
    values: list[float],
    p: float,
) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        len(ordered) - 1
    ) * p

    lower = int(position)

    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = (
        position
        - lower
    )

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


# ============================================================
# STREAM EXTRACTION
# ============================================================

def extract_tool_calls(
    message: Any,
) -> list[dict[str, Any]]:
    calls = (
        getattr(
            message,
            "tool_calls",
            None,
        )
        or []
    )

    result: list[dict[str, Any]] = []

    for call in calls:
        function = getattr(
            call,
            "function",
            None,
        )

        if function is None:
            continue

        name = (
            getattr(
                function,
                "name",
                "",
            )
            or ""
        )

        arguments = (
            getattr(
                function,
                "arguments",
                {},
            )
            or {}
        )

        result.append(
            {
                "id": getattr(
                    call,
                    "id",
                    None,
                ),
                "name": name,
                "arguments": dict(
                    arguments
                ),
            }
        )

    return result


def extract_call_target(
    call: dict[str, Any],
) -> str | None:
    arguments = (
        call.get(
            "arguments"
        )
        or {}
    )

    if "query" in arguments:
        return str(
            arguments["query"]
        )

    return None


# ============================================================
# CANDIDATE DETECTION
# ============================================================

def detect_candidate_operations(
    text: str,
) -> list[str]:
    """
    Detect possible operations mentioned by the model's observable
    reasoning/content.

    This is deliberately permissive.

    It is NOT considered a production decision function.

    Its purpose is to answer:

        "How early does the model expose something that looks like
         an action?"

    The retrospective safety analysis later determines whether that
    candidate was actually reliable.
    """

    lowered = text.lower()

    found: list[str] = []

    find_patterns = (
        r"\bapps\.find\b",
        r"\bfind\b.*\bapplication",
        r"\bfind\b.*\bapp\b",
        r"\bsearch\b.*\bapplication",
        r"\bsearch\b.*\bapp\b",
    )

    resolve_patterns = (
        r"\bapps\.resolve\b",
        r"\bresolve\b.*\bapplication",
        r"\bresolve\b.*\bapp\b",
    )

    launch_patterns = (
        r"\bapps\.launch\b",
        r"\blaunch\b",
        r"\bopen\b",
        r"\bstart\b",
        r"\brun\b",
    )

    if any(
        re.search(
            pattern,
            lowered,
        )
        for pattern in find_patterns
    ):
        found.append(
            "apps.find"
        )

    if any(
        re.search(
            pattern,
            lowered,
        )
        for pattern in resolve_patterns
    ):
        found.append(
            "apps.resolve"
        )

    if any(
        re.search(
            pattern,
            lowered,
        )
        for pattern in launch_patterns
    ):
        found.append(
            "apps.launch"
        )

    return found


def detect_candidate_targets(
    text: str,
    task: Task,
) -> list[str]:
    targets: list[str] = []

    if (
        task.expected_target
        and task.expected_target.lower()
        in text.lower()
    ):
        targets.append(
            task.expected_target
        )

    quoted = re.findall(
        r"""['"]([^'"]{2,100})['"]""",
        text,
    )

    for item in quoted:
        if item not in targets:
            targets.append(item)

    return targets


# ============================================================
# REASONING SIGNALS
# ============================================================

def detect_uncertainty(
    text: str,
) -> bool:
    return contains_any(
        text,
        (
            "maybe",
            "perhaps",
            "uncertain",
            "not sure",
            "i'm not sure",
            "i am not sure",
            "ambiguous",
            "could be",
            "might be",
            "need to determine",
            "need more information",
            "cannot determine",
            "can't determine",
        ),
    )


def detect_self_correction(
    text: str,
) -> bool:
    return contains_any(
        text,
        (
            "actually",
            "wait",
            "correction",
            "instead",
            "rather than",
            "i should",
            "i shouldn't",
            "reconsider",
            "let me reconsider",
            "that would be wrong",
            "not the right",
            "i need to change",
        ),
    )


def detect_terminal_language(
    text: str,
) -> bool:
    return contains_any(
        text,
        (
            "therefore",
            "so i will",
            "i'll use",
            "i should use",
            "appropriate tool",
            "final decision",
            "ready to",
            "proceed with",
            "execute",
            "i will open",
            "i will launch",
        ),
    )


# ============================================================
# READINESS SCORING
# ============================================================

def action_completeness(
    task: Task,
    operations: list[str],
) -> float:

    if task.expected_operation is None:
        return (
            1.0
            if operations
            else 0.0
        )

    if (
        task.expected_operation
        not in operations
    ):
        return 0.0

    return 1.0


def target_completeness(
    task: Task,
    targets: list[str],
) -> float:

    if task.expected_target is None:
        return 1.0

    if (
        task.expected_target
        in targets
    ):
        return 1.0

    return 0.0


def calculate_consistency(
    uncertainty: bool,
    self_correction: bool,
    repetition: bool,
) -> float:

    score = 1.0

    if uncertainty:
        score -= 0.35

    if self_correction:
        score -= 0.30

    if repetition:
        score -= 0.10

    return max(
        0.0,
        score,
    )


def calculate_readiness(
    task: Task,
    operations: list[str],
    targets: list[str],
    uncertainty: bool,
    self_correction: bool,
    repetition: bool,
    terminal_language: bool,
) -> tuple[
    float,
    float,
    float,
    float,
]:

    action = action_completeness(
        task,
        operations,
    )

    target = target_completeness(
        task,
        targets,
    )

    consistency = calculate_consistency(
        uncertainty,
        self_correction,
        repetition,
    )

    readiness = (
        0.40 * action
        + 0.25 * target
        + 0.20 * consistency
        + 0.15 * (
            1.0
            if terminal_language
            else 0.0
        )
    )

    return (
        action,
        target,
        consistency,
        readiness,
    )


# ============================================================
# PREFIX OBSERVATION
# ============================================================

def build_prefix_observation(
    *,
    sequence: int,
    elapsed: float,
    thinking: str,
    content: str,
    task: Task,
    previous_operations: list[str],
) -> PrefixObservation:

    combined = (
        thinking
        + "\n"
        + content
    )

    operations = (
        detect_candidate_operations(
            combined
        )
    )

    targets = (
        detect_candidate_targets(
            combined,
            task,
        )
    )

    uncertainty = detect_uncertainty(
        combined
    )

    self_correction = detect_self_correction(
        combined
    )

    repetition = (
        bool(
            previous_operations
        )
        and operations
        == previous_operations
    )

    terminal_language = (
        detect_terminal_language(
            combined
        )
    )

    (
        action_score,
        target_score,
        consistency,
        readiness,
    ) = calculate_readiness(
        task,
        operations,
        targets,
        uncertainty,
        self_correction,
        repetition,
        terminal_language,
    )

    return PrefixObservation(
        sequence=sequence,
        elapsed_seconds=elapsed,
        thinking_chars=len(
            thinking
        ),
        content_chars=len(
            content
        ),
        total_chars=len(
            combined
        ),
        candidate_operations=operations,
        candidate_targets=targets,
        uncertainty=uncertainty,
        self_correction=self_correction,
        repetition=repetition,
        terminal_language=terminal_language,
        action_completeness=action_score,
        target_completeness=target_score,
        consistency=consistency,
        readiness_score=readiness,
        final_operation_match=False,
        final_target_match=False,
        retrospectively_safe=False,
    )


# ============================================================
# RETROSPECTIVE GROUND TRUTH
# ============================================================

def annotate_ground_truth(
    observations: list[PrefixObservation],
    final_calls: list[dict[str, Any]],
    task: Task,
) -> dict[str, Any]:

    if not observations:
        return {
            "first_candidate": None,
            "first_safe": None,
            "median_readiness": None,
            "max_readiness": None,
            "reversals": 0,
            "self_corrections": 0,
            "repetitions": 0,
            "stagnation": 0,
        }

    final_operations = [
        normalize(
            call["name"]
        )
        for call in final_calls
    ]

    final_targets = [
        normalize(
            extract_call_target(
                call
            )
            or ""
        )
        for call in final_calls
    ]

    first_candidate = None
    first_safe = None

    readiness_values: list[float] = []

    reversals = 0
    self_corrections = 0
    repetitions = 0
    stagnation = 0

    previous_operations: list[str] = []

    for index, observation in enumerate(
        observations
    ):

        candidate_operations = [
            normalize(
                operation
            )
            for operation
            in observation.candidate_operations
        ]

        candidate_targets = [
            normalize(
                target
            )
            for target
            in observation.candidate_targets
        ]

        if (
            candidate_operations
            and first_candidate is None
        ):
            first_candidate = (
                observation.elapsed_seconds
            )

        if observation.self_correction:
            self_corrections += 1

        if observation.repetition:
            repetitions += 1

        if (
            previous_operations
            and candidate_operations
            and candidate_operations
            != previous_operations
        ):
            reversals += 1

        if candidate_operations:
            previous_operations = (
                candidate_operations
            )

        if observation.repetition:
            if (
                index >= 2
            ):
                stagnation += 1

        if final_calls:
            operation_match = (
                task.expected_operation is None
                or (
                    task.expected_operation
                    and normalize(
                        task.expected_operation
                    )
                    in final_operations
                )
            )

            target_match = (
                task.expected_target is None
                or (
                    task.expected_target
                    and normalize(
                        task.expected_target
                    )
                    in final_targets
                )
            )

            observation.final_operation_match = (
                operation_match
            )

            observation.final_target_match = (
                target_match
            )

            if (
                operation_match
                and target_match
            ):
                readiness_values.append(
                    observation.readiness_score
                )

            # ------------------------------------------------
            # Retrospective safe-prefix analysis.
            #
            # A prefix is considered "safe" only when:
            #
            # 1. its candidate agrees with the final call;
            # 2. its target agrees;
            # 3. it is not expressing uncertainty;
            # 4. it is not correcting itself;
            # 5. every later candidate remains compatible.
            #
            # This is deliberately conservative.
            # ------------------------------------------------

            current_is_compatible = (
                bool(
                    candidate_operations
                )
                and all(
                    operation
                    in final_operations
                    for operation
                    in candidate_operations
                )
                and (
                    not candidate_targets
                    or all(
                        target
                        in final_targets
                        for target
                        in candidate_targets
                    )
                )
                and not observation.uncertainty
                and not observation.self_correction
            )

            if current_is_compatible:

                later_is_compatible = True

                for later in observations[
                    index:
                ]:

                    later_operations = [
                        normalize(
                            operation
                        )
                        for operation
                        in later.candidate_operations
                    ]

                    later_targets = [
                        normalize(
                            target
                        )
                        for target
                        in later.candidate_targets
                    ]

                    if (
                        later_operations
                        and not all(
                            operation
                            in final_operations
                            for operation
                            in later_operations
                        )
                    ):
                        later_is_compatible = False
                        break

                    if (
                        later_targets
                        and not all(
                            target
                            in final_targets
                            for target
                            in later_targets
                        )
                    ):
                        later_is_compatible = False
                        break

                    if later.self_correction:
                        later_is_compatible = False
                        break

                if (
                    later_is_compatible
                    and first_safe is None
                ):
                    first_safe = (
                        observation.elapsed_seconds
                    )

                    observation.retrospectively_safe = True

    return {
        "first_candidate": first_candidate,
        "first_safe": first_safe,
        "median_readiness": (
            median_or_none(
                readiness_values
            )
        ),
        "max_readiness": (
            max(
                readiness_values
            )
            if readiness_values
            else None
        ),
        "reversals": reversals,
        "self_corrections": self_corrections,
        "repetitions": repetitions,
        "stagnation": stagnation,
    }


# ============================================================
# ONE OLLAMA RUN
# ============================================================

def run_once(
    client: Client,
    task: Task,
    mode: str,
    run_index: int,
) -> RunResult:

    if mode == "baseline_think_true":
        think = True
        system_prompt = (
            BASE_SYSTEM_PROMPT
        )

    elif mode == "baseline_think_false":
        think = False
        system_prompt = (
            BASE_SYSTEM_PROMPT
        )

    elif mode == "strong_commit_control":
        think = True
        system_prompt = (
            STRONG_COMMIT_PROMPT
        )

    else:
        raise ValueError(
            f"Unknown mode: {mode}"
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": task.prompt,
        },
    ]

    started = clock()

    first_chunk = None
    first_thinking = None
    first_content = None
    first_tool_call = None

    thinking_parts: list[str] = []
    content_parts: list[str] = []

    observations: list[
        PrefixObservation
    ] = []

    previous_operations: list[str] = []

    final_tool_calls: list[
        dict[str, Any]
    ] = []

    sequence = 0

    try:

        stream = client.chat(
            model=MODEL,
            messages=messages,
            tools=JARVIS_TOOLS,
            stream=True,
            think=think,
            keep_alive=KEEP_ALIVE,
            options={
                "num_ctx": CONTEXT_SIZE,
            },
        )

        for chunk in stream:

            elapsed = (
                clock()
                - started
            )

            if first_chunk is None:
                first_chunk = elapsed

            message = getattr(
                chunk,
                "message",
                None,
            )

            if message is None:
                continue

            thinking_piece = (
                getattr(
                    message,
                    "thinking",
                    None,
                )
                or ""
            )

            content_piece = (
                getattr(
                    message,
                    "content",
                    None,
                )
                or ""
            )

            if thinking_piece:

                if first_thinking is None:
                    first_thinking = elapsed

                thinking_parts.append(
                    str(
                        thinking_piece
                    )
                )

            if content_piece:

                if first_content is None:
                    first_content = elapsed

                content_parts.append(
                    str(
                        content_piece
                    )
                )

            calls = extract_tool_calls(
                message
            )

            if (
                calls
                and first_tool_call is None
            ):
                first_tool_call = elapsed

                final_tool_calls = (
                    calls
                )

            if (
                thinking_piece
                or content_piece
                or calls
            ):

                sequence += 1

                current_thinking = (
                    "".join(
                        thinking_parts
                    )
                )

                current_content = (
                    "".join(
                        content_parts
                    )
                )

                observation = (
                    build_prefix_observation(
                        sequence=sequence,
                        elapsed=elapsed,
                        thinking=current_thinking,
                        content=current_content,
                        task=task,
                        previous_operations=(
                            previous_operations
                        ),
                    )
                )

                observations.append(
                    observation
                )

                previous_operations = (
                    list(
                        observation.candidate_operations
                    )
                )

    except Exception as exc:

        print(
            (
                f"[ERROR] "
                f"{task.name} "
                f"/ {mode} "
                f"/ run {run_index}: "
                f"{exc}"
            ),
            file=sys.stderr,
        )

    total_seconds = (
        clock()
        - started
    )

    analysis = annotate_ground_truth(
        observations,
        final_tool_calls,
        task,
    )

    expected_operation = normalize(
        task.expected_operation
        or ""
    )

    final_operation_names = [
        normalize(
            call["name"]
        )
        for call in final_tool_calls
    ]

    if task.expected_operation:
        correct_operation = (
            expected_operation
            in final_operation_names
        )
    else:
        correct_operation = (
            not final_operation_names
        )

    if task.expected_target:

        expected_target = normalize(
            task.expected_target
        )

        actual_targets = [
            normalize(
                extract_call_target(
                    call
                )
                or ""
            )
            for call
            in final_tool_calls
        ]

        correct_target = (
            expected_target
            in actual_targets
        )

    else:
        correct_target = True

    correct_call = (
        correct_operation
        and correct_target
    )
    candidate_gap = None

    if (
        analysis["first_candidate"] is not None
        and first_tool_call is not None
    ):
        candidate_gap = (
            first_tool_call
            - analysis["first_candidate"]
        )

    safe_gap = None

    if (
        analysis["first_safe"] is not None
        and first_tool_call is not None
    ):
        safe_gap = (
            first_tool_call
            - analysis["first_safe"]
        )

    post_commit = None

    if first_tool_call is not None:
        post_commit = (
            total_seconds
            - first_tool_call
        )

    return RunResult(
        task=task.name,
        category=task.category,
        mode=mode,
        run_index=run_index,
        total_seconds=total_seconds,
        first_chunk_seconds=first_chunk,
        first_thinking_seconds=first_thinking,
        first_content_seconds=first_content,
        first_tool_call_seconds=(
            first_tool_call
        ),
        post_commit_seconds=post_commit,
        thinking_chars=len(
            "".join(
                thinking_parts
            )
        ),
        content_chars=len(
            "".join(
                content_parts
            )
        ),
        total_chars=(
            len(
                "".join(
                    thinking_parts
                )
            )
            + len(
                "".join(
                    content_parts
                )
            )
        ),
        tool_calls=final_tool_calls,
        correct_operation=(
            correct_operation
        ),
        correct_target=(
            correct_target
        ),
        correct_call=(
            correct_call
        ),
        first_candidate_seconds=(
            analysis[
                "first_candidate"
            ]
        ),
        first_safe_prefix_seconds=(
            analysis[
                "first_safe"
            ]
        ),
        candidate_to_tool_gap_seconds=(
            candidate_gap
        ),
        safe_to_tool_gap_seconds=(
            safe_gap
        ),
        max_readiness_before_tool=(
            analysis[
                "max_readiness"
            ]
        ),
        median_readiness_before_tool=(
            analysis[
                "median_readiness"
            ]
        ),
        reversal_count=(
            analysis[
                "reversals"
            ]
        ),
        self_correction_count=(
            analysis[
                "self_corrections"
            ]
        ),
        repeated_prefix_count=(
            analysis[
                "repetitions"
            ]
        ),
        stagnation_indicator_count=(
            analysis[
                "stagnation"
            ]
        ),
        prefix_count=len(
            observations
        ),
        observations=observations,
    )


# ============================================================
# REPORTING
# ============================================================

def format_seconds(
    value: float | None,
) -> str:

    if value is None:
        return "n/a"

    return f"{value:.3f}s"


def summarize(
    results: list[RunResult],
    attribute: str,
) -> str:

    values = [
        getattr(
            result,
            attribute,
        )
        for result in results
        if getattr(
            result,
            attribute,
        )
        is not None
    ]

    if not values:
        return "n/a"

    return format_seconds(
        statistics.median(
            values
        )
    )


def print_run(
    result: RunResult,
) -> None:

    calls = []

    for call in result.tool_calls:

        calls.append(
            (
                f"{call['name']}"
                f"("
                f"{call.get('arguments', {})}"
                f")"
            )
        )

    call_text = (
        ", ".join(calls)
        if calls
        else "none"
    )

    print(
        "\n"
        f"RUN | "
        f"{result.task} | "
        f"{result.mode} | "
        f"#{result.run_index}\n"
        f"  total:       "
        f"{format_seconds(result.total_seconds)}\n"
        f"  first chunk: "
        f"{format_seconds(result.first_chunk_seconds)}\n"
        f"  first think: "
        f"{format_seconds(result.first_thinking_seconds)}\n"
        f"  first tool:  "
        f"{format_seconds(result.first_tool_call_seconds)}\n"
        f"  candidate:   "
        f"{format_seconds(result.first_candidate_seconds)}\n"
        f"  safe prefix: "
        f"{format_seconds(result.first_safe_prefix_seconds)}\n"
        f"  candidate→tool:"
        f"{format_seconds(result.candidate_to_tool_gap_seconds)}\n"
        f"  safe→tool:   "
        f"{format_seconds(result.safe_to_tool_gap_seconds)}\n"
        f"  readiness:   "
        f"{result.max_readiness_before_tool}\n"
        f"  reversals:   "
        f"{result.reversal_count}\n"
        f"  correction:  "
        f"{result.self_correction_count}\n"
        f"  repetition:  "
        f"{result.repeated_prefix_count}\n"
        f"  correct:      "
        f"{result.correct_call}\n"
        f"  calls:        "
        f"{call_text}",
        flush=True,
    )


def print_signal_trace(
    result: RunResult,
) -> None:

    print(
        "\n"
        + "-" * 80
    )

    print(
        "SIGNAL TRACE | "
        f"{result.task} | "
        f"{result.mode} | "
        f"run {result.run_index}"
    )

    print(
        "seq | time | ready | action | target | "
        "uncertain | correction | repeat | candidates"
    )

    observations = (
        result.observations
    )

    if len(
        observations
    ) > 30:

        step = max(
            1,
            len(observations)
            // 15,
        )

        indexes = sorted(
            set(
                [0, 1, 2]
                + list(
                    range(
                        3,
                        len(observations),
                        step,
                    )
                )
                + [
                    len(observations)
                    - 1
                ]
            )
        )

        observations = [
            observations[index]
            for index
            in indexes
        ]

    for observation in observations:

        candidates = (
            ",".join(
                observation.candidate_operations
            )
            or "-"
        )

        print(
            f"{observation.sequence:03d} | "
            f"{observation.elapsed_seconds:6.3f} | "
            f"{observation.readiness_score:5.2f} | "
            f"{observation.action_completeness:5.2f} | "
            f"{observation.target_completeness:5.2f} | "
            f"{str(observation.uncertainty):9} | "
            f"{str(observation.self_correction):10} | "
            f"{str(observation.repetition):7} | "
            f"{candidates}"
        )


def print_summary(
    results: list[RunResult],
) -> None:

    print(
        "\n"
        + "=" * 80
    )

    print(
        "JARVIS — ADAPTIVE REASONING STUDY"
    )

    print(
        "=" * 80
    )

    print(
        f"Model:          {MODEL}"
    )

    print(
        f"Ollama host:    {OLLAMA_HOST}"
    )

    print(
        f"Context size:   {CONTEXT_SIZE}"
    )

    print(
        f"Runs/task/mode: {RUNS}"
    )

    print(
        f"Total runs:     {len(results)}"
    )

    print()

    correct_count = sum(
        result.correct_call
        for result in results
    )

    structured_count = sum(
        bool(
            result.tool_calls
        )
        for result in results
    )

    print(
        "OVERALL"
    )

    print(
        "-" * 80
    )

    print(
        f"Structured calls: "
        f"{structured_count}/{len(results)}"
    )

    print(
        f"Correct calls:    "
        f"{correct_count}/{len(results)}"
    )

    if results:

        print(
            f"Correctness:      "
            f"{correct_count / len(results) * 100:.1f}%"
        )

    print(
        f"Median total:     "
        f"{summarize(results, 'total_seconds')}"
    )

    print(
        f"Median tool:      "
        f"{summarize(results, 'first_tool_call_seconds')}"
    )

    print(
        f"Median candidate: "
        f"{summarize(results, 'first_candidate_seconds')}"
    )

    print(
        f"Median safe:      "
        f"{summarize(results, 'first_safe_prefix_seconds')}"
    )

    print()

    # --------------------------------------------------------
    # MODE COMPARISON
    # --------------------------------------------------------

    print(
        "MODE COMPARISON"
    )

    print(
        "-" * 80
    )

    modes = sorted(
        {
            result.mode
            for result
            in results
        }
    )

    for mode in modes:

        subset = [
            result
            for result
            in results
            if result.mode
            == mode
        ]

        correct = sum(
            result.correct_call
            for result
            in subset
        )

        print(
            f"{mode:24} "
            f"correct={correct}/{len(subset)} | "
            f"tool={summarize(subset, 'first_tool_call_seconds')} | "
            f"total={summarize(subset, 'total_seconds')} | "
            f"safe={summarize(subset, 'first_safe_prefix_seconds')}"
        )

    print()

    # --------------------------------------------------------
    # TASK CATEGORIES
    # --------------------------------------------------------

    print(
        "TASK CATEGORIES"
    )

    print(
        "-" * 80
    )

    categories = sorted(
        {
            result.category
            for result
            in results
        }
    )

    for category in categories:

        subset = [
            result
            for result
            in results
            if result.category
            == category
        ]

        correct = sum(
            result.correct_call
            for result
            in subset
        )

        print(
            f"{category:20} "
            f"runs={len(subset):3d} | "
            f"correct={correct:3d} | "
            f"candidate={summarize(subset, 'first_candidate_seconds')} | "
            f"safe={summarize(subset, 'first_safe_prefix_seconds')} | "
            f"tool={summarize(subset, 'first_tool_call_seconds')}"
        )

    print()

    # --------------------------------------------------------
    # OPTIMIZATION WINDOW
    # --------------------------------------------------------

    candidate_gaps = [
        result.candidate_to_tool_gap_seconds
        for result
        in results
        if result.candidate_to_tool_gap_seconds
        is not None
    ]

    safe_gaps = [
        result.safe_to_tool_gap_seconds
        for result
        in results
        if result.safe_to_tool_gap_seconds
        is not None
    ]

    print(
        "OPTIMIZATION WINDOW"
    )

    print(
        "-" * 80
    )

    print(
        "Candidate → tool:",
        format_seconds(
            median_or_none(
                candidate_gaps
            )
        ),
    )

    print(
        "Safe → tool:     ",
        format_seconds(
            median_or_none(
                safe_gaps
            )
        ),
    )

    print()

    # --------------------------------------------------------
    # REASONING BEHAVIOUR
    # --------------------------------------------------------

    print(
        "REASONING BEHAVIOUR"
    )

    print(
        "-" * 80
    )

    print(
        "Candidate reversals:",
        sum(
            result.reversal_count
            for result
            in results
        ),
    )

    print(
        "Self-corrections:",
        sum(
            result.self_correction_count
            for result
            in results
        ),
    )

    print(
        "Repeated prefixes:",
        sum(
            result.repeated_prefix_count
            for result
            in results
        ),
    )

    print(
        "Stagnation indicators:",
        sum(
            result.stagnation_indicator_count
            for result
            in results
        ),
    )

    print()

    # --------------------------------------------------------
    # DECISION
    # --------------------------------------------------------

    print(
        "PRELIMINARY DECISION"
    )

    print(
        "-" * 80
    )

    if not results:

        print(
            "NO DATA."
        )

        return

    correctness = (
        correct_count
        / len(results)
    )

    safe_count = sum(
        result.first_safe_prefix_seconds
        is not None
        for result
        in results
    )

    reversal_count = sum(
        result.reversal_count
        for result
        in results
    )

    if (
        correctness >= 0.95
        and safe_count > 0
    ):

        print(
            "PROMISING: adaptive commit deserves "
            "a controlled controller experiment."
        )

    elif correctness >= 0.90:

        print(
            "PROMISING BUT NOT SAFE YET: "
            "signal validation needs to become stricter."
        )

    else:

        print(
            "NOT SAFE YET: do not implement automatic "
            "reasoning interruption."
        )

    if reversal_count:

        print(
            "Important: candidate reversals occurred."
        )

        print(
            "Candidate persistence alone must NOT "
            "be treated as a commit signal."
        )

    if candidate_gaps:

        print(
            "There is measurable latency between "
            "candidate detection and structured execution."
        )

    print(
        "The next production step, if justified, should "
        "observe the model rather than reconstruct its "
        "partial reasoning."
    )


# ============================================================
# JSON OUTPUT
# ============================================================

def write_json(
    results: list[RunResult],
) -> None:

    payload = {
        "study": {
            "model": MODEL,
            "ollama_host": OLLAMA_HOST,
            "context_size": CONTEXT_SIZE,
            "runs_per_task_mode": RUNS,
            "generated_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            ),
        },
        "principle": (
            "Complete generation is observed. "
            "No stream interruption or partial-reasoning "
            "reconstruction is used."
        ),
        "results": [
            asdict(result)
            for result
            in results
        ],
    }

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=True,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    print(
        "=" * 80
    )

    print(
        "JARVIS ADAPTIVE REASONING STUDY"
    )

    print(
        "=" * 80
    )

    print(
        f"Model:  {MODEL}"
    )

    print(
        f"Host:   {OLLAMA_HOST}"
    )

    print(
        f"Ctx:    {CONTEXT_SIZE}"
    )

    print(
        f"Runs:   {RUNS}"
    )

    print()

    # --------------------------------------------------------
    # CONNECTIVITY
    # --------------------------------------------------------

    client = Client(
        host=OLLAMA_HOST
    )

    try:

        client.list()

    except Exception as exc:

        print(
            "ERROR: Ollama is not reachable."
        )

        print(
            f"Host: {OLLAMA_HOST}"
        )

        print(
            f"Error: {exc}"
        )

        return 2

    # --------------------------------------------------------
    # MODEL CHECK
    # --------------------------------------------------------

    try:

        client.show(
            MODEL
        )

    except Exception as exc:

        print(
            f"ERROR: Could not load/check model "
            f"'{MODEL}': {exc}"
        )

        return 3

    # --------------------------------------------------------
    # TASK FILTER
    # --------------------------------------------------------

    requested_tasks = os.getenv(
        "JARVIS_STUDY_TASKS",
        "all",
    ).strip()

    if requested_tasks.lower() == "all":

        selected_tasks = list(
            TASKS
        )

    else:

        requested_names = {
            item.strip()
            for item
            in requested_tasks.split(",")
            if item.strip()
        }

        selected_tasks = [
            task
            for task
            in TASKS
            if task.name
            in requested_names
        ]

    if not selected_tasks:

        print(
            "ERROR: No tasks selected."
        )

        return 4

    print(
        "TASKS"
    )

    print(
        "-" * 80
    )

    for task in selected_tasks:

        print(
            f"{task.name:28} "
            f"[{task.category}] "
            f"{task.prompt}"
        )

    print()

    # --------------------------------------------------------
    # MODES
    # --------------------------------------------------------

    modes = (
        "baseline_think_true",
        "baseline_think_false",
        "strong_commit_control",
    )

    results: list[
        RunResult
    ] = []

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    for task in selected_tasks:

        for mode in modes:

            for run_index in range(
                1,
                RUNS + 1,
            ):

                print(
                    "\n"
                    f"[{task.name}] "
                    f"{mode} "
                    f"run "
                    f"{run_index}/{RUNS}",
                    flush=True,
                )

                result = run_once(
                    client=client,
                    task=task,
                    mode=mode,
                    run_index=run_index,
                )

                results.append(
                    result
                )

                print_run(
                    result
                )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print_summary(
        results
    )

    # --------------------------------------------------------
    # TRACE
    #
    # Print detailed traces only for action-oriented tasks.
    # Complete traces remain in JSON.
    # --------------------------------------------------------

    for result in results:

        if result.category != "conversation":

            print_signal_trace(
                result
            )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:

        write_json(
            results
        )

        print(
            "\n"
            f"Evidence written to: "
            f"{OUTPUT_JSON}"
        )

    except Exception as exc:

        print(
            "\n"
            f"[WARN] Could not write JSON evidence: "
            f"{exc}",
            file=sys.stderr,
        )

    print(
        "\nSTUDY COMPLETE"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )