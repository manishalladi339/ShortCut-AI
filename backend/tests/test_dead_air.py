"""Tests for deterministic dead-air compaction."""
from services.dead_air import compact_source_ranges


def test_removes_long_internal_silence_but_keeps_breathing_room():
    ranges, removed = compact_source_ranges(
        start=0.0,
        end=10.0,
        silences=[{"start": 4.0, "end": 6.0, "duration": 2.0}],
        min_dead_air_sec=0.8,
        retain_pause_sec=0.1,
    )
    assert ranges == [
        {"start": 0.0, "end": 4.1},
        {"start": 5.9, "end": 10.0},
    ]
    assert removed == 1.8


def test_does_not_remove_short_pause():
    ranges, removed = compact_source_ranges(
        start=0.0,
        end=5.0,
        silences=[{"start": 2.0, "end": 2.4, "duration": 0.4}],
        min_dead_air_sec=0.8,
    )
    assert ranges == [{"start": 0.0, "end": 5.0}]
    assert removed == 0.0


def test_preserves_edge_silence_added_for_cut_breathing_room():
    ranges, removed = compact_source_ranges(
        start=1.0,
        end=8.0,
        silences=[
            {"start": 1.0, "end": 1.8, "duration": 0.8},
            {"start": 7.2, "end": 8.0, "duration": 0.8},
        ],
        min_dead_air_sec=0.7,
    )
    assert ranges == [{"start": 1.0, "end": 8.0}]
    assert removed == 0.0
