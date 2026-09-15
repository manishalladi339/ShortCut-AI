"""Generated-audio integration test for FFmpeg silence detection."""
from __future__ import annotations

import subprocess

from services.silence_detection import detect_silences


def test_detects_synthetic_mid_clip_silence(tmp_path):
    audio = tmp_path / "tone-silence-tone.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono:d=0.8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=1",
            "-filter_complex",
            "[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]",
            "-map",
            "[out]",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio),
        ],
        check=True,
        capture_output=True,
    )

    silences = detect_silences(audio, duration_sec=2.8)

    assert silences
    middle = max(silences, key=lambda item: item["duration"])
    assert 0.9 <= middle["start"] <= 1.1
    assert 1.7 <= middle["end"] <= 1.9
    assert middle["duration"] >= 0.6
