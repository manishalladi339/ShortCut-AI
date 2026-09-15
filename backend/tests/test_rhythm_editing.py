"""Tests for rhythm evidence mapping and entrance snapping."""
from services.rhythm_editing import map_rhythm_to_timeline, snap_forward_to_rhythm


def test_maps_events_across_compacted_source_segments():
    mapped = map_rhythm_to_timeline(
        source_segments=[
            {"start": 0.0, "end": 2.0},
            {"start": 4.0, "end": 6.0},
        ],
        rhythm_events=[
            {"time": 1.0, "strength": 0.6},
            {"time": 3.0, "strength": 0.9},
            {"time": 4.5, "strength": 0.7},
        ],
        timeline_start=1000,
        ticks_per_second=1000.0,
    )
    assert mapped == [
        {"timeline_tick": 2000, "source_time": 1.0, "strength": 0.6},
        {"timeline_tick": 3500, "source_time": 4.5, "strength": 0.7},
    ]


def test_snaps_forward_to_nearby_onset_only():
    events = [
        {"timeline_tick": 1100, "strength": 0.5},
        {"timeline_tick": 1300, "strength": 0.9},
    ]
    tick, event = snap_forward_to_rhythm(
        desired_tick=1000,
        rhythm_events=events,
        max_delay_ticks=200,
        min_strength=0.1,
    )
    assert tick == 1100
    assert event["strength"] == 0.5


def test_keeps_original_tick_when_no_onset_is_close():
    tick, event = snap_forward_to_rhythm(
        desired_tick=1000,
        rhythm_events=[{"timeline_tick": 1500, "strength": 1.0}],
        max_delay_ticks=200,
    )
    assert tick == 1000
    assert event is None
