"""
JARVIS — TEST 1
Information Source Ground Truth
================================

Purpose
-------
Establish exactly what information exists in JARVIS BEFORE Retrieval,
Context compilation, Context Window management, or an LLM call.

This test is OBSERVATIONAL ONLY.

It does NOT:
    - call JarvisAgent.run()
    - call the LLM
    - perform retrieval
    - modify memories
    - modify conversations
    - modify diary entries
    - modify knowledge
    - modify relationships

It inspects the information services/repositories already used by
JarvisAgent and produces a structured diagnostic report.

Run from:
    backend/

Example:
    python test_information_sources.py
"""

from __future__ import annotations

import dataclasses
import json
import sys
import traceback
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============================================================================
# IMPORT JARVIS
# ============================================================================

try:
    from jarvis.core.agent import JarvisAgent
except Exception as exc:
    print("\n[IMPORT ERROR]")
    print(exc)
    traceback.print_exc()
    sys.exit(1)


# ============================================================================
# TERMINAL FORMATTING
# ============================================================================

WIDTH = 100

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"


def supports_color() -> bool:
    return sys.stdout.isatty()


if not supports_color():
    RESET = BOLD = DIM = CYAN = GREEN = YELLOW = RED = MAGENTA = ""


def line(char: str = "─") -> str:
    return char * WIDTH


def header(title: str) -> None:
    print()
    print(f"{BOLD}{CYAN}{line('═')}{RESET}")
    print(f"{BOLD}{CYAN}{title.center(WIDTH)}{RESET}")
    print(f"{BOLD}{CYAN}{line('═')}{RESET}")


def section(title: str) -> None:
    print()
    print(f"{BOLD}{MAGENTA}{'─' * 4} {title} {'─' * max(0, WIDTH - len(title) - 6)}{RESET}")


def subheader(title: str) -> None:
    print()
    print(f"{BOLD}{title}{RESET}")


def kv(key: str, value: Any, indent: int = 2) -> None:
    print(f"{' ' * indent}{key:<30}: {value}")


def status(ok: bool, text: str) -> None:
    symbol = "✓" if ok else "✗"
    colour = GREEN if ok else RED
    print(f"  {colour}{symbol}{RESET} {text}")


# ============================================================================
# SAFE SERIALIZATION
# ============================================================================

