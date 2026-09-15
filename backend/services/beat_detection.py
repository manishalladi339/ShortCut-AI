"""Conservative tempo/beat-grid estimation from measured audio onsets."""
from __future__ import annotations

import statistics


def estimate_beat_grid(
    onsets: list[float],
    *,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    regularity_tolerance: float = 0.18,
    min_confidence: float = 0.65,
) -> dict | None:
    """Estimate a regular beat grid only when measured onset spacing supports it."""
    ordered_onsets = sorted(float(value) for value in onsets)
    if len(ordered_onsets) < 4:
        return None

    intervals = [
        current - previous
        for previous, current in zip(ordered_onsets, ordered_onsets[1:])
        if current > previous
    ]
    min_period = 60.0 / max_bpm
    max_period = 60.0 / min_bpm
    valid = [
        interval
        for interval in intervals
        if min_period <= interval <= max_period
    ]
    if len(valid) < 3:
        return None

    period = statistics.median(valid)
    if period <= 0:
        return None
    deviations = [
        abs(interval - period) / period
        for interval in valid
    ]
    regular_count = sum(
        deviation <= regularity_tolerance
        for deviation in deviations
    )
    confidence = regular_count / len(valid)
    if confidence < min_confidence:
        return None

    # Anchor to the first measured onset and generate a deterministic grid only
    # across the observed range; do not extrapolate outside known audio evidence.
    start = ordered_onsets[0]
    end = ordered_onsets[-1]
    beats: list[float] = []
    tick = start
    while tick <= end + period * 0.25:
        beats.append(round(tick, 6))
        tick += period

    return {
        "bpm": round(60.0 / period, 3),
        "period_sec": round(period, 6),
        "confidence": round(confidence, 4),
        "beats": beats,
        "source": "energy_onsets",
    }


def nearest_beat(
    time_sec: float,
    beats: list[float],
    max_shift_sec: float,
) -> float | None:
    if not beats:
        return None
    nearest = min(
        (float(value) for value in beats),
        key=lambda value: abs(value - time_sec),
    )
    return (
        nearest
        if abs(nearest - time_sec) <= max_shift_sec
        else None
    )
