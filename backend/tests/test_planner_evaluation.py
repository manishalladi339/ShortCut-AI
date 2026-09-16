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
                    "transform": {
                        "scale": 3.2,
                        "position_x": -420.0,
                        "position_y": 0.0,
                        "rotation_deg": 0.0,
                        "opacity": 1.0,
                    },
                    "metadata": {
                        "source_unit_index": 1,
                        "reframe": {
                            "strategy": "single_visible_subject",
                            "confidence": 0.82,
                            "observation_index": 3,
                            "identity_claimed": False,
                        },
                    },
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
    assert result["smart_reframed_clip_count"] == 1
    assert result["transforms_valid"] is True



def test_evaluation_rejects_untraceable_reframe_metadata():
    plan = {
        "candidates": [
            {
                "asset_id": "a",
                "unit_index": 1,
                "start": 0.0,
                "end": 5.0,
                "final_score": 0.8,
            }
        ],
        "operations": [
            {
                "operation": "add_clip",
                "payload": {
                    "asset_id": "a",
                    "transform": {
                        "scale": 3.0,
                        "position_x": 0.0,
                        "position_y": 0.0,
                        "rotation_deg": 0.0,
                        "opacity": 1.0,
                    },
                    "metadata": {
                        "source_unit_index": 1,
                        "reframe": {
                            "strategy": "visible_speaking_cue",
                            "confidence": 0.9,
                            "observation_index": None,
                            "identity_claimed": True,
                        },
                    },
                },
            }
        ],
    }
    result = evaluate_plan(plan)
    assert result["all_operations_grounded"] is False
    assert result["smart_reframed_clip_count"] == 1
