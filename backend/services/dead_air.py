"""Deterministic dead-air compaction for selected source ranges."""
from __future__ import annotations


def compact_source_ranges(
    *,
    start: float,
    end: float,
    silences: list[dict],
    min_dead_air_sec: float,
    retain_pause_sec: float = 0.12,
    min_segment_sec: float = 0.35,
) -> tuple[list[dict], float]:
    """Split a source range around long internal silences.

    Edge pauses are intentionally preserved. For an internal silence, a small
    amount of pause is retained on both sides so speech does not feel slammed
    together.
    """
    start = max(0.0, float(start))
    end = max(start, float(end))
    if end <= start:
        return [], 0.0

    removals: list[tuple[float, float]] = []
    for item in sorted(silences, key=lambda value: float(value.get("start", 0.0))):
        silence_start = float(item.get("start", 0.0))
        silence_end = float(item.get("end", silence_start))
        silence_duration = max(0.0, silence_end - silence_start)

        # Only remove silence that is internal to the selected spoken range.
        if silence_start <= start or silence_end >= end:
            continue
        if silence_duration < min_dead_air_sec:
            continue

        remove_start = min(silence_end, silence_start + retain_pause_sec)
        remove_end = max(silence_start, silence_end - retain_pause_sec)
        if remove_end <= remove_start:
            continue
        removals.append((remove_start, remove_end))

    if not removals:
        return ([{"start": start, "end": end}], 0.0)

    ranges: list[dict] = []
    cursor = start
    removed = 0.0
    for remove_start, remove_end in removals:
        if remove_start <= cursor:
            cursor = max(cursor, remove_end)
            continue

        before_duration = remove_start - cursor
        remaining_after = end - remove_end
        if before_duration < min_segment_sec or remaining_after < min_segment_sec:
            continue

        ranges.append({"start": cursor, "end": remove_start})
        removed += remove_end - remove_start
        cursor = remove_end

    if end - cursor >= min_segment_sec:
        ranges.append({"start": cursor, "end": end})
    elif ranges:
        # If the last retained fragment is tiny, keep it attached rather than
        # deleting potentially spoken content.
        ranges[-1]["end"] = end
        removed = max(
            0.0,
            (end - start)
            - sum(float(item["end"]) - float(item["start"]) for item in ranges),
        )
    else:
        return ([{"start": start, "end": end}], 0.0)

    normalized = [
        {
            "start": round(float(item["start"]), 6),
            "end": round(float(item["end"]), 6),
        }
        for item in ranges
        if float(item["end"]) > float(item["start"])
    ]
    kept = sum(item["end"] - item["start"] for item in normalized)
    removed = max(0.0, (end - start) - kept)
    return normalized, round(removed, 6)
