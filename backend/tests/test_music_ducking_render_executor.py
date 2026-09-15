"""Generated-media regression test for speech-responsive music ducking."""
from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

from models.render_plan import RenderClip, RenderPlan
from services.render_executor import execute
from services.storage import get_storage


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True)


def _primary_with_mid_speech(path: Path) -> None:
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
            "color=c=red:s=160x90:r=30:d=4",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=2",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono:d=1",
            "-filter_complex",
            "[1:a][2:a][3:a]concat=n=3:v=0:a=1[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )


def _music(path: Path) -> None:
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
            "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def _extract_pcm(rendered: Path, wav_path: Path) -> None:
    _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
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


def _goertzel_power(samples: list[int], sample_rate: int, frequency: float) -> float:
    if not samples:
        return 0.0
    omega = 2.0 * math.pi * frequency / sample_rate
    coefficient = 2.0 * math.cos(omega)
    previous = 0.0
    previous_two = 0.0
    for sample in samples:
        current = float(sample) + coefficient * previous - previous_two
        previous_two = previous
        previous = current
    power = (
        previous_two * previous_two
        + previous * previous
        - coefficient * previous * previous_two
    )
    return max(0.0, power) / (len(samples) * len(samples))


def _frequency_power(path: Path, start_sec: float, end_sec: float, frequency: float) -> float:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        start = round(start_sec * sample_rate)
        count = round((end_sec - start_sec) * sample_rate)
        handle.setpos(start)
        raw = handle.readframes(count)
    samples = [sample[0] for sample in struct.iter_unpack("<h", raw)]
    return _goertzel_power(samples, sample_rate, frequency)


def test_music_is_attenuated_while_primary_speech_is_present(tmp_path):
    storage = get_storage()
    primary_key = "tests/music-ducking/primary.mp4"
    music_key = "tests/music-ducking/music.wav"
    primary = storage.local_path(primary_key)
    music = storage.local_path(music_key)
    _primary_with_mid_speech(primary)
    _music(music)

    plan = RenderPlan(
        project_id="p",
        project_state_version=7,
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
                    "_asset_audio_codec": "aac",
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
                volume=0.6,
                ducking={
                    "enabled": True,
                    "threshold": 0.02,
                    "ratio": 20.0,
                    "attack_ms": 10.0,
                    "release_ms": 80.0,
                    "makeup": 1.0,
                },
                metadata={
                    "_asset_kind": "audio",
                    "_asset_audio_codec": "pcm_s16le",
                    "_transform": {},
                    "music_bed": True,
                },
            ),
        ],
    )

    output = tmp_path / "ducked.mp4"
    result = execute(plan, output)
    extracted = tmp_path / "ducked.wav"
    _extract_pcm(output, extracted)

    before = _frequency_power(extracted, 0.30, 0.80, 440.0)
    during = _frequency_power(extracted, 1.45, 1.95, 440.0)
    after = _frequency_power(extracted, 3.20, 3.70, 440.0)

    assert result["ducked_audio_source_count"] == 1
    assert before > 0
    assert after > 0
    assert during < before * 0.55
    assert during < after * 0.55
