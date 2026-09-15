"""Deterministic FFmpeg scene-change detection."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.config import settings

PTS_RE = re.compile(r"pts_time:(?P<time>\d+(?:\.\d+)?)")
SCORE_RE = re.compile(r"lavfi\.scene_score=(?P<score>\d+(?:\.\d+)?)")


class SceneDetectionError(RuntimeError):
    pass


def detect_scenes(source: Path, duration_sec: float | None) -> list[dict]:
    threshold = settings.SCENE_DETECTION_THRESHOLD
    command = [
        settings.FFMPEG_PATH,
        "-hide_banner",
        "-i",
        str(source),
        "-vf",
        f"select='gt(scene,{threshold})',metadata=print",
        "-an",
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
        raise SceneDetectionError(str(exc)) from exc

    stderr = completed.stderr or ""
    if completed.returncode != 0:
        raise SceneDetectionError(stderr[-3000:])

    points: list[tuple[float, float | None]] = []
    last_time: float | None = None
    for line in stderr.splitlines():
        time_match = PTS_RE.search(line)
        if time_match:
            last_time = float(time_match.group("time"))
            continue
        score_match = SCORE_RE.search(line)
        if score_match and last_time is not None:
            points.append((last_time, float(score_match.group("score"))))
            last_time = None

    boundaries = [0.0] + [t for t, _ in points]
    if duration_sec and (not boundaries or duration_sec > boundaries[-1]):
        boundaries.append(float(duration_sec))

    scenes: list[dict] = []
    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else duration_sec
        if end is not None and end <= start:
            continue
        score = None
        if idx > 0 and idx - 1 < len(points):
            score = points[idx - 1][1]
        scenes.append({"start": start, "end": end, "score": score})
    return scenes
