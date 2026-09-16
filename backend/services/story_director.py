"""Grounded story-beat planning over an ordered set of source candidates."""
from __future__ import annotations


def candidate_key(item: dict) -> str:
    return f"{item['asset_id']}:{item['unit_index']}"


def _topic_lookup(project_intelligence: dict) -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for topic in project_intelligence.get("topic_clusters") or []:
        for evidence in topic.get("evidence") or []:
            key = f"{evidence['asset_id']}:{evidence['unit_index']}"
            lookup.setdefault(key, []).append(topic)
    return lookup


def _roles_for_count(count: int) -> list[str]:
    if count <= 0:
        return []
    if count == 1:
        return ["hook"]
    if count == 2:
        return ["hook", "payoff"]
    if count == 3:
        return ["hook", "development", "payoff"]
    if count <= 5:
        return ["hook", "context", "development", "payoff"]
    return ["hook", "context", "development", "proof", "payoff"]


def _partition(items: list[dict], bucket_count: int) -> list[list[dict]]:
    if bucket_count <= 0:
        return []
    buckets: list[list[dict]] = [[] for _ in range(bucket_count)]
    for index, item in enumerate(items):
        target = min(bucket_count - 1, (index * bucket_count) // len(items))
        buckets[target].append(item)
    return [bucket for bucket in buckets if bucket]


def _purpose(role: str) -> str:
    return {
        "hook": "Create immediate curiosity using the strongest grounded source moment.",
        "context": "Give the audience enough grounded context to understand what is at stake.",
        "development": "Advance the central idea or conflict with new source evidence.",
        "proof": "Support the story with corroborating evidence, examples, or alternate voices.",
        "payoff": "Resolve the promise of the opening with a grounded takeaway or consequence.",
    }.get(role, "Advance the story using grounded source evidence.")


def build_story_beats(
    *,
    ordered_candidates: list[dict],
    project_intelligence: dict,
    target_duration_sec: float,
) -> list[dict]:
    if not ordered_candidates:
        return []

    roles = _roles_for_count(len(ordered_candidates))
    groups = _partition(ordered_candidates, len(roles))
    roles = roles[: len(groups)]
    topic_lookup = _topic_lookup(project_intelligence)

    raw_durations = [
        max(
            0.1,
            sum(
                max(
                    0.0,
                    float(item.get("planned_duration_sec") or 0.0)
                    or (float(item["end"]) - float(item["start"])),
                )
                for item in group
            ),
        )
        for group in groups
    ]
    total_raw = sum(raw_durations)
    allocated = [
        round(float(target_duration_sec) * duration / total_raw, 3)
        for duration in raw_durations
    ]
    if allocated:
        allocated[-1] = round(
            max(0.1, float(target_duration_sec) - sum(allocated[:-1])),
            3,
        )

    beats: list[dict] = []
    for index, (role, group) in enumerate(zip(roles, groups), start=1):
        evidence_keys = [candidate_key(item) for item in group]
        topics = []
        seen_topic_ids = set()
        for key in evidence_keys:
            for topic in topic_lookup.get(key, []):
                if topic["id"] not in seen_topic_ids:
                    seen_topic_ids.add(topic["id"])
                    topics.append(topic)

        topic_label = topics[0]["label"] if topics else None
        title = role.replace("_", " ").title()
        if topic_label:
            title = f"{title} · {topic_label}"

        beats.append(
            {
                "id": f"beat-{index:02d}",
                "role": role,
                "title": title,
                "purpose": _purpose(role),
                "target_duration_sec": allocated[index - 1],
                "evidence_keys": evidence_keys,
                "topic_ids": [topic["id"] for topic in topics],
            }
        )
    return beats
