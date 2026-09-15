"""Tests for FFmpeg silencedetect parsing."""
from services.silence_detection import parse_silencedetect_output


def test_parse_multiple_silence_intervals():
    stderr = """
[silencedetect @ abc] silence_start: 1.25
[silencedetect @ abc] silence_end: 2.5 | silence_duration: 1.25
[silencedetect @ abc] silence_start: 7
[silencedetect @ abc] silence_end: 8.1 | silence_duration: 1.1
"""
    assert parse_silencedetect_output(stderr) == [
        {"start": 1.25, "end": 2.5, "duration": 1.25},
        {"start": 7.0, "end": 8.1, "duration": 1.1},
    ]


def test_parse_trailing_silence_uses_media_duration():
    stderr = "[silencedetect @ abc] silence_start: 9.4"
    assert parse_silencedetect_output(stderr, duration_sec=10.0) == [
        {"start": 9.4, "end": 10.0, "duration": 0.6}
    ]


def test_parse_ignores_unpaired_noise():
    assert parse_silencedetect_output("ordinary ffmpeg diagnostic") == []
