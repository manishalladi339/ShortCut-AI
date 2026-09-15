"""Transparent highlight scoring for transcript semantic units.

This is intentionally deterministic. It provides a defensible baseline before
LLM narrative ranking is added and makes evaluation possible.
"""
from __future__ import annotations

import math
import re

QUESTION_RE = re.compile(r"\?")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?%?\b")
HOOK_TERMS = {
    "but", "however", "secret", "mistake", "problem", "why", "how", "never",
    "best", "worst", "surprising", "important", "truth", "actually", "because",
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def heuristic_highlight_score(unit: dict, *, asset_duration_sec: float | None) -> tuple[float, list[str]]:
    text = str(unit.get("text") or "").strip()
    start = float(unit.get("start") or 0.0)
    end = float(unit.get("end") or start)
    duration = max(0.0, end - start)
    words = [token.lower().strip(".,!?;:'\"()[]{}") for token in text.split()]
    word_count = len([word for word in words if word])

    score = 0.18
    reasons: list[str] = []

    if 4.0 <= duration <= 18.0:
        score += 0.18
        reasons.append("concise standalone duration")
    elif duration < 2.0 or duration > 30.0:
        score -= 0.10

    if 8 <= word_count <= 55:
        score += 0.14
        reasons.append("dense spoken idea")

    hook_hits = sorted({word for word in words if word in HOOK_TERMS})
    if hook_hits:
        score += min(0.18, 0.045 * len(hook_hits))
        reasons.append("hook language: " + ", ".join(hook_hits[:4]))

    if QUESTION_RE.search(text):
        score += 0.10
        reasons.append("question structure")

    if NUMBER_RE.search(text):
        score += 0.08
        reasons.append("specific numeric detail")

    if any(char in text for char in ("!", "—", ":")):
        score += 0.04

    # Slight preference for early moments without dominating semantic relevance.
    if asset_duration_sec and asset_duration_sec > 0:
        position = start / asset_duration_sec
        if position <= 0.20:
            score += 0.06
            reasons.append("early hook position")
        elif position >= 0.90:
            score -= 0.03

    # Penalize units that look like transcription fragments.
    if text and text[-1] not in ".!?":
        score -= 0.04
    if word_count < 4:
        score -= 0.15

    return _clamp(score), reasons


def combine_scores(heuristic: float, relevance: float) -> float:
    """Combine auditable content signals with semantic objective relevance."""
    normalized_relevance = _clamp((relevance + 1.0) / 2.0)
    return _clamp(0.45 * heuristic + 0.55 * normalized_relevance)


def select_non_overlapping(
    candidates: list[dict],
    *,
    target_duration_sec: float,
    max_clips: int,
    min_clip_sec: float,
    max_clip_sec: float,
) -> list[dict]:
    """Greedy ranked selection with per-asset temporal overlap protection."""
    selected: list[dict] = []
    total = 0.0

    for candidate in sorted(
        candidates,
        key=lambda item: (-item["final_score"], item["asset_id"], item["start"]),
    ):
        duration = float(candidate["end"]) - float(candidate["start"])
        if duration < min_clip_sec:
            continue

        clipped = dict(candidate)
        if duration > max_clip_sec:
            clipped["end"] = clipped["start"] + max_clip_sec
            duration = max_clip_sec
            clipped.setdefault("reasons", []).append("trimmed to planner max clip duration")

        overlaps = any(
            existing["asset_id"] == clipped["asset_id"]
            and clipped["start"] < existing["end"]
            and existing["start"] < clipped["end"]
            for existing in selected
        )
        if overlaps:
            continue

        remaining = target_duration_sec - total
        if remaining < min_clip_sec:
            break
        if duration > remaining:
            clipped["end"] = clipped["start"] + remaining
            duration = remaining

        selected.append(clipped)
        total += duration
        if len(selected) >= max_clips or total >= target_duration_sec:
            break

    return selected
