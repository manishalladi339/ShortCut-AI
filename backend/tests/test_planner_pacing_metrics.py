"""Planner evaluation metrics for conversation pacing."""
from services.planner_evaluation import evaluate_plan


def test_evaluation_uses_compacted_duration_and_dead_air_metrics():
    plan = {
        "candidates": [
            {
                "asset_id": "a",
                "unit_index": 1,
                "start": 0.0,
                "end": 10.0,
                "planned_duration_sec": 8.2,
                "dead_air_removed_sec": 1.8,
                "final_score": 0.9,
                "narrative_role": "hook",
                "primary_speaker": "A",
            },
            {
                "asset_id": "b",
                "unit_index": 2,
                "start": 20.0,
                "end": 25.0,
                "planned_duration_sec": 5.0,
                "dead_air_removed_sec": 0.0,
                "final_score": 0.8,
                "narrative_role": "payoff",
                "primary_speaker": "B",
            },
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
                "operation": "add_clip",
                "payload": {
                    "asset_id": "a",
                    "metadata": {"source_unit_index": 1},
                },
            },
            {
                "operation": "add_clip",
                "payload": {
                    "asset_id": "b",
                    "metadata": {"source_unit_index": 2},
                },
            },
        ],
    }

    result = evaluate_plan(plan)

    assert result["selected_duration_sec"] == 13.2
    assert result["dead_air_removed_sec"] == 1.8
    assert result["primary_clip_part_count"] == 3
    assert result["speaker_switch_count"] == 1
    assert result["max_same_speaker_run"] == 1
    assert result["all_operations_grounded"] is True
