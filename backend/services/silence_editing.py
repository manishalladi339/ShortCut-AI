"""Silence-aware source-boundary refinement for AI-selected spoken clips."""
from __future__ import annotations


def snap_outward_to_silence(
    *,
    start: float,
    end: float,
    silences: list[dict],
    snap_window_sec: float,
) -> tuple[float, float, list[str]]:
    """Expand a spoken range toward nearby silence boundaries without cutting speech.

    Cut-in snaps backward to the latest silence end before the transcript start.
    Cut-out snaps forward to the earliest silence start after the transcript end.
    """
    refined_start = max(0.0, float(start))
    refined_end = max(refined_start, float(end))
    reasons: list[str] = []

    start_candidates = [
        float(item["end"])
        for item in silences
        if float(item.get("end", -1.0)) <= refined_start
        and refined_start - float(item["end"]) <= snap_window_sec
    ]
    if start_candidates:
        snapped = max(start_candidates)
        if abs(snapped - refined_start) > 0.001:
            refined_start = snapped
            reasons.append("cut-in expanded to nearby silence boundary")

    end_candidates = [
        float(item["start"])
        for item in silences
        if float(item.get("start", -1.0)) >= refined_end
        and float(item["start"]) - refined_end <= snap_window_sec
    ]
    if end_candidates:
        snapped = min(end_candidates)
        if abs(snapped - refined_end) > 0.001:
            refined_end = snapped
            reasons.append("cut-out expanded to nearby silence boundary")

    return refined_start, refined_end, reasons
