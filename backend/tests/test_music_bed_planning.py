"""Unit coverage for user-selected Create For Me music beds."""
from models.ai_plan import CreateAIEditPlanRequest
from services.transition_planning import bounded_fade_ticks


def test_music_bed_request_defaults_are_conservative():
    body = CreateAIEditPlanRequest()
    assert body.music_asset_id is None
    assert body.music_source_start_sec == 0.0
    assert body.music_volume == 0.12
    assert body.music_fade_sec == 0.75


def test_music_fade_uses_requested_duration_when_safe():
    ticks, metadata = bounded_fade_ticks(
        clip_duration_ticks=10000,
        ticks_per_second=1000.0,
        requested_fade_sec=0.75,
    )
    assert ticks == 750
    assert metadata["strategy"] == "requested"
    assert metadata["planned_fade_sec"] == 0.75


def test_music_fade_is_capped_for_short_output():
    ticks, metadata = bounded_fade_ticks(
        clip_duration_ticks=1000,
        ticks_per_second=1000.0,
        requested_fade_sec=0.75,
    )
    assert ticks == 250
    assert metadata["planned_fade_sec"] == 0.25
    assert metadata["clip_fraction_cap"] == 0.25
