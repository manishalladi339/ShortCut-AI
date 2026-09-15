"""Tests for silence-aware edit-boundary snapping."""
from services.silence_editing import snap_outward_to_silence


def test_snaps_outward_without_cutting_spoken_range():
    start, end, reasons = snap_outward_to_silence(
        start=5.0,
        end=10.0,
        silences=[
            {"start": 3.9, "end": 4.6, "duration": 0.7},
            {"start": 10.4, "end": 11.0, "duration": 0.6},
        ],
        snap_window_sec=0.75,
    )
    assert start == 4.6
    assert end == 10.4
    assert len(reasons) == 2


def test_does_not_snap_to_distant_silence():
    assert snap_outward_to_silence(
        start=5.0,
        end=10.0,
        silences=[
            {"start": 1.0, "end": 2.0, "duration": 1.0},
            {"start": 12.0, "end": 13.0, "duration": 1.0},
        ],
        snap_window_sec=0.75,
    ) == (5.0, 10.0, [])
