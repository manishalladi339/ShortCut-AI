"""Deterministic transition planning for canonical timeline clips."""
from __future__ import annotations


def bounded_fade_ticks(
    *,
    clip_duration_ticks: int,
    ticks_per_second: float,
    requested_fade_sec: float,
    clip_fraction_cap: float = 0.25,
) -> tuple[int, dict]:
    """Return a fade that cannot consume an unsafe fraction of a clip."""
    duration = max(0, int(clip_duration_ticks))
    if duration <= 1 or ticks_per_second <= 0:
        return 0, {"strategy": "disabled", "reason": "clip_too_short"}
    if clip_fraction_cap <= 0 or clip_fraction_cap > 0.5:
        raise ValueError("clip_fraction_cap must be > 0 and <= 0.5")

    requested = max(0.0, float(requested_fade_sec))
    if requested <= 0:
        return 0, {"strategy": "disabled", "reason": "zero_duration"}

    desired_ticks = max(1, round(requested * ticks_per_second))
    duration_cap = max(1, int(duration * clip_fraction_cap))
    fade_ticks = min(desired_ticks, duration_cap)

    return fade_ticks, {
        "strategy": "requested",
        "requested_fade_sec": round(requested, 6),
        "planned_fade_sec": round(fade_ticks / ticks_per_second, 6),
        "clip_fraction_cap": clip_fraction_cap,
    }


def broll_fade_ticks(
    *,
    clip_duration_ticks: int,
    ticks_per_second: float,
    requested_fade_sec: float,
    rhythm_event: dict | None = None,
) -> tuple[int, dict]:
    """Return a bounded B-roll fade with optional measured beat constraint."""
    desired_sec = max(0.0, float(requested_fade_sec))
    strategy = "requested"

    if rhythm_event and rhythm_event.get("signal") == "beat_grid":
        bpm = float(rhythm_event.get("bpm") or 0.0)
        confidence = float(rhythm_event.get("confidence") or 0.0)
        if bpm > 0 and confidence >= 0.65:
            desired_sec = min(desired_sec, 15.0 / bpm)
            strategy = "quarter_beat_bounded"

    fade_ticks, metadata = bounded_fade_ticks(
        clip_duration_ticks=clip_duration_ticks,
        ticks_per_second=ticks_per_second,
        requested_fade_sec=desired_sec,
        clip_fraction_cap=0.25,
    )
    if fade_ticks > 0:
        metadata["strategy"] = strategy
        metadata["requested_fade_sec"] = round(
            max(0.0, float(requested_fade_sec)),
            6,
        )
    return fade_ticks, metadata
