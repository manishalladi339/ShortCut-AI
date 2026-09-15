"""Tests for deterministic B-roll transition planning."""
from services.transition_planning import broll_fade_ticks


def test_requested_fade_is_used_for_long_overlay():
    ticks, meta = broll_fade_ticks(
        clip_duration_ticks=3000,
        ticks_per_second=1000.0,
        requested_fade_sec=0.18,
    )
    assert ticks == 180
    assert meta["strategy"] == "requested"


def test_fade_is_capped_to_quarter_of_short_overlay():
    ticks, meta = broll_fade_ticks(
        clip_duration_ticks=400,
        ticks_per_second=1000.0,
        requested_fade_sec=0.5,
    )
    assert ticks == 100
    assert meta["planned_fade_sec"] == 0.1


def test_high_confidence_beat_grid_bounds_fade_to_quarter_beat():
    ticks, meta = broll_fade_ticks(
        clip_duration_ticks=3000,
        ticks_per_second=1000.0,
        requested_fade_sec=0.3,
        rhythm_event={
            "signal": "beat_grid",
            "bpm": 120.0,
            "confidence": 0.9,
        },
    )
    assert ticks == 125
    assert meta["strategy"] == "quarter_beat_bounded"


def test_low_confidence_beat_grid_does_not_control_fade():
    ticks, meta = broll_fade_ticks(
        clip_duration_ticks=3000,
        ticks_per_second=1000.0,
        requested_fade_sec=0.3,
        rhythm_event={
            "signal": "beat_grid",
            "bpm": 120.0,
            "confidence": 0.4,
        },
    )
    assert ticks == 300
    assert meta["strategy"] == "requested"
