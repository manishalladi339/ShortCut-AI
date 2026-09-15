"""Grounded visual-context and B-roll recommendation helpers."""
from __future__ import annotations

import math


def bounded_broll_source_range(
    *,
    observation_time_sec: float,
    asset_duration_sec: float,
    target_duration_ticks: int,
    ticks_per_second: float,
) -> tuple[int, int] | None:
    """Center a B-roll source range on visual evidence without exceeding media bounds."""
    source_duration_ticks = round(asset_duration_sec * ticks_per_second)
    if source_duration_ticks <= 0 or target_duration_ticks <= 0:
        return None
    duration = min(target_duration_ticks, source_duration_ticks)
    centered_start = round(observation_time_sec * ticks_per_second) - duration // 2
    start = min(max(0, centered_start), max(0, source_duration_ticks - duration))
    return start, duration


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def visual_text(observation: dict) -> str:
    """Produce embedding text without inventing information beyond vision output."""
    parts = [str(observation.get("description") or "").strip()]
    objects = [str(item).strip() for item in observation.get("visible_objects") or [] if str(item).strip()]
    if objects:
        parts.append("Visible objects: " + ", ".join(objects))
    on_screen = str(observation.get("text_on_screen") or "").strip()
    if on_screen:
        parts.append("On-screen text: " + on_screen)
    shot_type = str(observation.get("shot_type") or "").strip()
    if shot_type and shot_type != "unknown":
        parts.append("Shot type: " + shot_type)
    return ". ".join(part for part in parts if part)


def build_visual_candidates(record: dict) -> list[dict]:
    """Pair persisted visual observations with their embedding vectors."""
    observations = record.get("visual_observations") or []
    vectors = record.get("visual_vectors") or []
    candidates: list[dict] = []
    for index, observation in enumerate(observations):
        if index >= len(vectors):
            continue
        text = visual_text(observation)
        if not text:
            continue
        candidates.append(
            {
                "asset_id": record["asset_id"],
                "intelligence_id": record["id"],
                "observation_index": index,
                "time": float(observation.get("time") or 0.0),
                "description": str(observation.get("description") or ""),
                "shot_type": str(observation.get("shot_type") or "unknown"),
                "visible_objects": observation.get("visible_objects") or [],
                "text_on_screen": observation.get("text_on_screen"),
                "vector": vectors[index],
            }
        )
    return candidates


def rank_broll_candidates(
    candidates: list[dict], *, objective_vector: list[float], limit: int = 5,
    exclude_asset_id: str | None = None,
) -> list[dict]:
    ranked: list[dict] = []
    for candidate in candidates:
        if exclude_asset_id and candidate.get("asset_id") == exclude_asset_id:
            continue
        similarity = cosine_similarity(objective_vector, candidate.get("vector") or [])
        if similarity <= 0:
            continue
        ranked.append(
            {key: value for key, value in candidate.items() if key != "vector"}
            | {"relevance_score": round(similarity, 6)}
        )
    ranked.sort(key=lambda item: (-item["relevance_score"], item.get("asset_id", ""), item.get("time", 0.0)))
    return ranked[: max(0, limit)]


def recommend_broll_for_highlight(
    *, highlight: dict, visual_candidates: list[dict], highlight_vector: list[float], limit: int = 3
) -> list[dict]:
    """Recommend semantically related visual moments from other source assets."""
    return rank_broll_candidates(
        visual_candidates,
        objective_vector=highlight_vector,
        limit=limit,
        exclude_asset_id=highlight.get("asset_id"),
    )
