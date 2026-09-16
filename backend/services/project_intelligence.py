"""Whole-project synthesis over persisted asset-level media intelligence.

This layer deliberately does not invent identities, events, or chronology. It
connects semantic units and visual observations across uploaded assets while
retaining source provenance for every topic.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from core.security import utc_now
from db.mongo import get_db
from services.semantic_search import cosine_similarity

_STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been", "before",
    "being", "but", "can", "could", "did", "does", "doing", "for", "from", "had",
    "has", "have", "here", "how", "into", "its", "just", "more", "most", "not",
    "now", "our", "out", "over", "really", "said", "she", "should", "some", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "too", "very", "was", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your",
}


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z0-9']+", text.lower())
        if len(token) >= 3 and token not in _STOPWORDS and not token.isdigit()
    ]


def _topic_label(rows: list[dict]) -> str:
    counts = Counter(
        token
        for row in rows
        for token in _tokens(str(row.get("text") or ""))
    )
    common = [token for token, _ in counts.most_common(3)]
    if common:
        return " · ".join(token.title() for token in common)
    fallback = str(rows[0].get("text") or "Project topic").strip()
    return (fallback[:57].rstrip() + "...") if len(fallback) > 60 else fallback


def _mean_vector(vectors: Iterable[list[float]]) -> list[float]:
    vectors = [vector for vector in vectors if vector]
    if not vectors:
        return []
    width = len(vectors[0])
    vectors = [vector for vector in vectors if len(vector) == width]
    if not vectors:
        return []
    return [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(width)
    ]


def _semantic_rows(records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        units = record.get("semantic_units") or []
        vectors = record.get("semantic_vectors") or []
        for index, unit in enumerate(units):
            if index >= len(vectors) or not vectors[index]:
                continue
            rows.append(
                {
                    "asset_id": record["asset_id"],
                    "intelligence_id": record["id"],
                    "unit_index": index,
                    "start": float(unit.get("start") or 0.0),
                    "end": float(unit.get("end") or unit.get("start") or 0.0),
                    "text": str(unit.get("text") or "").strip(),
                    "speakers": [
                        str(value)
                        for value in (unit.get("speakers") or [])
                        if str(value).strip()
                    ],
                    "vector": vectors[index],
                }
            )
    rows.sort(key=lambda item: (item["asset_id"], item["unit_index"]))
    return rows


def _cluster_topics(
    rows: list[dict],
    *,
    similarity_threshold: float = 0.76,
    max_topics: int = 8,
) -> list[dict]:
    clusters: list[dict] = []
    for row in rows:
        best_index = None
        best_score = -1.0
        for index, cluster in enumerate(clusters):
            score = cosine_similarity(row["vector"], cluster["centroid"])
            if score > best_score:
                best_index = index
                best_score = score

        if best_index is None or best_score < similarity_threshold:
            clusters.append({"rows": [row], "centroid": list(row["vector"])})
            continue

        cluster = clusters[best_index]
        cluster["rows"].append(row)
        cluster["centroid"] = _mean_vector(
            [candidate["vector"] for candidate in cluster["rows"]]
        )

    clusters.sort(
        key=lambda cluster: (
            -len(cluster["rows"]),
            cluster["rows"][0]["asset_id"],
            cluster["rows"][0]["unit_index"],
        )
    )

    topics: list[dict] = []
    for topic_index, cluster in enumerate(clusters[:max_topics], start=1):
        centroid = cluster["centroid"]
        ranked = sorted(
            cluster["rows"],
            key=lambda row: (
                -cosine_similarity(row["vector"], centroid),
                row["asset_id"],
                row["unit_index"],
            ),
        )
        evidence = []
        for row in ranked[:4]:
            evidence.append(
                {
                    "asset_id": row["asset_id"],
                    "intelligence_id": row["intelligence_id"],
                    "unit_index": row["unit_index"],
                    "start": row["start"],
                    "end": row["end"],
                    "text": row["text"],
                    "speakers": row["speakers"],
                    "relevance_to_topic": round(
                        cosine_similarity(row["vector"], centroid), 6
                    ),
                }
            )
        topics.append(
            {
                "id": f"topic-{topic_index:02d}",
                "label": _topic_label(cluster["rows"]),
                "unit_count": len(cluster["rows"]),
                "asset_ids": sorted({row["asset_id"] for row in cluster["rows"]}),
                "evidence": evidence,
            }
        )
    return topics


def _speaker_presences(records: list[dict]) -> list[dict]:
    stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"unit_count": 0, "spoken_duration_sec": 0.0}
    )
    for record in records:
        for unit in record.get("semantic_units") or []:
            speakers = [
                str(value)
                for value in (unit.get("speakers") or [])
                if str(value).strip()
            ]
            if not speakers:
                continue
            duration = max(
                0.0,
                float(unit.get("end") or 0.0) - float(unit.get("start") or 0.0),
            )
            share = duration / len(speakers)
            for speaker in speakers:
                key = (record["asset_id"], speaker)
                stats[key]["unit_count"] += 1
                stats[key]["spoken_duration_sec"] += share

    return [
        {
            "asset_id": asset_id,
            "speaker": speaker,
            "unit_count": values["unit_count"],
            "spoken_duration_sec": round(values["spoken_duration_sec"], 3),
        }
        for (asset_id, speaker), values in sorted(stats.items())
    ]


def _visual_summary(records: list[dict]) -> dict:
    objects: Counter[str] = Counter()
    shots: Counter[str] = Counter()
    observation_count = 0
    people_count = 0
    text_count = 0

    for record in records:
        for observation in record.get("visual_observations") or []:
            observation_count += 1
            if int(observation.get("people_count") or 0) > 0:
                people_count += 1
            if str(observation.get("text_on_screen") or "").strip():
                text_count += 1
            shot = str(observation.get("shot_type") or "unknown").strip().lower()
            if shot:
                shots[shot] += 1
            for value in observation.get("visible_objects") or []:
                name = str(value).strip().lower()
                if name:
                    objects[name] += 1

    return {
        "observation_count": observation_count,
        "observations_with_people": people_count,
        "observations_with_text": text_count,
        "common_objects": [
            {"name": name, "count": count}
            for name, count in objects.most_common(12)
        ],
        "shot_types": [
            {"name": name, "count": count}
            for name, count in shots.most_common(12)
        ],
    }


def synthesize_project_intelligence(
    *,
    project_id: str,
    user_id: str,
    records: list[dict],
    assets: list[dict],
) -> dict:
    now = utc_now()
    rows = _semantic_rows(records)
    topics = _cluster_topics(rows)
    speakers = _speaker_presences(records)
    visual_library = _visual_summary(records)

    asset_by_id = {asset["id"]: asset for asset in assets}
    asset_summaries = []
    for record in sorted(records, key=lambda item: item["asset_id"]):
        asset = asset_by_id.get(record["asset_id"]) or {}
        asset_summaries.append(
            {
                "asset_id": record["asset_id"],
                "filename": asset.get("filename"),
                "kind": asset.get("kind"),
                "duration_sec": asset.get("duration_sec"),
                "semantic_unit_count": len(record.get("semantic_units") or []),
                "visual_observation_count": len(
                    record.get("visual_observations") or []
                ),
                "speakers": list(record.get("speakers") or []),
            }
        )

    summary = (
        f"Understood {len(records)} analyzed assets with {len(rows)} grounded "
        f"semantic units, {len(topics)} cross-asset topic clusters, "
        f"{len(speakers)} source-local speaker tracks, and "
        f"{visual_library['observation_count']} visual observations."
    )

    return {
        "id": f"project-intelligence:{project_id}",
        "project_id": project_id,
        "user_id": user_id,
        "status": "completed",
        "asset_count": len(records),
        "semantic_unit_count": len(rows),
        "visual_observation_count": visual_library["observation_count"],
        "source_intelligence_ids": sorted(record["id"] for record in records),
        "asset_summaries": asset_summaries,
        "speaker_presences": speakers,
        "topic_clusters": topics,
        "visual_library": visual_library,
        "summary": summary,
        "created_at": now,
        "updated_at": now,
    }


async def build_and_store_project_intelligence(
    *,
    project_id: str,
    user_id: str,
    records: list[dict],
    assets: list[dict],
) -> dict:
    db = get_db()
    doc = synthesize_project_intelligence(
        project_id=project_id,
        user_id=user_id,
        records=records,
        assets=assets,
    )
    existing = await db.project_intelligence.find_one(
        {"project_id": project_id, "user_id": user_id},
        {"_id": 0, "created_at": 1},
    )
    if existing and existing.get("created_at"):
        doc["created_at"] = existing["created_at"]
    await db.project_intelligence.update_one(
        {"project_id": project_id, "user_id": user_id},
        {"$set": doc},
        upsert=True,
    )
    return doc
