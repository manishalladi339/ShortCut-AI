"""Evidence-gated subject-aware reframing.

This module never performs identity recognition or cross-frame face tracking.
It uses only frame-local visual evidence from persisted media intelligence.
"""
from __future__ import annotations

from typing import Any


def _subject_center(box: dict) -> tuple[float, float]:
    return (
        float(box["x"]) + float(box["width"]) / 2.0,
        float(box["y"]) + float(box["height"]) / 2.0,
    )


def _choose_subject(observation: dict) -> tuple[dict, str, float] | None:
    subjects = [
        item
        for item in (observation.get("subjects") or [])
        if isinstance(item, dict) and isinstance(item.get("box"), dict)
    ]
    people_count = int(observation.get("people_count") or 0)
    if not subjects:
        return None

    # A one-person shot is safe to center without claiming speaker identity.
    if people_count <= 1 and len(subjects) == 1:
        subject = subjects[0]
        prominence = float(subject.get("prominence") or 0.0)
        if prominence >= 0.45:
            return (
                subject,
                "single_visible_subject",
                round(max(0.55, min(1.0, prominence)), 4),
            )
        return None

    # Multi-person footage is reframed only when visible speaking cues are
    # meaningfully stronger for one frame-local person.
    ranked = sorted(
        subjects,
        key=lambda item: float(item.get("speaking_likelihood") or 0.0),
        reverse=True,
    )
    top = ranked[0]
    top_score = float(top.get("speaking_likelihood") or 0.0)
    second_score = (
        float(ranked[1].get("speaking_likelihood") or 0.0)
        if len(ranked) > 1
        else 0.0
    )
    if top_score >= 0.72 and top_score - second_score >= 0.18:
        return (
            top,
            "visible_speaking_cue",
            round(top_score, 4),
        )
    return None


def calculate_reframe_transform(
    *,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    box: dict,
) -> dict | None:
    if min(source_width, source_height, target_width, target_height) <= 0:
        return None

    x = float(box.get("x") or 0.0)
    y = float(box.get("y") or 0.0)
    width = float(box.get("width") or 0.0)
    height = float(box.get("height") or 0.0)
    if width <= 0 or height <= 0:
        return None

    center_x, center_y = _subject_center(
        {"x": x, "y": y, "width": width, "height": height}
    )

    # Render executor first performs a contain-fit into the output canvas.
    contain = min(
        target_width / source_width,
        target_height / source_height,
    )
    base_width = source_width * contain
    base_height = source_height * contain

    # Additional ProjectState scale converts the contain fit to a cover crop.
    cover_scale = max(
        target_width / max(1e-9, base_width),
        target_height / max(1e-9, base_height),
    )
    covered_width = base_width * cover_scale
    covered_height = base_height * cover_scale

    # Wide shots may benefit from a small additional zoom, but cap it so the
    # planner does not generate aggressive face crops from sparse observations.
    desired_subject_width = target_width * 0.28
    desired_subject_height = target_height * 0.38
    current_subject_width = width * covered_width
    current_subject_height = height * covered_height
    subject_zoom = max(
        1.0,
        desired_subject_width / max(1e-9, current_subject_width),
        desired_subject_height / max(1e-9, current_subject_height),
    )
    subject_zoom = min(1.35, subject_zoom)

    scale = min(10.0, cover_scale * subject_zoom)
    final_width = base_width * scale
    final_height = base_height * scale

    # Place the subject slightly above vertical center when geometry permits.
    target_center_x = target_width * 0.5
    target_center_y = target_height * 0.46
    desired_left = target_center_x - center_x * final_width
    desired_top = target_center_y - center_y * final_height

    min_left = min(0.0, target_width - final_width)
    max_left = max(0.0, target_width - final_width)
    min_top = min(0.0, target_height - final_height)
    max_top = max(0.0, target_height - final_height)

    left = max(min_left, min(max_left, desired_left))
    top = max(min_top, min(max_top, desired_top))

    default_left = (target_width - final_width) / 2.0
    default_top = (target_height - final_height) / 2.0
    position_x = left - default_left
    position_y = top - default_top

    # No-op transforms add noise to plan review and metadata.
    if (
        abs(scale - 1.0) < 0.01
        and abs(position_x) < 2.0
        and abs(position_y) < 2.0
    ):
        return None

    return {
        "scale": round(scale, 6),
        "position_x": round(position_x, 3),
        "position_y": round(position_y, 3),
        "rotation_deg": 0.0,
        "opacity": 1.0,
    }


def build_reframe_suggestion(
    *,
    record: dict,
    start: float,
    end: float,
    source_width: int | None,
    source_height: int | None,
    target_width: int,
    target_height: int,
) -> dict | None:
    if not source_width or not source_height or end <= start:
        return None

    midpoint = start + (end - start) / 2.0
    observations = [
        item
        for item in (record.get("visual_observations") or [])
        if start <= float(item.get("time") or -1.0) <= end
        and item.get("subjects")
    ]
    if not observations:
        return None

    observation = min(
        observations,
        key=lambda item: abs(float(item.get("time") or 0.0) - midpoint),
    )
    chosen = _choose_subject(observation)
    if not chosen:
        return None

    subject, strategy, confidence = chosen
    transform = calculate_reframe_transform(
        source_width=int(source_width),
        source_height=int(source_height),
        target_width=int(target_width),
        target_height=int(target_height),
        box=subject["box"],
    )
    if not transform:
        return None

    return {
        "transform": transform,
        "strategy": strategy,
        "confidence": confidence,
        "observation_index": observation.get("index"),
        "observation_time": float(observation.get("time") or 0.0),
        "subject_label": str(subject.get("label") or "visible_subject"),
        "subject_box": dict(subject["box"]),
        "people_count": int(observation.get("people_count") or 0),
        "speaking_likelihood": subject.get("speaking_likelihood"),
        "identity_claimed": False,
    }