def safe_serialize(value: Any, depth: int = 0, max_depth: int = 8) -> Any:
    """
    Convert JARVIS objects into JSON-friendly diagnostic structures.

    This intentionally does not assume that every model is a dataclass.
    """

    if depth > max_depth:
        return "<MAX_DEPTH>"

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"

    if dataclasses.is_dataclass(value):
        result = {}

        for field in dataclasses.fields(value):
            try:
                result[field.name] = safe_serialize(
                    getattr(value, field.name),
                    depth + 1,
                    max_depth,
                )
            except Exception as exc:
                result[field.name] = f"<ERROR: {exc}>"

        return result

    if isinstance(value, dict):
        return {
            str(k): safe_serialize(v, depth + 1, max_depth)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            safe_serialize(item, depth + 1, max_depth)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        try:
            return safe_serialize(
                value.model_dump(),
                depth + 1,
                max_depth,
            )
        except Exception:
            pass

    if hasattr(value, "dict"):
        try:
            return safe_serialize(
                value.dict(),
                depth + 1,
                max_depth,
            )
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        result = {}

        for key, item in vars(value).items():
            if key.startswith("__"):
                continue

            try:
                result[key] = safe_serialize(
                    item,
                    depth + 1,
                    max_depth,
                )
            except Exception as exc:
                result[key] = f"<ERROR: {exc}>"

        if result:
            return result

    return str(value)


# ============================================================================
# TEXT REPRESENTATION / TOKEN ESTIMATION
# ============================================================================

def pretty_json(value: Any) -> str:
    try:
        return json.dumps(
            safe_serialize(value),
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return repr(value)


def estimate_tokens(text: str) -> int:
    """
    Deliberately uses the same crude approximation currently used by
    JARVIS's ContextWindowManager:

        len(text) // 4

    This is NOT a tokenizer measurement.

    It is used here so Test 1 remains comparable with the current
    JARVIS context-window diagnostics.
    """

    if not text:
        return 0

    return max(1, len(text) // 4)


def measure(value: Any) -> dict[str, Any]:
    serialized = pretty_json(value)

    return {
        "characters": len(serialized),
        "estimated_tokens": estimate_tokens(serialized),
    }


# ============================================================================
# GENERIC COLLECTION HELPERS
# ============================================================================

def as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, (tuple, set, frozenset)):
        return list(value)

    return [value]


def get_public_methods(obj: Any) -> list[str]:
    return sorted(
        name
        for name in dir(obj)
        if not name.startswith("_")
        and callable(getattr(obj, name, None))
    )


def call_first_available(
    obj: Any,
    candidates: list[tuple[str, tuple[Any, ...], dict[str, Any]]],
) -> tuple[str | None, Any, str | None]:
    """
    Try known read-only service APIs.

    Returns:
        (method_name, result, error)
    """

    errors = []

    for method_name, args, kwargs in candidates:

        method = getattr(obj, method_name, None)

        if method is None or not callable(method):
            continue

        try:
            return method_name, method(*args, **kwargs), None

        except TypeError as exc:
            errors.append(f"{method_name}: {exc}")
            continue

        except Exception as exc:
            return method_name, None, str(exc)

    if errors:
        return None, None, " | ".join(errors)

    return None, None, "No compatible read-only method found."


# ============================================================================
# DIAGNOSTIC STORAGE
# ============================================================================

REPORT: dict[str, Any] = {
    "test": "Test 1 — Information Source Ground Truth",
    "purpose": (
        "Measure what information is currently available to JARVIS "
        "before Retrieval and Context processing."
    ),
    "sources": {},
    "totals": {
        "objects": 0,
        "characters": 0,
        "estimated_tokens": 0,
    },
}


def record_source(
    name: str,
    source_type: str,
    data: Any,
    *,
    retrieval_method: str | None = None,
    notes: list[str] | None = None,
) -> None:

    serialized = pretty_json(data)
    metrics = measure(data)

    items = as_list(data)

    item_types = Counter(
        type(item).__name__
        for item in items
    )

    source_report = {
        "source_type": source_type,
        "retrieval_method": retrieval_method,
        "count": len(items),
        "characters": metrics["characters"],
        "estimated_tokens": metrics["estimated_tokens"],
        "item_types": dict(item_types),
        "notes": notes or [],
        "data": safe_serialize(data),
    }

    REPORT["sources"][name] = source_report

    REPORT["totals"]["objects"] += len(items)
    REPORT["totals"]["characters"] += metrics["characters"]
    REPORT["totals"]["estimated_tokens"] += metrics["estimated_tokens"]


def print_source_summary(name: str) -> None:

    report = REPORT["sources"][name]

    print()
    print(f"{BOLD}{name}{RESET}")

    kv("Source type", report["source_type"])
    kv("Read method", report["retrieval_method"])
    kv("Objects", report["count"])
    kv("Characters", report["characters"])
    kv("Estimated tokens", report["estimated_tokens"])

    if report["item_types"]:
        kv("Object types", report["item_types"])

    for note in report["notes"]:
        print(f"  {YELLOW}NOTE:{RESET} {note}")


def print_source_data(name: str) -> None:

    report = REPORT["sources"][name]

    print()
    print(f"{BOLD}{name} — RAW DATA{RESET}")
    print(line())
    print(
        json.dumps(
            report["data"],
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


# ============================================================================
# STATE
# ============================================================================

def inspect_state(agent: JarvisAgent) -> None:

    section("1. AGENT STATE")

    state = agent.state

    record_source(
        "Agent State",
        "State",
        state,
        notes=[
            "Current runtime state object.",
            "This is not a retrieval result.",
            "This test does not modify the state.",
        ],
    )

    print_source_summary("Agent State")
    print_source_data("Agent State")


# ============================================================================
# CORE MEMORY
# ============================================================================

def inspect_core_memory(agent: JarvisAgent) -> None:

    section("2. CORE MEMORY")

    method_name, blocks, error = call_first_available(
        agent.core_memory,
        [
            ("list_blocks", (), {}),
        ],
    )

    if error is not None:
        print(f"{RED}Unable to inspect Core Memory:{RESET} {error}")

        record_source(
            "Core Memory",
            "Core Memory",
            [],
            retrieval_method=None,
            notes=[error],
        )
        return

    blocks = as_list(blocks)

    record_source(
        "Core Memory",
        "Core Memory",
        blocks,
        retrieval_method=method_name,
        notes=[
            "All blocks returned by CoreMemoryService.list_blocks().",
            "These are persistent core-memory objects, not compiled context.",
        ],
    )

    print_source_summary("Core Memory")
    print_source_data("Core Memory")


# ============================================================================
# CONVERSATION / RECALL
# ============================================================================

def inspect_conversation(agent: JarvisAgent) -> None:

    section("3. CONVERSATION / RECALL")

    conversation_id = getattr(
        agent.state,
        "conversation_id",
        None,
    )

    if conversation_id is None:
        print(
            f"{YELLOW}No conversation_id exists in AgentState.{RESET}"
        )

        record_source(
            "Conversation / Recall",
            "Recall",
            [],
            notes=[
                "AgentState.conversation_id is None.",
            ],
        )
        return

    method_name, messages, error = call_first_available(
        agent.recall,
        [
            (
                "get_messages",
                (),
                {
                    "conversation_id": conversation_id,
                },
            ),
            (
                "get_messages",
                (conversation_id,),
                {},
            ),
        ],
    )

    if error is not None:
        print(
            f"{RED}Unable to inspect conversation:{RESET} {error}"
        )

        record_source(
            "Conversation / Recall",
            "Recall",
            [],
            retrieval_method=None,
            notes=[error],
        )
        return

    messages = as_list(messages)

    record_source(
        "Conversation / Recall",
        "Recall / Conversation History",
        messages,
        retrieval_method=method_name,
        notes=[
            f"Conversation ID: {conversation_id}",
            "This represents persisted conversation history.",
            "It is distinct from Agent.messages runtime state.",
        ],
    )

    print_source_summary("Conversation / Recall")
    print_source_data("Conversation / Recall")


# ============================================================================
# RUNTIME CONVERSATION
# ============================================================================

def inspect_runtime_conversation(agent: JarvisAgent) -> None:

    section("4. AGENT RUNTIME CONVERSATION")

    messages = list(
        getattr(agent, "messages", []) or []
    )

    record_source(
        "Agent Runtime Conversation",
        "Agent Runtime State",
        messages,
        notes=[
            "This is self.messages currently held by JarvisAgent.",
            "It is not the same object as ConversationRepository.",
            "It is the conversation representation later passed into ContextRequest.",
        ],
    )

    print_source_summary("Agent Runtime Conversation")
    print_source_data("Agent Runtime Conversation")


# ============================================================================
# LONG-TERM MEMORY
# ============================================================================

def inspect_long_term_memory(agent: JarvisAgent) -> None:

    section("5. LONG-TERM MEMORY")

    method_name, memories, error = call_first_available(
        agent.memory,
        [
            (
                "list",
                (),
                {
                    "include_superseded": False,
                },
            ),
            (
                "list",
                (),
                {},
            ),
        ],
    )

    if error is not None:
        print(
            f"{RED}Unable to inspect Long-Term Memory:{RESET} {error}"
        )

        record_source(
            "Long-Term Memory",
            "Long-Term Memory",
            [],
            notes=[error],
        )
        return

    memories = as_list(memories)

    record_source(
        "Long-Term Memory",
        "Long-Term Memory",
        memories,
        retrieval_method=method_name,
        notes=[
            "Active memory records returned by LongTermMemoryService.",
            "Superseded memories are excluded when the API supports that argument.",
        ],
    )

    print_source_summary("Long-Term Memory")
    print_source_data("Long-Term Memory")


# ============================================================================
# KNOWLEDGE
# ============================================================================

def inspect_knowledge(agent: JarvisAgent) -> None:

    section("6. KNOWLEDGE")

    service = agent.knowledge

    public_methods = get_public_methods(service)

    print(
        f"  {DIM}KnowledgeService public methods detected:{RESET}"
    )

    print(
        "  "
        + ", ".join(public_methods)
    )

    # ------------------------------------------------------------------------
    # Important:
    #
    # KnowledgeService currently exposes search_passages(), which requires
    # a query. Test 1 is specifically about raw availability, so we do not
    # perform an arbitrary semantic/lexical query here.
    #
    # Instead we inspect the underlying repository's read-only collection
    # API when one is available.
    # ------------------------------------------------------------------------

    repository = getattr(
        service,
        "repository",
        None,
    )

    if repository is None:
        print(
            f"{YELLOW}"
            "KnowledgeService does not expose its repository as "
            "a public 'repository' attribute."
            f"{RESET}"
        )

        record_source(
            "Knowledge",
            "Knowledge",
            [],
            notes=[
                "KnowledgeService was inspected but a repository collection API "
                "could not be safely determined.",
                "Knowledge search itself is intentionally NOT performed in Test 1.",
            ],
        )
        return

    repository_methods = get_public_methods(repository)

    print(
        f"  {DIM}KnowledgeRepository public methods detected:{RESET}"
    )

    print(
        "  "
        + ", ".join(repository_methods)
    )

    # Try only generic read/list methods if they exist.
    method_name, documents, error = call_first_available(
        repository,
        [
            ("list", (), {}),
            ("all", (), {}),
            ("get_all", (), {}),
            ("list_documents", (), {}),
        ],
    )

    if error is not None:
        print(
            f"{YELLOW}"
            "Knowledge inventory could not be collected without "
            "performing a search:"
            f"{RESET} {error}"
        )

        record_source(
            "Knowledge",
            "Knowledge",
            [],
            retrieval_method=None,
            notes=[
                "KnowledgeService exposes search_passages(), but Test 1 "
                "does not execute an arbitrary search.",
                error,
            ],
        )
        return

    documents = as_list(documents)

    record_source(
        "Knowledge",
        "Knowledge Documents",
        documents,
        retrieval_method=method_name,
        notes=[
            "Read-only inventory of knowledge documents.",
            "This is NOT the same as retrieval results.",
            "Passage-level retrieval is intentionally deferred to Test 2.",
        ],
    )

    print_source_summary("Knowledge")
    print_source_data("Knowledge")


# ============================================================================
# RELATIONSHIPS
# ============================================================================

def inspect_relationships(agent: JarvisAgent) -> None:

    section("7. RELATIONSHIPS")

    method_name, relationships, error = call_first_available(
        agent.relationships,
        [
            ("all", (), {}),
        ],
    )

    if error is not None:
        print(
            f"{RED}Unable to inspect Relationships:{RESET} {error}"
        )

        record_source(
            "Relationships",
            "Relationship Store",
            [],
            notes=[error],
        )
        return

    relationships = as_list(relationships)

    record_source(
        "Relationships",
        "Relationship Store",
        relationships,
        retrieval_method=method_name,
        notes=[
            "RelationshipStore.all() returns the relationship inventory.",
            "This is particularly important because Retrieval's "
            "RelationshipProvider currently operates over this inventory.",
            "This test does NOT invoke Retrieval.",
        ],
    )

    print_source_summary("Relationships")
    print_source_data("Relationships")


# ============================================================================
# DIARY
# ============================================================================

def inspect_diary(agent: JarvisAgent) -> None:

    section("8. DIARY")

    conversation_id = getattr(
        agent.state,
        "conversation_id",
        None,
    )

    service = agent.diary

    public_methods = get_public_methods(service)

    print(
        f"  {DIM}DiaryService public methods detected:{RESET}"
    )

    print(
        "  "
        + ", ".join(public_methods)
    )

    # ------------------------------------------------------------------------
    # DiaryService is currently queried with either:
    #
    #     search(...)
    #
    # or:
    #
    #     recent(...)
    #
    # in Agent._build_context().
    #
    # Test 1 should not invent a search query.
    #
    # Therefore use recent() with a deliberately large diagnostic limit
    # if available. This is explicitly labeled as "recent", because it
    # cannot be assumed to equal the entire database.
    # ------------------------------------------------------------------------

    method_name, diary_entries, error = call_first_available(
        service,
        [
            (
                "recent",
                (),
                {
                    "conversation_id": conversation_id,
                    "limit": 1000,
                },
            ),
            (
                "recent",
                (),
                {
                    "limit": 1000,
                },
            ),
        ],
    )

    if error is not None:
        print(
            f"{YELLOW}"
            "Diary inventory could not be collected:"
            f"{RESET} {error}"
        )

        record_source(
            "Diary",
            "Diary",
            [],
            notes=[
                "Diary exposes search/recent behavior rather than a confirmed "
                "unbounded inventory API.",
                error,
            ],
        )
        return

    diary_entries = as_list(diary_entries)

    record_source(
        "Diary",
        "Diary",
        diary_entries,
        retrieval_method=method_name,
        notes=[
            "Collected through DiaryService.recent().",
            "This is a recent-entry inventory, not necessarily the complete diary.",
            "Test 2 will separately measure query-driven Diary selection.",
        ],
    )

    print_source_summary("Diary")
    print_source_data("Diary")


# ============================================================================
# OPERATION RESULTS
# ============================================================================

def inspect_operation_results(agent: JarvisAgent) -> None:

    section("9. CURRENT OPERATION RESULTS")

    results = list(
        getattr(agent, "operation_results", []) or []
    )

    record_source(
        "Operation Results",
        "Agent Runtime Operation State",
        results,
        notes=[
            "Current in-memory operation results held by JarvisAgent.",
            "These are runtime observations, not a persistent information source.",
            "At a fresh Agent instance this will normally be empty.",
        ],
    )

    print_source_summary("Operation Results")
    print_source_data("Operation Results")


# ============================================================================
# CAPABILITY INFORMATION
# ============================================================================

def inspect_capabilities(agent: JarvisAgent) -> None:

    section("10. CAPABILITIES")

    registry = getattr(
        agent,
        "capability_registry",
        None,
    )

    if registry is None:
        record_source(
            "Capabilities",
            "Capability Registry",
            [],
            notes=[
                "Agent has no capability_registry attribute.",
            ],
        )
        return

    try:
        discovered = registry.discover()

        record_source(
            "Capabilities",
            "Capability Registry",
            discovered,
            retrieval_method="capability_registry.discover()",
            notes=[
                "Capability definitions are included for diagnostic completeness.",
                "They are not memory records.",
                "Test 1 does not invoke any capability operation.",
            ],
        )

        print_source_summary("Capabilities")
        print_source_data("Capabilities")

    except Exception as exc:
        record_source(
            "Capabilities",
            "Capability Registry",
            [],
            notes=[f"discover() failed: {exc}"],
        )

        print(
            f"{YELLOW}Capability discovery failed:{RESET} {exc}"
        )


# ============================================================================
# SUMMARY TABLE
# ============================================================================

def print_summary_table() -> None:

    section("11. INFORMATION UNIVERSE — SUMMARY")

    print()
    print(
        f"{BOLD}"
        f"{'SOURCE':<32}"
        f"{'COUNT':>10}"
        f"{'CHARS':>15}"
        f"{'TOKENS*':>15}"
        f"{'TYPE':<25}"
        f"{RESET}"
    )

    print(line())

    for name, report in REPORT["sources"].items():

        print(
            f"{name:<32}"
            f"{report['count']:>10}"
            f"{report['characters']:>15,}"
            f"{report['estimated_tokens']:>15,}"
            f"{report['source_type']:<25}"
        )

    print(line())

    totals = REPORT["totals"]

    print(
        f"{BOLD}"
        f"{'TOTAL':<32}"
        f"{totals['objects']:>10}"
        f"{totals['characters']:>15,}"
        f"{totals['estimated_tokens']:>15,}"
        f"{RESET}"
    )

    print()
    print(
        f"{DIM}"
        "* Token estimate = serialized characters / 4. "
        "This is intentionally approximate."
        f"{RESET}"
    )


# ============================================================================
# DATA-SOURCE CHARACTERISTICS
# ============================================================================

def print_interpretation() -> None:

    section("12. WHAT THIS TEST ESTABLISHES")

    print()
    print(
        "This test establishes the INFORMATION UNIVERSE available to "
        "JARVIS before Retrieval and Context processing."
    )

    print()

    checks = [
        (
            "Agent State",
            "Current state object exists and can be inspected.",
        ),
        (
            "Core Memory",
            "Persistent core-memory blocks currently exist.",
        ),
        (
            "Conversation / Recall",
            "Persisted conversation history currently exists.",
        ),
        (
            "Runtime Conversation",
            "Agent.messages contains the current in-memory conversation representation.",
        ),
        (
            "Long-Term Memory",
            "Active persistent memories currently exist.",
        ),
        (
            "Knowledge",
            "Knowledge inventory is inspected where a safe read-only repository API exists.",
        ),
        (
            "Relationships",
            "RelationshipStore inventory is inspected directly.",
        ),
        (
            "Diary",
            "Recent diary inventory is inspected without inventing a search query.",
        ),
        (
            "Operation Results",
            "Current temporary operation observations are inspected.",
        ),
        (
            "Capabilities",
            "Available capability definitions are inspected.",
        ),
    ]

    for name, description in checks:
        print(f"  {GREEN}✓{RESET} {BOLD}{name}{RESET}")
        print(f"      {description}")

    print()
    print(
        f"{YELLOW}"
        "IMPORTANT:"
        f"{RESET} "
        "This test does NOT tell us what the LLM receives."
    )

    print(
        "That is deliberately deferred to Tests 2 and 3."
    )

    print()
    print(
        "The intended lineage is:"
    )

    print()
    print(
        "  AVAILABLE INFORMATION"
    )
    print(
        "          ↓"
    )
    print(
        "  Test 1  ← WE ARE HERE"
    )
    print(
        "          ↓"
    )
    print(
        "  RETRIEVAL / SELECTION"
    )
    print(
        "          ↓"
    )
    print(
        "  CONTEXT REQUEST"
    )
    print(
        "          ↓"
    )
    print(
        "  CONTEXT COMPILER"
    )
    print(
        "          ↓"
    )
    print(
        "  WINDOW MANAGEMENT"
    )
    print(
        "          ↓"
    )
    print(
        "  LLM INPUT"
    )


# ============================================================================
# JSON REPORT
# ============================================================================

def save_report() -> Path:

    output_path = (
        Path(__file__).resolve().parent
        / "test_information_sources_report.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            REPORT,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    return output_path


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    header(
        "J.A.R.V.I.S — TEST 1 — INFORMATION SOURCE GROUND TRUTH"
    )

    print()
    print(
        f"{BOLD}Purpose:{RESET} "
        "Determine exactly what information currently exists "
        "before Retrieval and Context processing."
    )

    print()
    print(
        f"{BOLD}Mode:{RESET} "
        "READ-ONLY / OBSERVATIONAL"
    )

    print()
    print(
        f"{BOLD}LLM call:{RESET} "
        f"{GREEN}NO{RESET}"
    )

    print(
        f"{BOLD}Retrieval call:{RESET} "
        f"{GREEN}NO{RESET}"
    )

    print(
        f"{BOLD}Agent.run():{RESET} "
        f"{GREEN}NO{RESET}"
    )

    print(
        f"{BOLD}Persistent mutation intended:{RESET} "
        f"{GREEN}NO{RESET}"
    )

    # ------------------------------------------------------------------------
    # Agent initialization
    # ------------------------------------------------------------------------

    section("INITIALIZING JARVIS")

    try:
        agent = JarvisAgent()

        status(
            True,
            "JarvisAgent initialized successfully.",
        )

    except Exception as exc:

        status(
            False,
            f"JarvisAgent initialization failed: {exc}",
        )

        traceback.print_exc()
        sys.exit(1)

    # ------------------------------------------------------------------------
    # Inspect every information source
    # ------------------------------------------------------------------------

    inspect_state(agent)
    inspect_core_memory(agent)
    inspect_conversation(agent)
    inspect_runtime_conversation(agent)
    inspect_long_term_memory(agent)
    inspect_knowledge(agent)
    inspect_relationships(agent)
    inspect_diary(agent)
    inspect_operation_results(agent)
    inspect_capabilities(agent)

    # ------------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------------

    print_summary_table()
    print_interpretation()

    # ------------------------------------------------------------------------
    # Save machine-readable report
    # ------------------------------------------------------------------------

    section("REPORT OUTPUT")

    try:
        output_path = save_report()

        status(
            True,
            f"JSON report written to: {output_path}",
        )

    except Exception as exc:

        status(
            False,
            f"Could not write JSON report: {exc}",
        )

    # ------------------------------------------------------------------------
    # End
    # ------------------------------------------------------------------------

    header(
        "TEST 1 COMPLETE"
    )

    print()
    print(
        f"{BOLD}Next diagnostic:{RESET} "
        "Test 2 — Retrieval → ContextRequest → Compiler → Window Manager"
    )

    print()


if __name__ == "__main__":
    main()