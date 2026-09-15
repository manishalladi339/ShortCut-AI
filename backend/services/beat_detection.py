"""Deterministic beat/onset detection from decoded mono PCM audio.

This module deliberately avoids an LLM. It estimates transient onsets from
short-time RMS energy and derives a conservative beat grid only when the onset
sequence is sufficiently regular.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path


def _rms(samples: list[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(float(value) * value for value in samples) / len(samples))


def detect_onsets_from_pcm(
    path: Path,
    *,
    frame_sec: float = 0.02,
    hop_sec: float = 0.01,
    energy_ratio: float = 1.65,
    min_gap_sec: float = 0.12,
) -> list[float]:
    """Return transient onset times from a 16-bit PCM WAV."""
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if sample_width != 2:
        raise ValueError("beat detection requires 16-bit PCM WAV")

    import array

    raw = array.array("h")
    raw.frombytes(frames)
    if channels > 1:
        raw = array.array("h", raw[::channels])
    samples = list(raw)
    frame = max(1, round(frame_sec * sample_rate))
    hop = max(1, round(hop_sec * sample_rate))
    energies: list[float] = []
    for start in range(0, max(0, len(samples) - frame + 1), hop):
        energies.append(_rms(samples[start : start + frame]))
    if len(energies) < 3:
        return []

    onsets: list[float] = []
    last = -min_gap_sec
    for index in range(1, len(energies)):
        history = energies[max(0, index - 20) : index]
        baseline = sum(history) / len(history) if history else 0.0
        current = energies[index]
        previous = energies[index - 1]
        time_sec = index * hop / sample_rate
        if (
            baseline > 0
            and current >= baseline * energy_ratio
            and current > previous * 1.15
            and time_sec - last >= min_gap_sec
        ):
            onsets.append(round(time_sec, 6))
            last = time_sec
    return onsets


def estimate_beat_grid(
    onsets: list[float],
    *,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    regularity_tolerance: float = 0.18,
) -> dict | None:
    """Estimate BPM/grid only for a sufficiently regular onset sequence."""
    if len(onsets) < 4:
        return None
    intervals = [
        current - previous
        for previous, current in zip(onsets, onsets[1:])
        if current > previous
    ]
    valid = [
        interval
        for interval in intervals
        if 60.0 / max_bpm <= interval <= 60.0 / min_bpm
    ]
    if len(valid) < 3:
        return None
    ordered = sorted(valid)
    median = ordered[len(ordered) // 2]
    deviations = [abs(value - median) / median for value in valid]
    regular = [value for value in deviations if value <= regularity_tolerance]
    confidence = len(regular) / len(valid)
    if confidence < 0.65:
        return None
    bpm = 60.0 / median
    return {
        "bpm": round(bpm, 3),
        "period_sec": round(median, 6),
        "confidence": round(confidence, 4),
        "beats": [round(value, 6) for value in onsets],
    }


def nearest_beat(time_sec: float, beats: list[float], max_shift_sec: float) -> float | None:
    if not beats:
        return None
    nearest = min(beats, key=lambda value: abs(value - time_sec))
    return nearest if abs(nearest - time_sec) <= max_shift_sec else None
