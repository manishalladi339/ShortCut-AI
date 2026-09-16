"""Semantic B-roll replacement for constrained Create With Me edits."""
from __future__ import annotations

import re

from core.config import settings
from db.mongo import get_db
from services.broll_planning import (
    bounded_broll_source_range,
    build_visual_candidates,
    rank_broll_candidates,
    visual_text,
)
from services.constrained_editing import (
    _active_sequence,
    _contained,
    _derive_scope,
    _operation,
    _ticks_per_second,
)
from services.embeddings import EmbeddingError, get_embedding_provider
from services.project_intelligence import latest_records_per_asset


def is_broll_replacement_instruction(instruction: str) -> bool:
    lowered = instruction.lower()
    mentions_broll = any(
        term in lowered
        for term in ("b-roll", "broll", "b roll", "overlay", "visual")
    )
    asks_replace = bool(
        re.search(
            r"\b(?:replace|swap|change)\s+(?:this\s+|the\s+|that\s+|current\s+)?"
            r"(?:b-roll|broll|b\s+roll|overlay|visual)",
            lowered,
        )
    )
    return mentions_broll and asks_replace


def _explicit_visual_query(instruction: str) -> str | None:
    match = re.search(
        r"\b(?:with|using|showing)\s+(.+)$",
        instruction,
        re.IGNORECASE,
    )
    if not match:
        return None
    query = match.group(1).strip(" .,!?:;")
    return query[:500] if len(query) >= 3 else None


async def _embed_query(text: str) -> list[float]:
    try:
        return (await get_embedding_provider().embed([text]))[0]
    except EmbeddingError as exc:
        raise ValueError(
            "Semantic B-roll replacement could not embed the requested visual context."
        ) from exc


def _best_primary_clip(sequence: dict, target: dict) -> dict | None:
    target_start = int(target.get("timeline_start") or 0)
    target_end = target_start + int(target.get("duration") or 0)
    candidates: list[tuple[int, dict]] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "video":
            continue
        for clip in track.get("clips") or []:
            start = int(clip.get("timeline_start") or 0)
            end = start + int(clip.get("duration") or 0)
            overlap = max(0, min(target_end, end) - max(target_start, start))
            if overlap > 0:
                candidates.append((overlap, clip))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            -item[0],
            int(item[1].get("timeline_start") or 0),
            str(item[1].get("id") or ""),
        )
    )
    return candidates[0][1]


def _semantic_vector_for_primary(primary: dict | None, records_by_id: dict[str, dict]) -> list[float]:
    if not primary:
        return []
    metadata = primary.get("metadata") or {}
    intelligence_id = str(metadata.get("source_intelligence_id") or "")
    unit_index = metadata.get("source_unit_index")
    if not intelligence_id or unit_index is None:
        return []
    record = records_by_id.get(intelligence_id) or {}
    vectors = record.get("semantic_vectors") or []
    try:
        index = int(unit_index)
    except (TypeError, ValueError):
        return []
    if index < 0 or index >= len(vectors):
        return []
    return list(vectors[index] or [])


def _old_visual_query(target: dict, records_by_id: dict[str, dict]) -> str | None:
    metadata = target.get("metadata") or {}
    intelligence_id = str(metadata.get("source_intelligence_id") or "")
    observation_index = metadata.get("source_observation_index")
    if not intelligence_id or observation_index is None:
        return None
    record = records_by_id.get(intelligence_id) or {}
    observations = record.get("visual_observations") or []
    try:
        index = int(observation_index)
    except (TypeError, ValueError):
        return None
    if index < 0 or index >= len(observations):
        return None
    text = visual_text(observations[index])
    return text[:500] if text else None


