"""Planner evaluation coverage for transition-bearing B-roll."""
from services.planner_evaluation import evaluate_plan


def _plan(transition_duration: int) -> dict:
    transition = {"kind": "fade", "duration": transition_duration}
    return {
        "candidates": [],
        "operations": [
            {
                "operation": "add_broll_overlay",
                "payload": {
                    "asset_id": "asset-b",
                    "duration": 1000,
                    "transition_in": transition,
                    "transition_out": transition,
                    "metadata": {
                        "source_intelligence_id": "intel-b",
                        "source_observation_index": 1,
                    },
                },
            }
        ],
    }


def test_counts_valid_faded_overlay():
    result = evaluate_plan(_plan(180))
    assert result["faded_overlay_count"] == 1
    assert result["transitions_valid"] is True
    assert result["all_operations_grounded"] is True


def test_rejects_transition_longer_than_overlay():
    result = evaluate_plan(_plan(1500))
    assert result["faded_overlay_count"] == 1
    assert result["transitions_valid"] is False
