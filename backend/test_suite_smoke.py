"""Pytest baseline runner for Jarvis manual integration tests.

The project historically stores tests as executable ``main()`` scripts.
This runner provides a single pytest entry point without rewriting every
existing test file into pytest style.
"""

import importlib


TEST_MODULES = [
    "test_agent_state",
    "test_context",
    "test_context_architecture",
    "test_conversation",
    "test_core_memory",
    "test_core_memory_context",
    "test_diary",
    "test_knowledge",
    "test_knowledge_ingestion",
    "test_knowledge_models",
    "test_knowledge_retrieval",
    "test_long_term_memory",
    "test_memory_candidate",
    "test_memory_consolidation",
    "test_memory_extraction",
    "test_memory_formation",
    "test_retrieval",
    "test_retrieval_compiler",
    "test_retrieval_integration",
]


def test_manual_suite() -> None:
    """Execute the project's existing manual tests as one pytest check."""

    for module_name in TEST_MODULES:
        module = importlib.import_module(module_name)
        main = getattr(module, "main", None)

        if not callable(main):
            raise AssertionError(
                f"{module_name} does not expose a callable main() test entry point."
            )

        main()
