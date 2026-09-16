"""Generated-media integration test for visual transitions."""
from __future__ import annotations

import subprocess
from pathlib import Path

from models.render_plan import RenderClip, RenderPlan, RenderTransition
from services.render_executor import execute
from services.storage import get_storage


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True)


def _test_video(path: Path, duration: float) -> None:
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
            f"testsrc2=s=320x180:r=30:d={duration}",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def test_ffmpeg_render_executes_slide_in_and_fade_out(tmp_path):
    storage = get_storage()
    key = "tests/transition-render/source.mp4"
    source = storage.local_path(key)
    _test_video(source, 3.0)

    plan = RenderPlan(
        project_id="p",
        project_state_version=8,
        sequence_id="seq",
        width=320,
        height=180,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=3000,
        clips=[
            RenderClip(
                clip_id="transitioned",
                track_id="main",
                track_kind="video",
                track_index=0,
                asset_id="source",
                source_storage_key=key,
                timeline_start=0,
                duration=3000,
                source_start=0,
                source_duration=3000,
                playback_rate=1.0,
                volume=0.0,
                transition_in=RenderTransition(kind="slide_left", duration=300),
                transition_out=RenderTransition(kind="fade", duration=250),
                metadata={
                    "_asset_kind": "video",
                    "_asset_audio_codec": None,
                    "_transform": {
                        "scale": 1.0,
                        "position_x": 0.0,
                        "position_y": 0.0,
                        "rotation_deg": 0.0,
                        "opacity": 1.0,
                        "keyframes": [],
                    },
                },
            )
        ],
    )

    output = tmp_path / "transitioned.mp4"
    result = execute(plan, output)

    assert output.is_file()
    assert output.stat().st_size > 0
    assert result["visual_clip_count"] == 1

    probe = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(output),
        ]
    )
    assert probe.stdout.decode("utf-8").strip().startswith("320,180")
