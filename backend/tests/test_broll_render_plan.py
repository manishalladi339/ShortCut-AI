"""Render-plan contract for AI-generated B-roll overlays."""
from models.render_plan import RenderClip, RenderPlan


def test_render_plan_preserves_overlay_kind_timing_and_muted_audio():
    plan = RenderPlan(
        project_id="p",
        project_state_version=3,
        sequence_id="seq",
        width=1080,
        height=1920,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=8000,
        clips=[
            RenderClip(
                clip_id="primary",
                track_id="main",
                track_kind="video",
                track_index=0,
                asset_id="talking-head",
                source_storage_key="assets/talking.mp4",
                timeline_start=0,
                duration=8000,
                source_start=12000,
                source_duration=8000,
                playback_rate=1.0,
                volume=1.0,
            ),
            RenderClip(
                clip_id="broll",
                track_id="overlay",
                track_kind="overlay",
                track_index=1,
                asset_id="broll-asset",
                source_storage_key="assets/broll.mp4",
                timeline_start=2000,
                duration=3000,
                source_start=5000,
                source_duration=3000,
                playback_rate=1.0,
                volume=0.0,
                metadata={"broll": True, "replaces_primary_visual": True},
            ),
        ],
    )
    overlay = plan.clips[1]
    assert overlay.track_kind == "overlay"
    assert overlay.timeline_start == 2000
    assert overlay.duration == 3000
    assert overlay.source_start == 5000
    assert overlay.volume == 0.0
    assert overlay.metadata["broll"] is True
