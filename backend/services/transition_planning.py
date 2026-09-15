"""Deterministic transition planning for grounded visual overlays."""
from __future__ import annotations


def broll_fade_ticks(
    *,
    clip_duration_ticks: int,
    ticks_per_second: float,
    requested_fade_sec: float,
    rhythm_event: dict | None = None,
) -> tuple[int, dict]:
    """Return a bounded fade duration and auditable strategy metadata.

    A fade is never allowed to consume more than one quarter of the overlay,
    which prevents fade-in and fade-out from overlapping on short B-roll.
    When a high-confidence beat grid is available, the requested fade is
    additionally bounded to a quarter beat.
    """
    duration = max(0, int(clip_duration_ticks))
    if duration <= 1 or ticks_per_second <= 0:
        return 0, {"strategy": "disabled", "reason": "clip_too_short"}

    requested = max(0.0, float(requested_fade_sec))
    desired_sec = requested
    strategy = "requested"

    if rhythm_event and rhythm_event.get("signal") == "beat_grid":
        bpm = float(rhythm_event.get("bpm") or 0.0)
        confidence = float(rhythm_event.get("confidence") or 0.0)
        if bpm > 0 and confidence >= 0.65:
            quarter_beat_sec = 15.0 / bpm
            desired_sec = min(desired_sec, quarter_beat_sec)
            strategy = "quarter_beat_bounded"

    desired_ticks = max(1, round(desired_sec * ticks_per_second))
    duration_cap = max(1, duration // 4)
    fade_ticks = min(desired_ticks, duration_cap)

    return fade_ticks, {
        "strategy": strategy,
        "requested_fade_sec": round(requested, 6),
        "planned_fade_sec": round(fade_ticks / ticks_per_second, 6),
        "clip_fraction_cap": 0.25,
    }
