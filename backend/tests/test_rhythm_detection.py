"""Signal-level tests for deterministic rhythm onset detection."""
from __future__ import annotations

import math
import struct
import wave

from services.rhythm_detection import detect_rhythm_events


def _write_pulse_wav(path):
    sample_rate = 16000
    samples = []
    sections = [
        (0.8, 0),
        (0.2, 10000),
        (0.8, 0),
        (0.2, 12000),
        (0.8, 0),
    ]
    phase = 0
    for duration, amplitude in sections:
        count = round(duration * sample_rate)
        for index in range(count):
            if amplitude:
                value = int(
                    amplitude
                    * math.sin(2 * math.pi * 440 * phase / sample_rate)
                )
                phase += 1
            else:
                value = 0
            samples.append(value)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(
            b"".join(struct.pack("<h", value) for value in samples)
        )


def test_detects_strong_energy_onsets(tmp_path):
    audio = tmp_path / "pulses.wav"
    _write_pulse_wav(audio)

    events = detect_rhythm_events(audio)
    times = [event["time"] for event in events]

    assert any(0.75 <= time <= 0.9 for time in times)
    assert any(1.75 <= time <= 1.9 for time in times)
