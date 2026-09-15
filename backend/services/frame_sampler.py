"""Representative-frame extraction for scene-aware visual intelligence."""
from __future__ import annotations

import subprocess
from pathlib import Path

from core.config import settings


class FrameSamplingError(RuntimeError):
    pass


def _run(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise FrameSamplingError(str(exc)) from exc
    if completed.returncode != 0:
        raise FrameSamplingError((completed.stderr or "frame extraction failed")[-3000:])


def representative_times(
    scenes: list[dict],
    *,
    duration_sec: float | None,
    max_frames: int,
) -> list[float]:
    times: list[float] = []
    for scene in scenes:
        start = float(scene.get("start") or 0.0)
        end_raw = scene.get("end")
        end = float(end_raw) if end_raw is not None else None
        if end is not None and end > start:
            timestamp = start + (end - start) / 2.0
        else:
            timestamp = start + 0.25
        if duration_sec is not None:
            timestamp = min(timestamp, max(0.0, float(duration_sec) - 0.05))
        times.append(max(0.0, timestamp))

    if not times and duration_sec and duration_sec > 0:
        times = [min(float(duration_sec) / 2.0, max(0.0, float(duration_sec) - 0.05))]

    # Deterministically downsample across the full media duration.
    if len(times) > max_frames:
        if max_frames == 1:
            times = [times[len(times) // 2]]
        else:
            indexes = [
                round(i * (len(times) - 1) / (max_frames - 1))
                for i in range(max_frames)
            ]
            times = [times[index] for index in indexes]

    return times


def extract_frames(
    source: Path,
    destination_dir: Path,
    *,
    scenes: list[dict],
    duration_sec: float | None,
    max_frames: int,
) -> list[dict]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    observations: list[dict] = []
    for index, timestamp in enumerate(
        representative_times(
            scenes,
            duration_sec=duration_sec,
            max_frames=max_frames,
        )
    ):
        output = destination_dir / f"frame-{index:03d}.jpg"
        _run(
            [
                settings.FFMPEG_PATH,
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(960,iw)':-2",
                "-q:v",
                "3",
                str(output),
            ]
        )
        if output.is_file() and output.stat().st_size > 0:
            observations.append(
                {
                    "index": index,
                    "time": round(timestamp, 3),
                    "path": output,
                }
            )
    return observations
