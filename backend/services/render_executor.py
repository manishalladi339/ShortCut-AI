"""Execute a deterministic RenderPlan using FFmpeg.

The first executor intentionally supports a constrained but real subset:
- one primary video track
- non-overlapping video clips on that track
- clip trims, playback rate and timeline gaps
- optional audio carried with source video
- H.264/AAC MP4 output

Unsupported compositions fail explicitly rather than producing a misleading render.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import settings
from models.render_plan import RenderPlan
from services.storage import get_storage, materialize


class RenderExecutionError(RuntimeError):
    pass


def _ticks_to_seconds(ticks: int, numerator: int, denominator: int) -> float:
    return ticks * denominator / numerator


def _run(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.RENDER_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RenderExecutionError("ffmpeg is not installed or FFMPEG_PATH is invalid") from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderExecutionError("render timed out") from exc
    if completed.returncode != 0:
        raise RenderExecutionError((completed.stderr or "ffmpeg failed").strip()[-4000:])


def execute(plan: RenderPlan, output_path: Path) -> dict:
    """Render the supported subset of a plan to MP4."""
    video_clips = [c for c in plan.clips if c.track_kind == "video"]
    if not video_clips:
        raise RenderExecutionError("render requires at least one video clip")

    track_ids = {c.track_id for c in video_clips}
    if len(track_ids) != 1:
        raise RenderExecutionError("multi-video-track compositing is not implemented yet")

    # Reject overlaps for now; gaps are rendered as black.
    ordered = sorted(video_clips, key=lambda c: c.timeline_start)
    previous_end = 0
    for clip in ordered:
        if clip.timeline_start < previous_end:
            raise RenderExecutionError("overlapping video clips require compositing support")
        previous_end = clip.timeline_start + clip.duration

    storage = get_storage()
    with TemporaryDirectory(prefix="shortcut-render-") as tmp:
        root = Path(tmp)
        segment_paths: list[Path] = []
        cursor = 0

        for index, clip in enumerate(ordered):
            if clip.timeline_start > cursor:
                gap_ticks = clip.timeline_start - cursor
                gap_sec = _ticks_to_seconds(
                    gap_ticks, plan.timebase_numerator, plan.timebase_denominator
                )
                gap = root / f"gap-{index}.mp4"
                _run([
                    settings.FFMPEG_PATH, "-y",
                    "-f", "lavfi", "-i",
                    f"color=c=black:s={plan.width}x{plan.height}:r=30:d={gap_sec:.6f}",
                    "-f", "lavfi", "-i",
                    f"anullsrc=r=48000:cl=stereo:d={gap_sec:.6f}",
                    "-shortest",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    str(gap),
                ])
                segment_paths.append(gap)

            source_start = _ticks_to_seconds(
                clip.source_start, plan.timebase_numerator, plan.timebase_denominator
            )
            source_duration = _ticks_to_seconds(
                clip.source_duration, plan.timebase_numerator, plan.timebase_denominator
            )
            target_duration = _ticks_to_seconds(
                clip.duration, plan.timebase_numerator, plan.timebase_denominator
            )
            segment = root / f"clip-{index}.mp4"
            suffix = Path(clip.source_storage_key).suffix

            with materialize(clip.source_storage_key, suffix=suffix) as source:
                video_filter = (
                    f"setpts=(PTS-STARTPTS)/{clip.playback_rate},"
                    f"scale={plan.width}:{plan.height}:force_original_aspect_ratio=decrease,"
                    f"pad={plan.width}:{plan.height}:(ow-iw)/2:(oh-ih)/2:black,"
                    "setsar=1"
                )
                audio_filter = f"atempo={clip.playback_rate},volume={clip.volume}"
                command = [
                    settings.FFMPEG_PATH, "-y",
                    "-ss", f"{source_start:.6f}",
                    "-t", f"{source_duration:.6f}",
                    "-i", str(source),
                    "-vf", video_filter,
                    "-af", audio_filter,
                    "-t", f"{target_duration:.6f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(segment),
                ]
                _run(command)

            segment_paths.append(segment)
            cursor = clip.timeline_start + clip.duration

        concat_file = root / "concat.txt"
        concat_file.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in segment_paths),
            encoding="utf-8",
        )
        _run([
            settings.FFMPEG_PATH, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ])

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RenderExecutionError("renderer did not produce a valid output file")

    return {"bytes": output_path.stat().st_size}
