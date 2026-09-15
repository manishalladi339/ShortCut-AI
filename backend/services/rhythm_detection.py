"""Deterministic short-time energy onset detection for normalized PCM WAV audio."""
from __future__ import annotations

import math
import statistics
import struct
import wave
from pathlib import Path

from core.config import settings


class RhythmDetectionError(RuntimeError):
    pass


def _window_rms(raw: bytes, sample_width: int) -> float:
    if sample_width != 2:
        raise RhythmDetectionError("rhythm detector requires 16-bit PCM WAV")
    sample_count = len(raw) // 2
    if sample_count <= 0:
        return 0.0
    total = 0.0
    for (sample,) in struct.iter_unpack("<h", raw[: sample_count * 2]):
        total += float(sample) * float(sample)
    return math.sqrt(total / sample_count)


def detect_rhythm_events(audio_path: Path) -> list[dict]:
    """Detect strong energy onsets.

    These are rhythm/onset markers, not a claimed musical beat grid.
    """
    try:
        handle = wave.open(str(audio_path), "rb")
    except (wave.Error, OSError) as exc:
        raise RhythmDetectionError(str(exc)) from exc

    with handle:
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        if sample_rate <= 0 or channels <= 0:
            raise RhythmDetectionError("invalid WAV format")
        if sample_width != 2:
            raise RhythmDetectionError("rhythm detector requires 16-bit PCM WAV")

        window_frames = max(
            1,
            round(sample_rate * settings.RHYTHM_WINDOW_MS / 1000.0),
        )
        energies: list[float] = []
        while True:
            raw = handle.readframes(window_frames)
            if not raw:
                break
            energies.append(_window_rms(raw, sample_width))

    if len(energies) < 4:
        return []

    baseline_windows = max(
        3,
        round(settings.RHYTHM_BASELINE_SEC * 1000.0 / settings.RHYTHM_WINDOW_MS),
    )
    window_sec = settings.RHYTHM_WINDOW_MS / 1000.0
    events: list[dict] = []

    for index in range(1, len(energies)):
        energy = energies[index]
        if energy < settings.RHYTHM_MIN_RMS:
            continue

        baseline_slice = energies[max(0, index - baseline_windows):index]
        if len(baseline_slice) < 2:
            continue
        baseline = max(1.0, statistics.median(baseline_slice))
        ratio = energy / baseline
        previous = energies[index - 1]

        if ratio < settings.RHYTHM_ENERGY_RATIO:
            continue
        if energy < previous:
            continue

        time_sec = index * window_sec
        strength = min(
            1.0,
            max(
                0.0,
                (ratio - settings.RHYTHM_ENERGY_RATIO)
                / max(settings.RHYTHM_ENERGY_RATIO * 2.0, 0.001),
            ),
        )
        event = {
            "time": round(time_sec, 6),
            "strength": round(strength, 6),
            "energy": round(energy, 3),
            "energy_ratio": round(ratio, 4),
        }

        if events and time_sec - events[-1]["time"] < settings.RHYTHM_MIN_INTERVAL_SEC:
            if event["energy_ratio"] > events[-1]["energy_ratio"]:
                events[-1] = event
            continue
        events.append(event)

    return events
