"""Tests for deterministic beat intelligence."""
from services.beat_detection import estimate_beat_grid, nearest_beat


def test_estimates_regular_120_bpm_grid():
    result = estimate_beat_grid([0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
    assert result is not None
    assert result["bpm"] == 120.0
    assert result["confidence"] == 1.0


def test_rejects_irregular_onsets():
    assert estimate_beat_grid([0.0, 0.31, 0.93, 1.18, 2.0, 2.42]) is None


def test_nearest_beat_respects_shift_limit():
    beats = [0.0, 0.5, 1.0, 1.5]
    assert nearest_beat(1.08, beats, 0.1) == 1.0
    assert nearest_beat(1.2, beats, 0.1) is None