async def build_semantic_broll_replacements(
    *,
    project_id: str,
    user_id: str,
    state: dict,
    instruction: str,
    scope_start_sec: float | None,
    scope_end_sec: float | None,
) -> tuple[list[str], list[dict]]:
    if not is_broll_replacement_instruction(instruction):
        return [], []

    sequence = _active_sequence(state)
    tps = _ticks_per_second(sequence)
    start_sec, end_sec = _derive_scope(
        instruction=instruction,
        sequence=sequence,
        explicit_start_sec=scope_start_sec,
        explicit_end_sec=scope_end_sec,
    )
    scope_start = round(start_sec * tps)
    scope_end = max(scope_start + 1, round(end_sec * tps))

    targets: list[tuple[dict, dict]] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "overlay" or track.get("locked"):
            continue
        for clip in track.get("clips") or []:
            metadata = clip.get("metadata") or {}
            if not (metadata.get("broll") or metadata.get("ai_plan_id")):
                continue
            if not _contained(
                int(clip.get("timeline_start") or 0),
                int(clip.get("duration") or 0),
                scope_start,
                scope_end,
            ):
                continue
            targets.append((track, clip))

    if not targets:
        return ["replace_broll"], []

    db = get_db()
    records = await db.media_intelligence.find(
        {
            "project_id": project_id,
            "user_id": user_id,
            "status": "completed",
            "embedding_model": settings.EMBEDDING_MODEL,
        },
        {
            "_id": 0,
            "id": 1,
            "asset_id": 1,
            "semantic_units": 1,
            "semantic_vectors": 1,
            "visual_observations": 1,
            "visual_vectors": 1,
            "created_at": 1,
            "updated_at": 1,
        },
    ).to_list(500)
    records = latest_records_per_asset(records)
    records_by_id = {record["id"]: record for record in records}

    visual_candidates = [
        candidate
        for record in records
        for candidate in build_visual_candidates(record)
    ]
    if not visual_candidates:
        raise ValueError(
            "Project media has no embedded visual observations available for B-roll replacement."
        )

    asset_ids = sorted({candidate["asset_id"] for candidate in visual_candidates})
    asset_docs = await db.assets.find(
        {
            "id": {"$in": asset_ids},
            "user_id": user_id,
            "processing_status": "ready",
            "kind": "video",
        },
        {"_id": 0, "id": 1, "duration_sec": 1, "kind": 1},
    ).to_list(len(asset_ids))
    assets = {item["id"]: item for item in asset_docs}
    visual_candidates = [
        candidate
        for candidate in visual_candidates
        if candidate["asset_id"] in assets
    ]
    if not visual_candidates:
        raise ValueError("No ready video assets are available as replacement B-roll.")

    explicit_query = _explicit_visual_query(instruction)
    explicit_vector: list[float] = []
    if explicit_query:
        explicit_vector = await _embed_query(explicit_query)

    operations: list[dict] = []
    used_sources: set[tuple[str, int]] = set()

    for track, target in targets:
        duration = int(target.get("duration") or 0)
        if duration <= 0:
            continue
        current_asset_id = str(target.get("asset_id") or "")

        primary = _best_primary_clip(sequence, target)
        context_vector = (
            explicit_vector
            or _semantic_vector_for_primary(primary, records_by_id)
        )
        replacement_query = explicit_query

        if not context_vector:
            old_query = _old_visual_query(target, records_by_id)
            if old_query:
                replacement_query = replacement_query or old_query
                context_vector = await _embed_query(old_query)

        if not context_vector:
            replacement_query = replacement_query or instruction.strip()
            context_vector = await _embed_query(replacement_query)

        ranked = rank_broll_candidates(
            visual_candidates,
            objective_vector=context_vector,
            limit=20,
            exclude_asset_id=current_asset_id,
        )

        chosen = None
        chosen_range = None
        for candidate in ranked:
            key = (
                str(candidate["asset_id"]),
                int(candidate["observation_index"]),
            )
            if key in used_sources:
                continue
            asset = assets.get(candidate["asset_id"]) or {}
            source_range = bounded_broll_source_range(
                observation_time_sec=float(candidate["time"]),
                asset_duration_sec=float(asset.get("duration_sec") or 0.0),
                target_duration_ticks=duration,
                ticks_per_second=tps,
            )
            if not source_range:
                continue
            source_start, source_duration = source_range
            if source_duration != duration:
                continue
            chosen = candidate
            chosen_range = (source_start, source_duration)
            used_sources.add(key)
            break

        if chosen is None or chosen_range is None:
            raise ValueError(
                "ShortCut found no alternative grounded visual long enough to preserve "
                "the selected B-roll slot."
            )

        source_start, source_duration = chosen_range
        operations.append(
            _operation(
                operation="replace_broll",
                component="broll",
                payload={
                    "sequence_id": sequence["id"],
                    "track_id": track["id"],
                    "clip_id": target["id"],
                    "asset_id": chosen["asset_id"],
                    "source_start": source_start,
                    "source_duration": source_duration,
                    "source_intelligence_id": chosen["intelligence_id"],
                    "source_observation_index": chosen["observation_index"],
                    "relevance_score": chosen["relevance_score"],
                    "replacement_query": replacement_query or "underlying story context",
                },
                reason=(
                    f"Replace the existing B-roll in-place with grounded visual evidence "
                    f"from {chosen['asset_id']} at {float(chosen['time']):.2f}s "
                    f"(semantic similarity {float(chosen['relevance_score']):.3f}) "
                    "without changing its timeline slot."
                ),
            )
        )

    return ["replace_broll"], operations
