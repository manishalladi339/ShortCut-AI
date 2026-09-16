"""Tests for source-diverse Multi-Asset Director selection."""
from services.multi_asset_director import (
    build_director_brief,
    select_multi_asset_candidates,
)


def _candidate(asset, index, start, score, text=None):
    return {
        "asset_id": asset,
        "intelligence_id": f"intel-{asset}",
        "unit_index": index,
        "start": float(start),
        "end": float(start + 8),
        "text": text or f"{asset} moment {index}",
        "heuristic_score": score,
        "relevance_score": score,
        "final_score": score,
        "reasons": [],
        "narrative_role": None,
        "speakers": [f"{asset}-speaker"],
        "primary_speaker": f"{asset}-speaker",
        "source_segments": [],
        "dead_air_removed_sec": 0.0,
        "planned_duration_sec": None,
        "visual_context": None,
        "semantic_vector": [score, 1.0 - score],
    }


def _project_intelligence():
    return {
        "asset_count": 4,
        "topic_clusters": [
            {
                "id": "topic-origin",
                "member_keys": ["a:0", "b:0"],
            },
            {
                "id": "topic-failure",
                "member_keys": ["a:1", "c:0"],
            },
            {
                "id": "topic-proof",
                "member_keys": ["b:1", "c:1"],
            },
        ],
        "asset_summaries": [
            {
                "asset_id": "a",
                "semantic_unit_count": 4,
                "visual_observation_count": 3,
            },
            {
                "asset_id": "b",
                "semantic_unit_count": 4,
                "visual_observation_count": 2,
            },
            {
                "asset_id": "c",
                "semantic_unit_count": 4,
                "visual_observation_count": 2,
            },
            {
                "asset_id": "still",
                "semantic_unit_count": 0,
                "visual_observation_count": 1,
            },
        ],
        "speaker_presences": [
            {"asset_id": "a", "speaker": "speaker_0"},
            {"asset_id": "b", "speaker": "speaker_0"},
            {"asset_id": "c", "speaker": "speaker_0"},
        ],
    }


def test_multi_asset_selection_seeds_distinct_sources_and_topics():
    candidates = [
        _candidate("a", 0, 0, 0.96),
        _candidate("a", 1, 20, 0.94),
        _candidate("a", 2, 40, 0.92),
        _candidate("b", 0, 0, 0.84),
        _candidate("b", 1, 20, 0.82),
        _candidate("c", 0, 0, 0.78),
        _candidate("c", 1, 20, 0.76),
    ]

    selected = select_multi_asset_candidates(
        candidates,
        target_duration_sec=40,
        max_clips=8,
        min_clip_sec=2,
        max_clip_sec=12,
        min_source_assets=3,
        max_source_share=0.55,
        project_intelligence=_project_intelligence(),
    )

    assert {"a", "b", "c"}.issubset({item["asset_id"] for item in selected})
    covered = {
        topic
        for item in selected
        for topic in item.get("multi_asset_topics", [])
    }
    assert {"topic-origin", "topic-failure", "topic-proof"}.issubset(covered)
    assert any(
        "multi-source story diversity" in " ".join(item["reasons"])
        for item in selected
    )


def test_multi_asset_selection_caps_dominant_source_when_alternatives_exist():
    candidates = [
        *[_candidate("a", i, i * 10, 0.99 - i * 0.01) for i in range(6)],
        *[_candidate("b", i, i * 10, 0.75 - i * 0.01) for i in range(3)],
        *[_candidate("c", i, i * 10, 0.70 - i * 0.01) for i in range(3)],
    ]
    selected = select_multi_asset_candidates(
        candidates,
        target_duration_sec=48,
        max_clips=10,
        min_clip_sec=2,
        max_clip_sec=8,
        min_source_assets=3,
        max_source_share=0.50,
        project_intelligence=_project_intelligence(),
    )

    duration_by_asset = {}
    for item in selected:
        duration_by_asset[item["asset_id"]] = duration_by_asset.get(
            item["asset_id"], 0
        ) + item["end"] - item["start"]

    assert duration_by_asset["a"] <= 24.0001
    assert len(duration_by_asset) >= 3


def test_source_cap_relaxes_when_only_one_spoken_source_exists():
    candidates = [
        _candidate("a", 0, 0, 0.95),
        _candidate("a", 1, 12, 0.90),
        _candidate("a", 2, 24, 0.85),
    ]
    selected = select_multi_asset_candidates(
        candidates,
        target_duration_sec=24,
        max_clips=5,
        min_clip_sec=2,
        max_clip_sec=8,
        min_source_assets=3,
        max_source_share=0.40,
        project_intelligence={"topic_clusters": []},
    )
    assert sum(item["end"] - item["start"] for item in selected) >= 23.9


def test_director_brief_reports_source_mix_without_inventing_roles():
    selected = [
        {
            **_candidate("a", 0, 0, 0.9),
            "multi_asset_topics": ["topic-origin"],
        },
        {
            **_candidate("b", 0, 0, 0.8),
            "multi_asset_topics": ["topic-origin", "topic-proof"],
        },
    ]
    assets = [
        {"id": "a", "filename": "founder.mp4", "kind": "video"},
        {"id": "b", "filename": "customer.mp4", "kind": "video"},
        {"id": "still", "filename": "old-photo.jpg", "kind": "image"},
    ]
    brief = build_director_brief(
        objective="Tell the company story",
        target_duration_sec=120,
        selected=selected,
        project_intelligence=_project_intelligence(),
        assets=assets,
        min_source_assets=3,
        max_source_share=0.55,
    )

    assert brief["mode"] == "multi_asset"
    assert brief["selected_spoken_asset_count"] == 2
    assert brief["topic_coverage_count"] == 2
    assert "still" in brief["visual_support_asset_ids"]
    assert {item["role"] for item in brief["source_mix"]} == {
        "primary_spoken_source"
    }
