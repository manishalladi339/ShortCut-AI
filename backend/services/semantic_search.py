"""Deterministic cosine retrieval over stored semantic-unit embeddings."""
from __future__ import annotations

import math


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_units(
    query_vector: list[float],
    candidates: list[dict],
    *,
    limit: int,
    min_score: float,
) -> list[dict]:
    scored: list[dict] = []
    for candidate in candidates:
        vector = candidate.get("embedding") or []
        score = cosine_similarity(query_vector, vector)
        if score < min_score:
            continue
        scored.append(
            {
                "score": score,
                "asset_id": candidate["asset_id"],
                "intelligence_id": candidate["intelligence_id"],
                "unit_index": candidate["unit_index"],
                "start": candidate["start"],
                "end": candidate["end"],
                "text": candidate["text"],
            }
        )
    scored.sort(key=lambda item: (-item["score"], item["asset_id"], item["unit_index"]))
    return scored[:limit]
