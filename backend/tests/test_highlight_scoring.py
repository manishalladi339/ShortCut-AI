"""Tests for deterministic highlight ranking."""
from services.highlight_scoring import (
    combine_scores,
    heuristic_highlight_score,
    select_non_overlapping,
)


def test_hook_like_unit_scores_above_fragment():
    strong, strong_reasons = heuristic_highlight_score(
        {
            "start": 2.0,
            "end": 10.0,
            "text": "But why is this the biggest mistake? Because 80% of people skip this step.",
        },
        asset_duration_sec=100.0,
    )
    weak, _ = heuristic_highlight_score(
        {"start": 90.0, "end": 91.0, "text": "and then"},
        asset_duration_sec=100.0,
    )
    assert strong > weak
    assert strong_reasons


def test_relevance_can_raise_final_score():
    low = combine_scores(0.5, -0.5)
    high = combine_scores(0.5, 0.8)
    assert high > low


def test_selection_prevents_temporal_overlap():
    candidates = [
        {
            "asset_id": "a",
            "start": 0.0,
            "end": 10.0,
            "final_score": 0.9,
            "reasons": [],
        },
        {
            "asset_id": "a",
            "start": 5.0,
            "end": 12.0,
            "final_score": 0.8,
            "reasons": [],
        },
        {
            "asset_id": "a",
            "start": 12.0,
            "end": 18.0,
            "final_score": 0.7,
            "reasons": [],
        },
    ]
    selected = select_non_overlapping(
        candidates,
        target_duration_sec=30,
        max_clips=5,
        min_clip_sec=2,
        max_clip_sec=20,
    )
    assert [(item["start"], item["end"]) for item in selected] == [(0.0, 10.0), (12.0, 18.0)]
