"""Tests for grounded story-beat construction."""
from services.story_director import build_story_beats


def _candidate(index: int, role: str = "body") -> dict:
    return {
        "asset_id": "asset-a",
        "unit_index": index,
        "start": index * 5.0,
        "end": index * 5.0 + 4.0,
        "text": f"Evidence {index}",
        "narrative_role": role,
        "planned_duration_sec": 4.0,
    }


def test_story_director_builds_grounded_beats_with_duration_budget():
    candidates = [_candidate(i) for i in range(6)]
    intelligence = {
        "topic_clusters": [
            {
                "id": "topic-01",
                "label": "Founder · Failure",
                "evidence": [
                    {"asset_id": "asset-a", "unit_index": 0},
                    {"asset_id": "asset-a", "unit_index": 1},
                ],
            }
        ]
    }
    beats = build_story_beats(
        ordered_candidates=candidates,
        project_intelligence=intelligence,
        target_duration_sec=60,
    )

    assert [beat["role"] for beat in beats] == [
        "hook", "context", "development", "proof", "payoff"
    ]
    assert round(sum(beat["target_duration_sec"] for beat in beats), 3) == 60.0
    valid_keys = {f"asset-a:{i}" for i in range(6)}
    planned_keys = [
        key
        for beat in beats
        for key in beat["evidence_keys"]
    ]
    assert set(planned_keys) == valid_keys
    assert len(planned_keys) == len(set(planned_keys))
    assert beats[0]["topic_ids"] == ["topic-01"]


def test_story_director_single_source_moment_is_still_grounded():
    beats = build_story_beats(
        ordered_candidates=[_candidate(0)],
        project_intelligence={"topic_clusters": []},
        target_duration_sec=12,
    )
    assert len(beats) == 1
    assert beats[0]["role"] == "hook"
    assert beats[0]["evidence_keys"] == ["asset-a:0"]
    assert beats[0]["target_duration_sec"] == 12.0
