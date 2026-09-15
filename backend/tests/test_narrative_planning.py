"""Tests for grounded deterministic narrative ordering."""
from services.narrative_planning import deterministic_structure


def _candidate(key, text, score, start):
    return {
        "asset_id": "asset",
        "intelligence_id": "intel",
        "unit_index": key,
        "start": start,
        "end": start + 5.0,
        "text": text,
        "final_score": score,
    }


def test_deterministic_structure_assigns_hook_body_payoff():
    candidates = [
        _candidate(0, "Supporting context.", 0.65, 10),
        _candidate(1, "Why does this problem keep happening?", 0.92, 0),
        _candidate(2, "That is why this lesson matters.", 0.72, 20),
    ]
    result = deterministic_structure(
        objective="Create a concise explanation",
        project={"content_type": "podcast", "target_platforms": ["ig_reels"]},
        candidates=candidates,
        target_audience="Founders",
    )
    assert result["ordered_keys"][0] == "asset:1"
    assert result["roles"]["asset:1"] == "hook"
    assert result["roles"][result["ordered_keys"][-1]] == "payoff"
    assert result["audience_profile"]["description"] == "Founders"


def test_narrative_structure_never_invents_candidate_keys():
    candidates = [_candidate(4, "Only supplied clip.", 0.9, 0)]
    result = deterministic_structure(
        objective="Make a clip",
        project={},
        candidates=candidates,
        target_audience=None,
    )
    assert result["ordered_keys"] == ["asset:4"]
    assert set(result["roles"]) == {"asset:4"}
