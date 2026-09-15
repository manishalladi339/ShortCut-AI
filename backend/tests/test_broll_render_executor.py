"""Generated-media integration test for deterministic B-roll compositing."""
from __future__ import annotations

import subprocess
from pathlib import Path

from models.render_plan import RenderClip, RenderPlan
from services.render_executor import execute
from services.storage import get_storage


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True)


def _solid_video(path: Path, color: str, duration: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=160x90:r=30:d={duration}",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def _sample_rgb(path: Path, at_sec: float) -> tuple[int, int, int]:
    result = _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-ss",
            str(at_sec),
            "-i",
            str(path),
            "-vf",
            "scale=1:1",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
    )
    assert len(result.stdout) >= 3
    return tuple(result.stdout[:3])


def test_ffmpeg_render_visually_replaces_primary_with_broll(tmp_path):
    storage = get_storage()
    primary_key = "tests/broll-render/primary.mp4"
    broll_key = "tests/broll-render/broll.mp4"
    primary = storage.local_path(primary_key)
    broll = storage.local_path(broll_key)

    _solid_video(primary, "red", 4.0)
    _solid_video(broll, "blue", 3.0)

    plan = RenderPlan(
        project_id="p",
        project_state_version=4,
        sequence_id="seq",
        width=320,
        height=180,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=4000,
        clips=[
            RenderClip(
                clip_id="primary",
                track_id="main",
                track_kind="video",
                track_index=0,
                asset_id="primary",
                source_storage_key=primary_key,
                timeline_start=0,
                duration=4000,
                source_start=0,
                source_duration=4000,
                playback_rate=1.0,
                volume=1.0,
                metadata={
                    "_asset_kind": "video",
                    "_asset_audio_codec": None,
                    "_transform": {},
                },
            ),
            RenderClip(
                clip_id="broll",
                track_id="overlay",
                track_kind="overlay",
                track_index=1,
                asset_id="broll",
                source_storage_key=broll_key,
                timeline_start=1000,
                duration=2000,
                source_start=500,
                source_duration=2000,
                playback_rate=1.0,
                volume=0.0,
                metadata={
                    "_asset_kind": "video",
                    "_asset_audio_codec": None,
                    "_transform": {},
                    "broll": True,
                    "replaces_primary_visual": True,
                },
            ),
        ],
    )

    output = tmp_path / "rendered.mp4"
    result = execute(plan, output)

    assert output.is_file()
    assert result["visual_clip_count"] == 2
    before = _sample_rgb(output, 0.5)
    during = _sample_rgb(output, 2.0)
    after = _sample_rgb(output, 3.5)

    assert before[0] > before[2]  # red primary
    assert during[2] > during[0]  # blue B-roll
    assert after[0] > after[2]  # primary returns
