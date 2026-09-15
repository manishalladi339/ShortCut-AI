"""Deterministic visual signals used by the edit planner.

These signals never replace transcript grounding. They add auditable context from
visual observations that overlap a transcript candidate's source time range.
"""
from __future__ import annotations


def observations_for_range(
    observations: list[dict], *, start: float, end: float
) -> list[dict]:
    return [
        item
        for item in observations
        if start <= float(item.get("time", -1.0)) <= end
    ]


def score_visual_context(observations: list[dict]) -> dict:
    """Return a small bounded editability score plus explainable features."""
    if not observations:
        return {
            "score": 0.0,
            "observation_count": 0,
            "people_present": False,
            "onscreen_text_present": False,
            "shot_variety": 0,
            "reasons": [],
        }

    shot_types = {
        str(item.get("shot_type") or "unknown").strip().lower()
        for item in observations
        if str(item.get("shot_type") or "").strip()
    }
    people_present = any(int(item.get("people_count") or 0) > 0 for item in observations)
    onscreen_text = any(item.get("text_on_screen") not in (None, "") for item in observations)
    described = sum(bool(str(item.get("description") or "").strip()) for item in observations)

    score = 0.0
    reasons: list[str] = []
    if described:
        score += min(0.08, 0.03 + 0.01 * described)
        reasons.append("visually described source coverage")
    if people_present:
        score += 0.05
        reasons.append("person visible in representative frame")
    if len(shot_types) >= 2:
        score += 0.04
        reasons.append("shot variety")
    if onscreen_text:
        score += 0.02
        reasons.append("on-screen text available for edit context")

    return {
        "score": round(min(score, 0.15), 4),
        "observation_count": len(observations),
        "people_present": people_present,
        "onscreen_text_present": onscreen_text,
        "shot_variety": len(shot_types),
        "reasons": reasons,
    }
