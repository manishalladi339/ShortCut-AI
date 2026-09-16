"""Deterministic multi-asset selection and Director brief helpers.

This layer adds source diversity and topic coverage to the existing grounded
highlight/narrative pipeline. It never invents source roles or identities.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def candidate_key(item: dict) -> str:
    return f"{item['asset_id']}:{item['unit_index']}"


def _prepare_candidates(
    candidates: list[dict],
    *,
    min_clip_sec: float,
    max_clip_sec: float,
) -> list[dict]:
    prepared: list[dict] = []
    for candidate in candidates:
        start = float(candidate["start"])
        end = float(candidate["end"])
        duration = end - start
        if duration < min_clip_sec:
            continue
        item = dict(candidate)
        item["reasons"] = list(candidate.get("reasons") or [])
        if duration > max_clip_sec:
            item["end"] = start + max_clip_sec
            item["reasons"].append("trimmed to multi-asset max clip duration")
        prepared.append(item)
    prepared.sort(
        key=lambda item: (-float(item["final_score"]), item["asset_id"], item["start"])
    )
    return prepared


def _topic_lookup(project_intelligence: dict) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    for topic in project_intelligence.get("topic_clusters") or []:
        topic_id = str(topic.get("id") or "")
        if not topic_id:
            continue
        member_keys = topic.get("member_keys") or [
            f"{row.get('asset_id')}:{row.get('unit_index')}"
            for row in (topic.get("evidence") or [])
        ]
        for key in member_keys:
            lookup.setdefault(str(key), set()).add(topic_id)
    return lookup


def _overlaps(selected: list[dict], candidate: dict) -> bool:
    return any(
        item["asset_id"] == candidate["asset_id"]
        and float(candidate["start"]) < float(item["end"])
        and float(item["start"]) < float(candidate["end"])
        for item in selected
    )


def select_multi_asset_candidates(
    candidates: list[dict],
    *,
    target_duration_sec: float,
    max_clips: int,
    min_clip_sec: float,
    max_clip_sec: float,
    min_source_assets: int,
    max_source_share: float,
    project_intelligence: dict,
) -> list[dict]:
    """Select a grounded story cut with explicit source/topic diversity.

    The requested source-share cap is relaxed only when mathematically necessary
    because too few spoken-source assets are available.
    """
    prepared = _prepare_candidates(
        candidates,
        min_clip_sec=min_clip_sec,
        max_clip_sec=max_clip_sec,
    )
    if not prepared:
        return []

    available_assets = sorted({str(item["asset_id"]) for item in prepared})
    effective_share = max(
        float(max_source_share),
        1.0 / max(1, len(available_assets)),
    )
    asset_cap = max(float(max_clip_sec), float(target_duration_sec) * effective_share)
    required_assets = min(max(1, int(min_source_assets)), len(available_assets))
    topic_lookup = _topic_lookup(project_intelligence)

    selected: list[dict] = []
    selected_keys: set[str] = set()
    selected_topics: set[str] = set()
    asset_duration: dict[str, float] = defaultdict(float)
    total = 0.0

    def add(item: dict, reason: str) -> bool:
        nonlocal total
        if len(selected) >= max_clips:
            return False
        key = candidate_key(item)
        if key in selected_keys or _overlaps(selected, item):
            return False

        duration = float(item["end"]) - float(item["start"])
        remaining = float(target_duration_sec) - total
        asset_remaining = asset_cap - asset_duration[str(item["asset_id"])]
        allowed = min(duration, remaining, asset_remaining)
        if allowed < min_clip_sec:
            return False

        chosen = dict(item)
        chosen["reasons"] = list(item.get("reasons") or [])
        if allowed + 1e-9 < duration:
            chosen["end"] = float(chosen["start"]) + allowed
            chosen["reasons"].append("trimmed to Director diversity/duration budget")
        chosen["reasons"].append(reason)
        chosen["multi_asset_topics"] = sorted(topic_lookup.get(key, set()))

        selected.append(chosen)
        selected_keys.add(key)
        chosen_duration = float(chosen["end"]) - float(chosen["start"])
        total += chosen_duration
        asset_duration[str(chosen["asset_id"])] += chosen_duration
        selected_topics.update(topic_lookup.get(key, set()))
        return True

    # Seed the story with the strongest viable moment from distinct source assets.
    strongest_by_asset: dict[str, dict] = {}
    for item in prepared:
        strongest_by_asset.setdefault(str(item["asset_id"]), item)
    seeds = sorted(
        strongest_by_asset.values(),
        key=lambda item: (-float(item["final_score"]), item["asset_id"], item["start"]),
    )
    for item in seeds[:required_assets]:
        if total >= target_duration_sec or len(selected) >= max_clips:
            break
        add(item, "selected to establish multi-source story diversity")

    # Fill the remaining budget using relevance + uncovered topic/source bonuses.
    while total + min_clip_sec <= target_duration_sec and len(selected) < max_clips:
        ranked: list[tuple[float, dict]] = []
        used_assets = {str(item["asset_id"]) for item in selected}
        for item in prepared:
            key = candidate_key(item)
            if key in selected_keys or _overlaps(selected, item):
                continue
            asset_id = str(item["asset_id"])
            duration = float(item["end"]) - float(item["start"])
            if asset_duration[asset_id] + min(duration, max_clip_sec) > asset_cap + 1e-9:
                # It may still fit after trimming, so only reject if less than min remains.
                if asset_cap - asset_duration[asset_id] < min_clip_sec:
                    continue

            topics = topic_lookup.get(key, set())
            new_topic_count = len(topics - selected_topics)
            new_asset_bonus = 0.10 if asset_id not in used_assets else 0.0
            topic_bonus = min(0.12, 0.04 * new_topic_count)
            share_ratio = asset_duration[asset_id] / max(asset_cap, 1e-9)
            repetition_penalty = 0.08 * share_ratio
            director_score = (
                float(item["final_score"])
                + new_asset_bonus
                + topic_bonus
                - repetition_penalty
            )
            ranked.append((director_score, item))

        if not ranked:
            break
        ranked.sort(
            key=lambda pair: (
                -pair[0],
                -float(pair[1]["final_score"]),
                pair[1]["asset_id"],
                pair[1]["start"],
            )
        )
        best_score, best = ranked[0]
        before = len(selected)
        add(
            best,
            "Director selection balanced semantic relevance, source diversity "
            f"and topic coverage (score {best_score:.3f})",
        )
        if len(selected) == before:
            break

    return selected


def build_director_brief(
    *,
    objective: str,
    target_duration_sec: float,
    selected: list[dict],
    project_intelligence: dict,
    assets: list[dict],
    min_source_assets: int,
    max_source_share: float,
) -> dict[str, Any]:
    asset_by_id = {str(item["id"]): item for item in assets}
    selected_asset_ids = sorted({str(item["asset_id"]) for item in selected})
    selected_topics = sorted(
        {
            str(topic)
            for item in selected
            for topic in (item.get("multi_asset_topics") or [])
            if str(topic)
        }
    )

    duration_by_asset: dict[str, float] = defaultdict(float)
    clips_by_asset: dict[str, int] = defaultdict(int)
    for item in selected:
        asset_id = str(item["asset_id"])
        duration_by_asset[asset_id] += max(
            0.0,
            float(item["end"]) - float(item["start"]),
        )
        clips_by_asset[asset_id] += 1

    summary_by_asset = {
        str(item.get("asset_id")): item
        for item in (project_intelligence.get("asset_summaries") or [])
    }
    speaker_counts: dict[str, int] = defaultdict(int)
    for row in project_intelligence.get("speaker_presences") or []:
        speaker_counts[str(row.get("asset_id"))] += 1

    source_mix = []
    for asset_id in selected_asset_ids:
        asset = asset_by_id.get(asset_id) or {}
        intel = summary_by_asset.get(asset_id) or {}
        source_mix.append(
            {
                "asset_id": asset_id,
                "filename": asset.get("filename"),
                "kind": asset.get("kind"),
                "selected_clip_count": clips_by_asset[asset_id],
                "selected_duration_sec": round(duration_by_asset[asset_id], 3),
                "semantic_unit_count": int(intel.get("semantic_unit_count") or 0),
                "visual_observation_count": int(
                    intel.get("visual_observation_count") or 0
                ),
                "source_local_speaker_count": speaker_counts[asset_id],
                "role": "primary_spoken_source",
            }
        )

    visual_support_asset_ids = sorted(
        {
            str(item.get("asset_id"))
            for item in (project_intelligence.get("asset_summaries") or [])
            if int(item.get("visual_observation_count") or 0) > 0
        }
    )

    selected_duration = sum(duration_by_asset.values())
    summary = (
        f"Director Mode selected {len(selected)} grounded story moments from "
        f"{len(selected_asset_ids)} spoken-source assets, covering "
        f"{len(selected_topics)} project topics across {selected_duration:.1f}s "
        "before dead-air/pacing adjustments."
    )

    return {
        "mode": "multi_asset",
        "objective": objective,
        "target_duration_sec": float(target_duration_sec),
        "requested_min_source_assets": int(min_source_assets),
        "max_source_share": float(max_source_share),
        "available_analyzed_asset_count": int(
            project_intelligence.get("asset_count") or 0
        ),
        "selected_spoken_asset_count": len(selected_asset_ids),
        "selected_asset_ids": selected_asset_ids,
        "covered_topic_ids": selected_topics,
        "topic_coverage_count": len(selected_topics),
        "source_mix": source_mix,
        "visual_support_asset_ids": visual_support_asset_ids,
        "summary": summary,
    }
