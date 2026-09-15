"""Generated-media integration test for dead-air compaction through rendering."""
from __future__ import annotations

import subprocess

from models.render_plan import RenderClip, RenderPlan
from services.dead_air import compact_source_ranges
from services.render_executor import execute
from services.silence_detection import detect_silences
from services.storage import get_storage


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def test_compacted_source_parts_render_without_original_long_pause(tmp_path):
    storage = get_storage()
    source_key = "tests/dead-air/source.mp4"
    source = storage.local_path(source_key)
    source.parent.mkdir(parents=True, exist_ok=True)

    # Six-second red video. Audio is 2s tone + 2s silence + 2s tone.
    _run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=160x90:r=30:d=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=800:duration=2",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=800:duration=2",
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
            str(source),
        ]
    )

    ranges, removed = compact_source_ranges(
        start=0.0,
        end=6.0,
        silences=[{"start": 2.0, "end": 4.0, "duration": 2.0}],
        min_dead_air_sec=0.9,
        retain_pause_sec=0.1,
    )
    assert removed == 1.8

    clips = []
    cursor = 0
    for index, item in enumerate(ranges):
        source_start = round(item["start"] * 1000)
        duration = round((item["end"] - item["start"]) * 1000)
        clips.append(
            RenderClip(
                clip_id=f"part-{index}",
                track_id="main",
                track_kind="video",
                track_index=0,
                asset_id="source",
                source_storage_key=source_key,
                timeline_start=cursor,
                duration=duration,
                source_start=source_start,
                source_duration=duration,
                playback_rate=1.0,
                volume=1.0,
                metadata={
                    "_asset_kind": "video",
                    "_asset_audio_codec": "aac",
                    "_transform": {},
                    "source_part_index": index,
                    "source_part_count": len(ranges),
                },
            )
        )
        cursor += duration

    plan = RenderPlan(
        project_id="p",
        project_state_version=5,
        sequence_id="seq",
        width=320,
        height=180,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=cursor,
        clips=clips,
    )
    output = tmp_path / "compacted.mp4"
    result = execute(plan, output)

    assert result["visual_clip_count"] == 2
    assert 4.1 <= result["duration_sec"] <= 4.3

    rendered_silences = detect_silences(output, duration_sec=result["duration_sec"])
    longest = max(
        (item["duration"] for item in rendered_silences),
        default=0.0,
    )
    assert longest < 0.6
