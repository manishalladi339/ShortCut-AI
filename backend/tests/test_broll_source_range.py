"""Tests for bounded B-roll source ranges."""
from services.broll_planning import bounded_broll_source_range


def test_broll_range_clamps_at_start():
    assert bounded_broll_source_range(
        observation_time_sec=0.2,
        asset_duration_sec=10.0,
        target_duration_ticks=3000,
        ticks_per_second=1000.0,
    ) == (0, 3000)


def test_broll_range_clamps_at_end():
    start, duration = bounded_broll_source_range(
        observation_time_sec=9.8,
        asset_duration_sec=10.0,
        target_duration_ticks=3000,
        ticks_per_second=1000.0,
    )
    assert duration == 3000
    assert start == 7000
    assert start + duration == 10000


def test_broll_range_shortens_to_short_asset():
    assert bounded_broll_source_range(
        observation_time_sec=0.5,
        asset_duration_sec=1.0,
        target_duration_ticks=3000,
        ticks_per_second=1000.0,
    ) == (0, 1000)


def test_broll_range_rejects_unknown_duration():
    assert bounded_broll_source_range(
        observation_time_sec=1.0,
        asset_duration_sec=0.0,
        target_duration_ticks=3000,
        ticks_per_second=1000.0,
    ) is None
