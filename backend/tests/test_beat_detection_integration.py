"""Signal integration: measured click onsets produce a high-confidence beat grid."""
from __future__ import annotations

import math
import struct
import wave

from services.beat_detection import estimate_beat_grid
from services.rhythm_detection import detect_rhythm_events


def _write_click_track(path):
    sample_rate = 16000
    duration_sec = 4.5
    total = round(duration_sec * sample_rate)
    samples = [0] * total

    for beat_index in range(8):
        start = round((0.5 + beat_index * 0.5) * sample_rate)
        width = round(0.06 * sample_rate)
        for offset in range(width):
            index = start + offset
            if index >= total:
                break
            samples[index] = int(
                14000
                * math.sin(2 * math.pi * 900 * offset / sample_rate)
            )

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(
            b"".join(struct.pack("<h", value) for value in samples)
        )


def test_click_track_yields_about_120_bpm(tmp_path):
    path = tmp_path / "clicks.wav"
    _write_click_track(path)

    events = detect_rhythm_events(path)
    grid = estimate_beat_grid(
        [event["time"] for event in events]
    )

    assert grid is not None
    assert 118.0 <= grid["bpm"] <= 122.0
    assert grid["confidence"] >= 0.8
