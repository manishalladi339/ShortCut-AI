"""Grounded B-roll recommendation helpers.

The planner may recommend source moments, but does not mutate the timeline until
the deterministic editing/rendering path supports that operation end to end.
"""
from __future__ import annotations

import math


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_broll_candidates(
    candidates: list[dict], *, objective_vector: list[float], limit: int = 5
) -> list[dict]:
    ranked: list[dict] = []
    for candidate in candidates:
        similarity = cosine_similarity(objective_vector, candidate.get("vector") or [])
        if similarity <= 0:
            continue
        ranked.append(
            {
                key: value
                for key, value in candidate.items()
                if key != "vector"
            }
            | {"relevance_score": round(similarity, 6)}
        )
    ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
    return ranked[: max(0, limit)]
