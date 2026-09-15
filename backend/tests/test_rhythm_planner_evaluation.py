"""Planner evaluation metric for rhythm-aware overlays."""
from services.planner_evaluation import evaluate_plan


def test_evaluation_counts_rhythm_snapped_overlays():
    plan = {
        "candidates": [
            {
                "asset_id": "a",
                "unit_index": 1,
                "start": 0.0,
                "end": 5.0,
                "final_score": 0.8,
                "narrative_role": "hook",
            }
        ],
        "operations": [
            {
                "operation": "add_clip",
                "payload": {
                    "asset_id": "a",
                    "metadata": {"source_unit_index": 1},
                },
            },
            {
                "operation": "add_broll_overlay",
                "payload": {
                    "asset_id": "b",
                    "metadata": {
                        "source_intelligence_id": "intel-b",
                        "source_observation_index": 2,
                        "rhythm_snapped": True,
                    },
                },
            },
        ],
    }
    result = evaluate_plan(plan)
    assert result["rhythm_snapped_overlay_count"] == 1
    assert result["all_operations_grounded"] is True
