"""Generated-media integration test for explicit music-source looping."""
from __future__ import annotations

import subprocess
import wave
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


def _short_tone(path: Path) -> None:
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
            "sine=frequency=440:sample_rate=48000:duration=1.25",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def _extract_tail_pcm(rendered: Path, wav_path: Path) -> float:
    _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "3.4",
            "-t",
            "0.4",
            "-i",
            str(rendered),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )
    with wave.open(str(wav_path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    if not raw:
        return 0.0
    samples = [
        int.from_bytes(raw[index : index + 2], "little", signed=True)
        for index in range(0, len(raw) - 1, 2)
    ]
    return sum(abs(value) for value in samples) / max(1, len(samples))


def test_short_music_source_can_fill_longer_output_when_looping_is_explicit(tmp_path):
    storage = get_storage()
    video_key = "tests/music-loop/primary.mp4"
    music_key = "tests/music-loop/music.wav"
    video = storage.local_path(video_key)
    music = storage.local_path(music_key)
    _solid_video(video, 4.0)
    _short_tone(music)

    plan = RenderPlan(
        project_id="p",
        project_state_version=8,
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
                loop_source=True,
                playback_rate=1.0,
                volume=0.25,
                metadata={
                    "_asset_kind": "audio",
                    "_asset_audio_codec": "pcm_s16le",
                    "_transform": {},
                    "music_bed": True,
                    "music_fit_mode": "loop",
                },
            ),
        ],
    )

    output = tmp_path / "looped.mp4"
    result = execute(plan, output)
    metadata = probe(output)
    tail = _extract_tail_pcm(output, tmp_path / "tail.wav")

    assert result["looped_audio_source_count"] == 1
    assert result["audio_source_count"] == 1
    assert 3.8 <= float(metadata["duration_sec"]) <= 4.2
    assert tail > 50.0
