"""Tests for grounded B-roll candidate ranking."""
from services.broll_planning import build_visual_candidates, rank_broll_candidates, recommend_broll_for_highlight, visual_text


def test_visual_text_preserves_grounded_fields():
    text = visual_text({"description": "A chef chops tomatoes", "visible_objects": ["knife", "tomato"], "text_on_screen": "Step 1", "shot_type": "close-up"})
    assert "chef chops tomatoes" in text
    assert "knife" in text
    assert "Step 1" in text
    assert "close-up" in text


def test_build_visual_candidates_pairs_observations_and_vectors():
    record = {"id": "intel-1", "asset_id": "asset-1", "visual_observations": [{"time": 3.0, "description": "city skyline"}], "visual_vectors": [[1.0, 0.0]]}
    candidates = build_visual_candidates(record)
    assert candidates[0]["intelligence_id"] == "intel-1"
    assert candidates[0]["vector"] == [1.0, 0.0]


def test_broll_ranking_prefers_semantically_closer_visual():
    candidates = [{"asset_id": "a", "time": 2.0, "description": "car", "vector": [1.0, 0.0]}, {"asset_id": "b", "time": 5.0, "description": "tree", "vector": [0.0, 1.0]}]
    ranked = rank_broll_candidates(candidates, objective_vector=[0.9, 0.1], limit=2)
    assert ranked[0]["asset_id"] == "a"
    assert "vector" not in ranked[0]
    assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]


def test_recommendation_excludes_primary_talking_head_asset():
    candidates = [{"asset_id": "talking-head", "time": 2.0, "vector": [1.0, 0.0]}, {"asset_id": "broll", "time": 5.0, "vector": [0.8, 0.2]}]
    ranked = recommend_broll_for_highlight(highlight={"asset_id": "talking-head"}, visual_candidates=candidates, highlight_vector=[1.0, 0.0], limit=3)
    assert [item["asset_id"] for item in ranked] == ["broll"]


def test_broll_ranking_ignores_nonpositive_matches():
    candidates = [{"asset_id": "a", "vector": [-1.0, 0.0]}, {"asset_id": "b", "vector": [0.0, 1.0]}]
    assert rank_broll_candidates(candidates, objective_vector=[1.0, 0.0], limit=5) == []
