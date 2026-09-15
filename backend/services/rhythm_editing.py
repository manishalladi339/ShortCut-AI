"""Map source-audio rhythm evidence onto a compacted output timeline."""
from __future__ import annotations


def map_rhythm_to_timeline(
    *,
    source_segments: list[dict],
    rhythm_events: list[dict],
    timeline_start: int,
    ticks_per_second: float,
) -> list[dict]:
    mapped: list[dict] = []
    cursor = int(timeline_start)

    for segment in source_segments:
        source_start = float(segment["start"])
        source_end = float(segment["end"])
        segment_ticks = max(
            1,
            round((source_end - source_start) * ticks_per_second),
        )

        for event in rhythm_events:
            event_time = float(event.get("time", -1.0))
            if source_start <= event_time < source_end:
                mapped.append(
                    {
                        "timeline_tick": cursor
                        + round((event_time - source_start) * ticks_per_second),
                        "source_time": event_time,
                        "strength": float(event.get("strength") or 0.0),
                    }
                )
        cursor += segment_ticks

    mapped.sort(key=lambda item: item["timeline_tick"])
    return mapped


def snap_forward_to_rhythm(
    *,
    desired_tick: int,
    rhythm_events: list[dict],
    max_delay_ticks: int,
    min_strength: float = 0.0,
) -> tuple[int, dict | None]:
    """Snap an entrance forward to the earliest strong nearby onset."""
    upper = desired_tick + max(0, int(max_delay_ticks))
    eligible = [
        event
        for event in rhythm_events
        if desired_tick <= int(event["timeline_tick"]) <= upper
        and float(event.get("strength") or 0.0) >= min_strength
    ]
    if not eligible:
        return desired_tick, None
    event = min(
        eligible,
        key=lambda item: (int(item["timeline_tick"]), -float(item.get("strength") or 0.0)),
    )
    return int(event["timeline_tick"]), event
