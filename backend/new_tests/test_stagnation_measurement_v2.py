from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.core.stagnation_detector import StagnationDetector


OUTPUT_PATH = (
    Path(__file__).parent
    / "stagnation_measurement_fake.jsonl"
)


def _run_scenario(
    name: str,
    observations: list[dict],
) -> dict:
    detector = StagnationDetector(window_size=3)

    detected_turns: list[int] = []
    results: list[dict] = []

    for observation in observations:
        result = detector.observe(
            content=observation.get("content", ""),
            tool_intents=tuple(
                observation.get("tool_intents", ())
            ),
            new_action_information=observation.get(
                "new_action_information",
                True,
            ),
            self_correction=observation.get(
                "self_correction",
                False,
            ),
        )

        results.append(
            {
                "turn": observation["turn"],
                "stagnant": result.stagnant,
                "repeated_content": (
                    result.repeated_content
                ),
                "repeated_tool_intent": (
                    result.repeated_tool_intent
                ),
                "no_new_action_information": (
                    result.no_new_action_information
                ),
                "repeated_self_correction": (
                    result.repeated_self_correction
                ),
            }
        )

        if result.stagnant:
            detected_turns.append(
                observation["turn"]
            )

    return {
        "scenario": name,
        "stagnation_detected": bool(
            detected_turns
        ),
        "stagnation_turns": detected_turns,
        "observations": results,
    }


SCENARIOS = {
    "healthy_progress": [
        {
            "turn": 1,
            "content": (
                "I need to open WhatsApp."
            ),
            "tool_intents": (
                "apps.launch:WhatsApp",
            ),
            "new_action_information": True,
        },
        {
            "turn": 2,
            "content": (
                "WhatsApp opened successfully."
            ),
            "tool_intents": (),
            "new_action_information": True,
        },
    ],
    "repeated_tool_intent": [
        {
            "turn": 1,
            "content": (
                "I will open WhatsApp."
            ),
            "tool_intents": (
                "apps.launch:WhatsApp",
            ),
            "new_action_information": True,
        },
        {
            "turn": 2,
            "content": (
                "I will open WhatsApp again."
            ),
            "tool_intents": (
                "apps.launch:WhatsApp",
            ),
            "new_action_information": False,
        },
    ],
    "repeated_content": [
        {
            "turn": 1,
            "content": (
                "I am checking what to do next."
            ),
            "tool_intents": (),
            "new_action_information": False,
        },
        {
            "turn": 2,
            "content": (
                "I am checking what to do next."
            ),
            "tool_intents": (),
            "new_action_information": False,
        },
    ],
    "self_correction_loop": [
        {
            "turn": 1,
            "content": (
                "I should open WhatsApp."
            ),
            "tool_intents": (),
            "new_action_information": False,
            "self_correction": True,
        },
        {
            "turn": 2,
            "content": (
                "Actually, I should open WhatsApp."
            ),
            "tool_intents": (),
            "new_action_information": False,
            "self_correction": True,
        },
    ],
}


@pytest.mark.parametrize(
    "scenario,observations",
    SCENARIOS.items(),
)
def test_stagnation_scenarios(
    scenario,
    observations,
):
    result = _run_scenario(
        scenario,
        observations,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    if scenario == "healthy_progress":
        assert result["stagnation_detected"] is False
    else:
        assert result["stagnation_detected"] is True


def test_write_measurement_results():
    results = [
        _run_scenario(
            name,
            observations,
        )
        for name, observations
        in SCENARIOS.items()
    ]

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as handle:
        for result in results:
            handle.write(
                json.dumps(result) + "\n"
            )

    assert OUTPUT_PATH.exists()