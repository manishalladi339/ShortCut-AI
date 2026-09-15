"""Tests for planner evaluation metrics."""
from services.planner_evaluation import evaluate_plan


def test_evaluation_tracks_grounding_and_roles():
    plan = {
        "candidates": [
            {"asset_id": "a", "unit_index": 1},
            {"asset_id": "a", "unit_index": 2},
        ],
        "operations": [
            {
                "operation": "add_clip",
                "payload": {
                    "asset_id": "a",
                    "duration": 5000,
                    "metadata": {
                        "source_unit_index": 1,
                        "highlight_score": 0.9,
                        "narrative_role": "hook",
                    },
                },
            },
            {
                "operation": "add_clip",
                "payload": {
                    "asset_id": "a",
                    "duration": 7000,
                    "metadata": {
                        "source_unit_index": 2,
                        "highlight_score": 0.8,
                        "narrative_role": "payoff",
                    },
                },
            },
        ],
    }
    result = evaluate_plan(plan)
    assert result["all_operations_grounded"] is True
    assert result["hook_present"] is True
    assert result["payoff_present"] is True
    assert result["selected_duration_sec"] == 12.0
