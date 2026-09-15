"""Transition contract and generated-media regression tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from models.project_state import Clip, ClipTransition
from models.render_plan import RenderClip, RenderPlan, RenderTransition
from services.render_executor import execute
from services.storage import get_storage


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True)


def _solid_video(path: Path, color: str, duration: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={color}:s=160x90:r=30:d={duration}",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ])


def _sample_rgb(path: Path, at_sec: float) -> tuple[int, int, int]:
    result = _run([
        "ffmpeg", "-loglevel", "error", "-ss", str(at_sec),
        "-i", str(path), "-vf", "scale=1:1", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ])
    return tuple(result.stdout[:3])


def test_transition_duration_must_fit_clip():
    with pytest.raises(ValidationError):
        Clip(
            id="clip", asset_id="asset", timeline_start=0,
            duration=100, source_start=0, source_duration=100,
            transition_in=ClipTransition(kind="fade", duration=101),
        )


def test_generated_overlay_visually_fades_in_and_out(tmp_path):
    storage = get_storage()
    primary_key = "tests/fade-render/primary.mp4"
    overlay_key = "tests/fade-render/overlay.mp4"
    primary = storage.local_path(primary_key)
    overlay = storage.local_path(overlay_key)
    _solid_video(primary, "red", 4.0)
    _solid_video(overlay, "blue", 2.0)

    plan = RenderPlan(
        project_id="p", project_state_version=1, sequence_id="seq",
        width=320, height=180,
        timebase_numerator=1000, timebase_denominator=1,
        duration_ticks=4000,
        clips=[
            RenderClip(
                clip_id="primary", track_id="main", track_kind="video",
                track_index=0, asset_id="primary",
                source_storage_key=primary_key, timeline_start=0,
                duration=4000, source_start=0, source_duration=4000,
                playback_rate=1.0, volume=1.0,
                metadata={"_asset_kind": "video", "_asset_audio_codec": None, "_transform": {}},
            ),
            RenderClip(
                clip_id="overlay", track_id="overlay", track_kind="overlay",
                track_index=1, asset_id="overlay",
                source_storage_key=overlay_key, timeline_start=1000,
                duration=2000, source_start=0, source_duration=2000,
                playback_rate=1.0, volume=0.0,
                transition_in=RenderTransition(kind="fade", duration=500),
                transition_out=RenderTransition(kind="fade", duration=500),
                metadata={"_asset_kind": "video", "_asset_audio_codec": None, "_transform": {}},
            ),
        ],
    )

    output = tmp_path / "fade.mp4"
    execute(plan, output)

    before = _sample_rgb(output, 0.5)
    early_fade = _sample_rgb(output, 1.1)
    full_overlay = _sample_rgb(output, 2.0)
    late_fade = _sample_rgb(output, 2.9)
    after = _sample_rgb(output, 3.5)

    assert before[0] > before[2]
    assert early_fade[0] > 0 and early_fade[2] > 0
    assert full_overlay[2] > full_overlay[0]
    assert late_fade[0] > 0 and late_fade[2] > 0
    assert after[0] > after[2]
