"""Tests for planner evaluation metrics."""
from services.planner_evaluation import evaluate_plan


def test_evaluation_tracks_grounding_and_roles():
    plan = {
        "candidates": [
            {
                "asset_id": "a",
                "unit_index": 1,
                "start": 0.0,
                "end": 5.0,
                "final_score": 0.9,
                "narrative_role": "hook",
            },
            {
                "asset_id": "a",
                "unit_index": 2,
                "start": 5.0,
                "end": 12.0,
                "final_score": 0.8,
                "narrative_role": "payoff",
            },
        ],
        "story_beats": [
            {
                "id": "beat-01",
                "role": "hook",
                "evidence_keys": ["a:1"],
            },
            {
                "id": "beat-02",
                "role": "payoff",
                "evidence_keys": ["a:2"],
            },
        ],
        "project_topics": [{"id": "topic-01"}],
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
                    "metadata": {"source_unit_index": 2},
                },
            },
        ],
    }
    result = evaluate_plan(plan)
    assert result["all_operations_grounded"] is True
    assert result["hook_present"] is True
    assert result["payoff_present"] is True
    assert result["selected_duration_sec"] == 12.0
    assert result["average_highlight_score"] == 0.85
    assert result["story_beat_count"] == 2
    assert result["story_beats_grounded"] is True
    assert result["project_topic_count"] == 1
