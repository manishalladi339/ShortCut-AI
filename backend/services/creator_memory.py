"""Derive creator preferences from real editing behavior.

Creator Memory is intentionally evidence-based. It learns only from:
- optional AI Director operations the creator applied or skipped;
- explicit plan feedback;
- constrained edits that were actually applied.

No preference is inferred from demographic/profile data.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from typing import Any


_OPTIONAL_COMPONENTS = {
    "add_broll_overlay": "broll",
    "add_caption": "captions",
    "add_music_bed": "music",
}


def _mode(values: list[Any]) -> Any | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    counts = Counter(clean)
    return sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0][0]


def _component_preferences(plans: list[dict]) -> dict[str, dict]:
    counts = {
        "broll": {"total": 0, "kept": 0, "skipped": 0},
        "captions": {"total": 0, "kept": 0, "skipped": 0},
        "music": {"total": 0, "kept": 0, "skipped": 0},
    }
    for plan in plans:
        if plan.get("status") != "applied":
            continue
        applied = set(plan.get("applied_operation_ids") or [])
        skipped = set(plan.get("skipped_operation_ids") or [])
        for operation in plan.get("operations") or []:
            component = _OPTIONAL_COMPONENTS.get(operation.get("operation"))
            operation_id = operation.get("id")
            if not component or not operation_id:
                continue
            # Ignore old plans that predate explicit operation-selection tracking.
            if operation_id not in applied and operation_id not in skipped:
                continue
            counts[component]["total"] += 1
            if operation_id in applied:
                counts[component]["kept"] += 1
            else:
                counts[component]["skipped"] += 1

    for values in counts.values():
        total = values["total"]
        values["keep_ratio"] = (
            round(values["kept"] / total, 4) if total else None
        )
    return counts


def _selected_constrained_operations(proposal: dict) -> list[dict]:
    if proposal.get("status") != "applied":
        return []
    selected = set(proposal.get("applied_operation_ids") or [])
    return [
        operation
        for operation in (proposal.get("operations") or [])
        if operation.get("id") in selected
    ]


def _constrained_signals(proposals: list[dict]) -> dict:
    caption_presets: list[str] = []
    caption_sizes: list[float] = []
    caption_positions: list[str] = []
    caption_animations: list[str] = []
    caption_removals = 0
    broll_removals = 0
    music_removals = 0
    music_volume_ratios: list[float] = []

    for proposal in proposals:
        for operation in _selected_constrained_operations(proposal):
            component = operation.get("component")
            op = operation.get("operation")
            payload = operation.get("payload") or {}

            if component == "captions":
                if op == "remove_caption":
                    caption_removals += 1
                elif op == "update_caption":
                    style = payload.get("style") or {}
                    if style.get("preset"):
                        caption_presets.append(str(style["preset"]))
                    if style.get("vertical_position"):
                        caption_positions.append(str(style["vertical_position"]))
                    if style.get("animation") is not None:
                        caption_animations.append(str(style["animation"]))
                    if style.get("size_scale") is not None:
                        try:
                            caption_sizes.append(float(style["size_scale"]))
                        except (TypeError, ValueError):
                            pass

            elif component == "broll" and op == "remove_clip":
                broll_removals += 1

            elif component == "music":
                if op == "remove_clip":
                    music_removals += 1
                elif op == "set_clip_properties":
                    reason = str(operation.get("reason") or "")
                    match = re.search(
                        r"from volume\s+([0-9]+(?:\.[0-9]+)?)\s+to\s+([0-9]+(?:\.[0-9]+)?)",
                        reason,
                        re.IGNORECASE,
                    )
                    if match:
                        before = float(match.group(1))
                        after = float(match.group(2))
                        if before > 0:
                            music_volume_ratios.append(after / before)

    return {
        "caption_presets": caption_presets,
        "caption_sizes": caption_sizes,
        "caption_positions": caption_positions,
        "caption_animations": caption_animations,
        "caption_removals": caption_removals,
        "broll_removals": broll_removals,
        "music_removals": music_removals,
        "music_volume_ratios": music_volume_ratios,
    }


def _confidence(evidence: int, *, full_at: int = 6) -> float:
    return round(min(1.0, max(0.0, evidence / full_at)), 3)


def derive_creator_memory(
    *,
    user_id: str,
    plans: list[dict],
    feedback: list[dict],
    constrained_proposals: list[dict],
    existing_created_at: datetime | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    optional = _component_preferences(plans)
    signals = _constrained_signals(constrained_proposals)

    feedback_counts = Counter(
        str(item.get("outcome"))
        for item in feedback
        if item.get("outcome") in {"accepted", "modified", "rejected"}
    )
    feedback_total = sum(feedback_counts.values())
    acceptance_rate = (
        round(feedback_counts["accepted"] / feedback_total, 4)
        if feedback_total
        else None
    )

    caption_style: dict[str, Any] = {}
    if signals["caption_presets"]:
        caption_style["preset"] = _mode(signals["caption_presets"])
    if signals["caption_positions"]:
        caption_style["vertical_position"] = _mode(signals["caption_positions"])
    if signals["caption_animations"]:
        caption_style["animation"] = _mode(signals["caption_animations"])
    if signals["caption_sizes"]:
        caption_style["size_scale"] = round(
            median(signals["caption_sizes"]), 3
        )

    broll_evidence = optional["broll"]["total"] + signals["broll_removals"]
    broll_keep = optional["broll"]["keep_ratio"]
    broll_density_multiplier = 1.0
    if broll_evidence >= 3:
        if signals["broll_removals"] >= 3 or (
            broll_keep is not None and broll_keep < 0.5
        ):
            broll_density_multiplier = 0.6
        elif signals["broll_removals"] >= 1 or (
            broll_keep is not None and broll_keep < 0.8
        ):
            broll_density_multiplier = 0.8
        elif (
            signals["broll_removals"] == 0
            and broll_keep is not None
            and broll_keep > 0.95
        ):
            broll_density_multiplier = 1.05

    music_multiplier = 1.0
    if signals["music_volume_ratios"]:
        music_multiplier = round(
            max(0.25, min(1.5, median(signals["music_volume_ratios"]))),
            3,
        )
    elif signals["music_removals"] >= 2:
        music_multiplier = 0.7

    caption_evidence = (
        len(signals["caption_presets"])
        + len(signals["caption_positions"])
        + len(signals["caption_animations"])
        + len(signals["caption_sizes"])
        + signals["caption_removals"]
        + optional["captions"]["total"]
    )
    music_evidence = (
        optional["music"]["total"]
        + len(signals["music_volume_ratios"])
        + signals["music_removals"]
    )

    preferences = {
        "caption_style": caption_style,
        "caption_removal_count": signals["caption_removals"],
        "broll_density_multiplier": broll_density_multiplier,
        "broll_removal_count": signals["broll_removals"],
        "music_volume_multiplier": music_multiplier,
        "music_removal_count": signals["music_removals"],
    }
    confidence = {
        "captions": _confidence(caption_evidence),
        "broll": _confidence(broll_evidence),
        "music": _confidence(music_evidence),
        "plan_feedback": _confidence(feedback_total, full_at=8),
    }

    evidence_count = (
        feedback_total
        + sum(values["total"] for values in optional.values())
        + sum(
            len(_selected_constrained_operations(proposal))
            for proposal in constrained_proposals
        )
    )

    learned: list[str] = []
    if caption_style and confidence["captions"] >= 0.34:
        details = ", ".join(
            f"{key.replace('_', ' ')}={value}"
            for key, value in sorted(caption_style.items())
        )
        learned.append(f"caption style ({details})")
    if broll_density_multiplier < 1 and confidence["broll"] >= 0.5:
        learned.append("fewer B-roll inserts")
    elif broll_density_multiplier > 1 and confidence["broll"] >= 0.5:
        learned.append("frequent B-roll inserts")
    if music_multiplier < 0.95 and confidence["music"] >= 0.34:
        learned.append("quieter music")
    elif music_multiplier > 1.05 and confidence["music"] >= 0.34:
        learned.append("louder music")

    if learned:
        summary = "Learned from your edits: " + "; ".join(learned) + "."
    elif evidence_count:
        summary = (
            f"Creator Memory has {evidence_count} editing signals; "
            "more decisions are needed before adapting strongly."
        )
    else:
        summary = "Creator Memory is ready and will learn from your editing decisions."

    return {
        "id": f"creator-memory:{user_id}",
        "user_id": user_id,
        "evidence_count": evidence_count,
        "plan_feedback_count": feedback_total,
        "constrained_edit_count": sum(
            1 for proposal in constrained_proposals if proposal.get("status") == "applied"
        ),
        "plan_acceptance_rate": acceptance_rate,
        "optional_operation_preferences": optional,
        "preferences": preferences,
        "confidence": confidence,
        "summary": summary,
        "created_at": existing_created_at or now,
        "updated_at": now,
    }


async def refresh_creator_memory(*, user_id: str) -> dict:
    from db.mongo import get_db

    db = get_db()
    plans = await db.ai_edit_plans.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("updated_at", -1).limit(200).to_list(200)
    feedback = await db.ai_plan_feedback.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("updated_at", -1).limit(200).to_list(200)
    proposals = await db.ai_constrained_edit_proposals.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("updated_at", -1).limit(200).to_list(200)
    existing = await db.creator_memories.find_one(
        {"user_id": user_id},
        {"_id": 0, "created_at": 1},
    )
    doc = derive_creator_memory(
        user_id=user_id,
        plans=plans,
        feedback=feedback,
        constrained_proposals=proposals,
        existing_created_at=(existing or {}).get("created_at"),
    )
    await db.creator_memories.update_one(
        {"user_id": user_id},
        {"$set": doc},
        upsert=True,
    )
    return doc


async def get_creator_memory(*, user_id: str) -> dict:
    from db.mongo import get_db

    doc = await get_db().creator_memories.find_one(
        {"user_id": user_id},
        {"_id": 0},
    )
    if doc:
        return doc
    return await refresh_creator_memory(user_id=user_id)


def creator_caption_style(memory: dict) -> dict[str, Any]:
    confidence = float((memory.get("confidence") or {}).get("captions") or 0.0)
    if confidence < 0.34:
        return {}
    style = (memory.get("preferences") or {}).get("caption_style") or {}
    return {
        key: value
        for key, value in style.items()
        if key in {"preset", "vertical_position", "size_scale", "animation"}
    }


def creator_allows_broll(memory: dict, candidate_index: int) -> bool:
    confidence = float((memory.get("confidence") or {}).get("broll") or 0.0)
    if confidence < 0.5:
        return True
    multiplier = float(
        (memory.get("preferences") or {}).get("broll_density_multiplier") or 1.0
    )
    if multiplier <= 0.65:
        return candidate_index % 2 == 0
    if multiplier <= 0.85:
        return candidate_index % 3 != 2
    return True
