"""Whole-project synthesis over persisted asset-level media intelligence.

This layer deliberately does not invent identities, events, or chronology. It
connects semantic units and visual observations across uploaded assets while
retaining source provenance for every topic.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Iterable

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


_FILENAME_ROLE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("testimonial", ("testimonial", "customer story", "client story", "customer review")),
    ("interview", ("interview", "podcast", "q&a", "q and a", "conversation")),
    ("screen_recording", ("screen recording", "screenrecord", "screencast", "screen capture")),
    ("product_demo", ("product demo", "product-demo", "demo walkthrough", "demonstration")),
    ("broll", ("b-roll", "broll", "cutaway", "establishing shot", "beauty shot")),
]


def _normalized_filename(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[_\-.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _record_speakers(record: dict) -> list[str]:
    explicit = [
        str(value)
        for value in (record.get("speakers") or [])
        if str(value).strip()
    ]
    if explicit:
        return sorted(set(explicit))
    return sorted(
        {
            str(speaker)
            for unit in (record.get("semantic_units") or [])
            for speaker in (unit.get("speakers") or [])
            if str(speaker).strip()
        }
    )


def infer_asset_director_role(*, record: dict, asset: dict) -> dict:
    """Infer a conservative editor role from explicit/structural source evidence.

    Specific semantic labels such as interview/testimonial are used only when the
    filename explicitly supports them. Otherwise the role stays structural.
    """
    kind = str(asset.get("kind") or "")
    filename = _normalized_filename(asset.get("filename"))
    semantic_units = record.get("semantic_units") or []
    observations = record.get("visual_observations") or []
    speakers = _record_speakers(record)

    obs_count = len(observations)
    text_obs = sum(
        1
        for item in observations
        if str(item.get("text_on_screen") or "").strip()
    )
    people_obs = sum(
        1
        for item in observations
        if int(item.get("people_count") or 0) > 0
    )
    text_ratio = text_obs / obs_count if obs_count else 0.0
    people_ratio = people_obs / obs_count if obs_count else 0.0

    evidence: list[str] = []
    roles: list[str] = []
    primary_role: str
    confidence: float

    if kind == "image":
        primary_role = "photo"
        confidence = 1.0
        roles = ["photo", "visual_support"]
        evidence.append("media kind is image")
    else:
        explicit_role = None
        for role, phrases in _FILENAME_ROLE_PATTERNS:
            matched = next((phrase for phrase in phrases if phrase in filename), None)
            if matched:
                explicit_role = role
                evidence.append(f"filename contains '{matched}'")
                break

        if semantic_units:
            roles.append("spoken_source")
            evidence.append(f"{len(semantic_units)} grounded semantic units")
        if obs_count:
            roles.append("visual_support")
            evidence.append(f"{obs_count} visual observations")
        if len(speakers) >= 2:
            roles.append("multi_speaker")
            evidence.append(f"{len(speakers)} source-local speakers")

        if explicit_role is not None:
            primary_role = explicit_role
            confidence = 0.95
        elif (
            obs_count >= 2
            and text_ratio >= 0.55
            and people_ratio <= 0.35
        ):
            primary_role = "screen_recording"
            confidence = 0.82
            evidence.append(
                f"on-screen text in {text_obs}/{obs_count} observations with "
                f"people in {people_obs}/{obs_count}"
            )
        elif semantic_units and len(speakers) >= 2:
            primary_role = "conversation"
            confidence = 0.82
        elif semantic_units and people_ratio >= 0.5:
            primary_role = "spoken_on_camera"
            confidence = 0.78
        elif semantic_units:
            primary_role = "spoken_source"
            confidence = 0.72
        elif obs_count:
            primary_role = "broll"
            confidence = 0.74
            evidence.append("visual observations without grounded spoken units")
        else:
            primary_role = "visual_source"
            confidence = 0.55
            evidence.append("no richer analyzed role evidence available")

        if primary_role not in roles:
            roles.insert(0, primary_role)
        if primary_role in {
            "broll",
            "screen_recording",
            "product_demo",
        } and "visual_support" not in roles:
            roles.append("visual_support")

    # Preserve deterministic order without duplicates.
    roles = list(dict.fromkeys(roles))
    return {
        "primary_role": primary_role,
        "roles": roles,
        "confidence": round(confidence, 3),
        "evidence": evidence,
        "metrics": {
            "semantic_unit_count": len(semantic_units),
            "visual_observation_count": obs_count,
            "source_local_speaker_count": len(speakers),
            "text_observation_ratio": round(text_ratio, 3),
            "people_observation_ratio": round(people_ratio, 3),
        },
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


def _freshness(record: dict) -> str:
    value = record.get("updated_at") or record.get("created_at")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def latest_records_per_asset(records: list[dict]) -> list[dict]:
    """Keep one deterministic latest completed intelligence record per source asset."""
    latest: dict[str, dict] = {}
    for record in records:
        asset_id = str(record.get("asset_id") or "")
        if not asset_id:
            continue
        current = latest.get(asset_id)
        candidate_key = (_freshness(record), str(record.get("id") or ""))
        current_key = (
            (_freshness(current), str(current.get("id") or ""))
            if current is not None
            else None
        )
        if current_key is None or candidate_key >= current_key:
            latest[asset_id] = record
    return [latest[key] for key in sorted(latest)]


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
                "member_keys": [
                    str(row["asset_id"]) + ":" + str(row["unit_index"])
                    for row in cluster["rows"]
                ],
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
    now = datetime.now(timezone.utc)
    rows = _semantic_rows(records)
    topics = _cluster_topics(rows)
    speakers = _speaker_presences(records)
    visual_library = _visual_summary(records)

    asset_by_id = {asset["id"]: asset for asset in assets}
    asset_summaries = []
    for record in sorted(records, key=lambda item: item["asset_id"]):
        asset = asset_by_id.get(record["asset_id"]) or {}
        director_role = infer_asset_director_role(
            record=record,
            asset=asset,
        )
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
                "director_role": director_role["primary_role"],
                "director_roles": director_role["roles"],
                "director_role_confidence": director_role["confidence"],
                "director_role_evidence": director_role["evidence"],
                "director_role_metrics": director_role["metrics"],
            }
        )

    role_counts = Counter(
        str(item.get("director_role") or "unknown")
        for item in asset_summaries
    )

    summary = (
        f"Understood {len(records)} analyzed assets with {len(rows)} grounded "
        f"semantic units, {len(topics)} cross-asset topic clusters, "
        f"{len(speakers)} source-local speaker tracks, and "
        f"{visual_library['observation_count']} visual observations across "
        f"{len(role_counts)} grounded director-role types."
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
        "asset_role_counts": [
            {"role": role, "count": count}
            for role, count in sorted(role_counts.items())
        ],
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
    # Keep deterministic synthesis importable/testable without the Mongo driver.
    from db.mongo import get_db

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
