"""Tests for deterministic visual editability signals."""
from services.visual_edit_signals import observations_for_range, score_visual_context


def test_observations_are_grounded_to_source_range():
    observations = [
        {"time": 2.0, "description": "host", "people_count": 1},
        {"time": 8.0, "description": "product", "people_count": 0},
    ]
    result = observations_for_range(observations, start=0.0, end=5.0)
    assert len(result) == 1
    assert result[0]["time"] == 2.0


def test_visual_score_is_bounded_and_explainable():
    observations = [
        {
            "time": 2.0,
            "description": "speaker at desk",
            "shot_type": "medium",
            "people_count": 1,
            "text_on_screen": None,
        },
        {
            "time": 4.0,
            "description": "close-up of product",
            "shot_type": "close-up",
            "people_count": 0,
            "text_on_screen": "Demo",
        },
    ]
    result = score_visual_context(observations)
    assert 0.0 < result["score"] <= 0.15
    assert result["people_present"] is True
    assert result["onscreen_text_present"] is True
    assert result["shot_variety"] == 2
    assert result["reasons"]
