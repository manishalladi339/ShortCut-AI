"""Tests for render-plan and file-signal QA."""
from services.export_qa import analyze_plan_quality, parse_ffmpeg_signal_output
from models.render_plan import RenderCaption, RenderClip, RenderPlan


def _clip(
    clip_id: str,
    *,
    asset_id: str,
    start: int,
    duration: int,
    kind: str = "video",
    track_index: int = 0,
):
    return RenderClip(
        clip_id=clip_id,
        track_id=f"track-{kind}",
        track_kind=kind,
        track_index=track_index,
        asset_id=asset_id,
        source_storage_key=f"source/{asset_id}.mp4",
        timeline_start=start,
        duration=duration,
        source_start=0,
        source_duration=duration,
        playback_rate=1.0,
        volume=1.0,
        metadata={},
    )


def _plan(*, clips=None, captions=None, duration=10000):
    return RenderPlan(
        project_id="project-1",
        project_state_version=4,
        sequence_id="seq",
        width=1080,
        height=1920,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=duration,
        clips=clips or [],
        captions=captions or [],
    )


def test_plan_qa_finds_primary_gap_and_repeated_broll():
    plan = _plan(
        clips=[
            _clip("p1", asset_id="a", start=0, duration=4000),
            _clip("p2", asset_id="a", start=5000, duration=5000),
            _clip("b1", asset_id="b", start=1000, duration=1000, kind="overlay", track_index=1),
            _clip("b2", asset_id="b", start=3500, duration=1000, kind="overlay", track_index=1),
        ]
    )
    issues, checks = analyze_plan_quality(plan)
    codes = [issue["code"] for issue in issues]
    assert "timeline.primary_visual_gap" in codes
    assert "visual.repeated_broll_source" in codes
    assert next(check for check in checks if check["id"] == "timeline_continuity")["status"] == "warning"


def test_plan_qa_flags_caption_reading_rate_and_overlap():
    plan = _plan(
        clips=[_clip("p1", asset_id="a", start=0, duration=10000)],
        captions=[
            RenderCaption(
                id="c1",
                start=0,
                duration=1000,
                text="This caption contains far too many words to read comfortably",
                style={},
            ),
            RenderCaption(
                id="c2",
                start=500,
                duration=1500,
                text="Overlap",
                style={},
            ),
        ],
    )
    issues, _ = analyze_plan_quality(plan)
    codes = [issue["code"] for issue in issues]
    assert "captions.reading_rate" in codes
    assert "captions.overlap" in codes


def test_signal_parser_extracts_black_silence_and_volume():
    stderr = """
[blackdetect @ 0x1] black_start:1.2 black_end:2.1 black_duration:0.9
[silencedetect @ 0x2] silence_start: 4.000
[silencedetect @ 0x2] silence_end: 7.500 | silence_duration: 3.500
[Parsed_volumedetect_1 @ 0x3] mean_volume: -18.2 dB
[Parsed_volumedetect_1 @ 0x3] max_volume: -0.2 dB
"""
    parsed = parse_ffmpeg_signal_output(stderr)
    assert parsed["black_segments"][0]["duration_sec"] == 0.9
    assert parsed["silence_segments"][0]["start_sec"] == 4.0
    assert parsed["silence_segments"][0]["duration_sec"] == 3.5
    assert parsed["mean_volume_db"] == -18.2
    assert parsed["max_volume_db"] == -0.2



def test_export_qa_degrades_signal_analysis_failure_to_warning(monkeypatch, tmp_path):
    from services import export_qa

    plan = _plan(
        clips=[_clip("p1", asset_id="a", start=0, duration=10000)],
    )

    def fail(_path):
        raise RuntimeError("signal analyzer unavailable")

    monkeypatch.setattr(export_qa, "_run_signal_analysis", fail)
    report = export_qa.analyze_export(tmp_path / "render.mp4", plan)

    assert report["status"] == "warnings"
    issue = next(
        item
        for item in report["issues"]
        if item["code"] == "qa.signal_analysis_unavailable"
    )
    assert issue["severity"] == "warning"
    assert report["error_count"] == 0
