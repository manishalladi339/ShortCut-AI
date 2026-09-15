"""Lightweight measurable planner-quality checks."""
from __future__ import annotations


def _candidate_duration(item: dict) -> float:
    planned = item.get("planned_duration_sec")
    if planned is not None:
        return max(0.0, float(planned))
    return max(
        0.0,
        float(item["end"]) - float(item["start"]),
    )


def _max_speaker_run(candidates: list[dict]) -> int:
    maximum = 0
    current_speaker: str | None = None
    current_run = 0
    for item in candidates:
        speaker = item.get("primary_speaker")
        if not speaker:
            current_speaker = None
            current_run = 0
            continue
        if speaker == current_speaker:
            current_run += 1
        else:
            current_speaker = str(speaker)
            current_run = 1
        maximum = max(maximum, current_run)
    return maximum


def _transitions_valid(payload: dict) -> bool:
    duration = int(payload.get("duration") or 0)
    for field in ("transition_in", "transition_out"):
        transition = payload.get(field)
        if transition is None:
            continue
        transition_duration = int(transition.get("duration") or 0)
        if (
            transition.get("kind") != "fade"
            or transition_duration <= 0
            or transition_duration > duration
        ):
            return False
    return True


def evaluate_plan(plan: dict) -> dict:
    candidates = plan.get("candidates") or []
    operations = plan.get("operations") or []
    candidate_keys = {
        (item["asset_id"], item["unit_index"])
        for item in candidates
    }

    selected_duration_sec = round(
        sum(_candidate_duration(item) for item in candidates),
        3,
    )
    dead_air_removed_sec = round(
        sum(
            max(0.0, float(item.get("dead_air_removed_sec") or 0.0))
            for item in candidates
        ),
        3,
    )
    scores = [
        float(item.get("final_score", 0.0))
        for item in candidates
    ]
    roles = [
        str(item.get("narrative_role") or "")
        for item in candidates
    ]
    primary_speakers = [
        str(item.get("primary_speaker"))
        for item in candidates
        if item.get("primary_speaker")
    ]
    speaker_switches = sum(
        1
        for previous, current in zip(
            primary_speakers,
            primary_speakers[1:],
        )
        if previous != current
    )

    grounded = True
    transitions_valid = True
    for operation in operations:
        operation_type = operation.get("operation")
        payload = operation.get("payload") or {}
        metadata = payload.get("metadata") or {}

        if operation_type == "add_clip":
            key = (
                payload.get("asset_id"),
                metadata.get("source_unit_index"),
            )
            if key not in candidate_keys:
                grounded = False

        elif operation_type == "add_broll_overlay":
            if (
                not payload.get("asset_id")
                or not metadata.get("source_intelligence_id")
                or metadata.get("source_observation_index") is None
            ):
                grounded = False
            transitions_valid = (
                transitions_valid and _transitions_valid(payload)
            )

        elif operation_type == "add_music_bed":
            if (
                not payload.get("asset_id")
                or not metadata.get("music_bed")
                or not metadata.get("user_selected_music")
            ):
                grounded = False
            volume = float(payload.get("volume", -1.0))
            if volume < 0.0 or volume > 1.0:
                grounded = False
            transitions_valid = (
                transitions_valid and _transitions_valid(payload)
            )

        elif operation_type == "add_caption":
            style = payload.get("style") or {}
            if style.get("source") != "transcript":
                grounded = False

    primary_clip_part_count = sum(
        1
        for operation in operations
        if operation.get("operation") == "add_clip"
    )
    rhythm_snapped_overlay_count = sum(
        1
        for operation in operations
        if operation.get("operation") == "add_broll_overlay"
        and bool(
            ((operation.get("payload") or {}).get("metadata") or {}).get(
                "rhythm_snapped"
            )
        )
    )
    faded_overlay_count = sum(
        1
        for operation in operations
        if operation.get("operation") == "add_broll_overlay"
        and (operation.get("payload") or {}).get("transition_in")
        and (operation.get("payload") or {}).get("transition_out")
    )
    music_bed_count = sum(
        1
        for operation in operations
        if operation.get("operation") == "add_music_bed"
    )

    return {
        "operation_count": len(operations),
        "selected_duration_sec": selected_duration_sec,
        "dead_air_removed_sec": dead_air_removed_sec,
        "primary_clip_part_count": primary_clip_part_count,
        "rhythm_snapped_overlay_count": rhythm_snapped_overlay_count,
        "faded_overlay_count": faded_overlay_count,
        "music_bed_count": music_bed_count,
        "transitions_valid": transitions_valid,
        "average_highlight_score": (
            round(sum(scores) / len(scores), 4)
            if scores
            else 0.0
        ),
        "hook_present": "hook" in roles,
        "payoff_present": "payoff" in roles,
        "all_operations_grounded": grounded,
        "candidate_count": len(candidates),
        "speaker_count": len(set(primary_speakers)),
        "speaker_switch_count": speaker_switches,
        "max_same_speaker_run": _max_speaker_run(candidates),
    }
