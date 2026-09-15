"""Generated-media integration test for canonical music-bed rendering."""
from __future__ import annotations

import subprocess
from pathlib import Path

from models.render_plan import RenderClip, RenderPlan
from services.media_probe import probe
from services.render_executor import execute
from services.storage import get_storage


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def _solid_video(path: Path, duration: float) -> None:
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
            f"color=c=red:s=160x90:r=30:d={duration}",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def _tone(path: Path, duration: float) -> None:
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
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def test_music_bed_mixes_into_real_render_with_audio_fades(tmp_path):
    storage = get_storage()
    video_key = "tests/music-bed/primary.mp4"
    music_key = "tests/music-bed/music.wav"
    video = storage.local_path(video_key)
    music = storage.local_path(music_key)

    _solid_video(video, 4.0)
    _tone(music, 4.0)

    plan = RenderPlan(
        project_id="p",
        project_state_version=6,
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
                asset_id="video",
                source_storage_key=video_key,
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
                clip_id="music",
                track_id="audio",
                track_kind="audio",
                track_index=2,
                asset_id="music",
                source_storage_key=music_key,
                timeline_start=0,
                duration=4000,
                source_start=0,
                source_duration=4000,
                playback_rate=1.0,
                volume=0.12,
                transition_in={"kind": "fade", "duration": 500},
                transition_out={"kind": "fade", "duration": 500},
                metadata={
                    "_asset_kind": "audio",
                    "_asset_audio_codec": "pcm_s16le",
                    "_transform": {},
                    "music_bed": True,
                    "user_selected_music": True,
                },
            ),
        ],
    )

    output = tmp_path / "music-bed.mp4"
    result = execute(plan, output)
    metadata = probe(output)

    assert output.is_file()
    assert result["audio_source_count"] == 1
    assert metadata["audio_codec"] is not None
    assert metadata["video_codec"] is not None
    assert 3.8 <= float(metadata["duration_sec"]) <= 4.2
