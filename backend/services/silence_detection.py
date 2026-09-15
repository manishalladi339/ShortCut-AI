"""Deterministic silence detection using FFmpeg's silencedetect filter."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.config import settings


class SilenceDetectionError(RuntimeError):
    pass


_START_RE = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_END_RE = re.compile(
    r"silence_end:\s*(-?\d+(?:\.\d+)?)"
    r"(?:\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?))?"
)


def parse_silencedetect_output(
    stderr: str, *, duration_sec: float | None = None
) -> list[dict]:
    """Parse FFmpeg silencedetect stderr into normalized intervals."""
    intervals: list[dict] = []
    current_start: float | None = None

    for line in stderr.splitlines():
        start_match = _START_RE.search(line)
        if start_match:
            current_start = max(0.0, float(start_match.group(1)))
            continue

        end_match = _END_RE.search(line)
        if not end_match:
            continue

        end = max(0.0, float(end_match.group(1)))
        duration_value = end_match.group(2)
        if current_start is None:
            if duration_value is None:
                continue
            duration = max(0.0, float(duration_value))
            start = max(0.0, end - duration)
        else:
            start = current_start
            duration = max(0.0, end - start)

        if end > start:
            intervals.append(
                {
                    "start": round(start, 6),
                    "end": round(end, 6),
                    "duration": round(duration, 6),
                }
            )
        current_start = None

    if current_start is not None and duration_sec is not None:
        end = max(current_start, float(duration_sec))
        if end > current_start:
            intervals.append(
                {
                    "start": round(current_start, 6),
                    "end": round(end, 6),
                    "duration": round(end - current_start, 6),
                }
            )

    return intervals


def detect_silences(
    audio_path: Path, *, duration_sec: float | None = None
) -> list[dict]:
    """Run FFmpeg silencedetect over normalized speech audio."""
    command = [
        settings.FFMPEG_PATH,
        "-hide_banner",
        "-nostats",
        "-i",
        str(audio_path),
        "-af",
        (
            "silencedetect="
            f"noise={settings.SILENCE_NOISE_DB:.2f}dB:"
            f"d={settings.SILENCE_MIN_DURATION_SEC:.3f}"
        ),
        "-f",
        "null",
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise SilenceDetectionError(str(exc)) from exc

    if completed.returncode != 0:
        raise SilenceDetectionError(
            (completed.stderr or "FFmpeg silence detection failed")[-3000:]
        )

    return parse_silencedetect_output(
        completed.stderr or "",
        duration_sec=duration_sec,
    )
