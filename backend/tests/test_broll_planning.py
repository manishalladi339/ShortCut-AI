"""Tests for B-roll candidate ranking."""
from services.broll_planning import rank_broll_candidates


def test_broll_ranking_prefers_semantically_closer_visual():
    candidates = [
        {"asset_id": "a", "time": 2.0, "description": "car", "vector": [1.0, 0.0]},
        {"asset_id": "b", "time": 5.0, "description": "tree", "vector": [0.0, 1.0]},
    ]
    ranked = rank_broll_candidates(candidates, objective_vector=[0.9, 0.1], limit=2)
    assert ranked[0]["asset_id"] == "a"
    assert "vector" not in ranked[0]
    assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]


def test_broll_ranking_ignores_nonpositive_matches():
    candidates = [
        {"asset_id": "a", "vector": [-1.0, 0.0]},
        {"asset_id": "b", "vector": [0.0, 1.0]},
    ]
    ranked = rank_broll_candidates(candidates, objective_vector=[1.0, 0.0], limit=5)
    assert ranked == []
