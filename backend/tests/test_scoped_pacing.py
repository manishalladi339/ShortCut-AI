"""Tests for scoped sequence retiming."""
from services.scoped_pacing import apply_retime_scope, pacing_operations


def _sequence():
    return {
        "id": "seq",
        "name": "Main",
        "width": 1080,
        "height": 1920,
        "timebase": {"numerator": 1000, "denominator": 1},
        "tracks": [
            {
                "id": "video",
                "kind": "video",
                "name": "Video",
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "p1",
                        "asset_id": "a",
                        "timeline_start": 0,
                        "duration": 5000,
                        "source_start": 0,
                        "source_duration": 5000,
                        "playback_rate": 1.0,
                        "metadata": {"ai_plan_id": "plan"},
                    },
                    {
                        "id": "p2",
                        "asset_id": "a",
                        "timeline_start": 5000,
                        "duration": 5000,
                        "source_start": 5000,
                        "source_duration": 5000,
                        "playback_rate": 1.0,
                        "metadata": {"ai_plan_id": "plan"},
                    },
                    {
                        "id": "p3",
                        "asset_id": "a",
                        "timeline_start": 10000,
                        "duration": 5000,
                        "source_start": 10000,
                        "source_duration": 5000,
                        "playback_rate": 1.0,
                        "metadata": {"ai_plan_id": "plan"},
                    },
                ],
            },
            {
                "id": "overlay",
                "kind": "overlay",
                "name": "Overlay",
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "b1",
                        "asset_id": "b",
                        "timeline_start": 2000,
                        "duration": 3000,
                        "source_start": 0,
                        "source_duration": 3000,
                        "playback_rate": 1.0,
                        "metadata": {"ai_plan_id": "plan", "broll": True},
                    },
                    {
                        "id": "b2",
                        "asset_id": "b",
                        "timeline_start": 11000,
                        "duration": 2000,
                        "source_start": 3000,
                        "source_duration": 2000,
                        "playback_rate": 1.0,
                        "metadata": {"ai_plan_id": "plan", "broll": True},
                    },
                ],
            },
            {
                "id": "audio",
                "kind": "audio",
                "name": "Music",
                "locked": False,
                "muted": False,
                "clips": [
                    {
                        "id": "music",
                        "asset_id": "m",
                        "timeline_start": 0,
                        "duration": 15000,
                        "source_start": 0,
                        "source_duration": 15000,
                        "playback_rate": 1.0,
                        "volume": 0.12,
                        "metadata": {"ai_plan_id": "plan", "music_bed": True},
                    }
                ],
            },
        ],
        "captions": [
            {
                "id": "c1",
                "start": 1000,
                "duration": 3000,
                "text": "Intro",
                "style": {"source": "transcript"},
            },
            {
                "id": "c2",
                "start": 11000,
                "duration": 2000,
                "text": "After",
                "style": {"source": "transcript"},
            },
        ],
    }


def test_pacing_planner_defaults_to_conservative_speedup():
    sequence = _sequence()
    intents, operations = pacing_operations(
        instruction="Make the first 10 seconds faster",
        sequence=sequence,
        scope_start=0,
        scope_end=10000,
    )
    assert intents == ["tighten_pacing"]
    assert len(operations) == 1
    payload = operations[0]["payload"]
    assert payload["speed_factor"] == 1.15
    assert payload["scope_start"] == 0
    assert payload["scope_end"] == 10000
    assert payload["removed_duration_ticks"] == 1304
    assert payload["primary_clip_ids"] == ["p1", "p2"]


def test_pacing_planner_accepts_explicit_safe_factor():
    _, operations = pacing_operations(
        instruction="Make this section faster at 1.25x",
        sequence=_sequence(),
        scope_start=0,
        scope_end=10000,
    )
    assert operations[0]["payload"]["speed_factor"] == 1.25
    assert operations[0]["payload"]["retimed_duration_ticks"] == 8000


def test_retime_scope_compresses_story_and_synchronized_content():
    sequence = _sequence()
    _, operations = pacing_operations(
        instruction="Make the first 10 seconds faster at 1.25x",
        sequence=sequence,
        scope_start=0,
        scope_end=10000,
    )
    apply_retime_scope(sequence, operations[0]["payload"])

    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    assert [clip["timeline_start"] for clip in video["clips"]] == [0, 4000, 8000]
    assert [clip["duration"] for clip in video["clips"]] == [4000, 4000, 5000]
    assert [clip["source_duration"] for clip in video["clips"]] == [5000, 5000, 5000]
    assert [clip["playback_rate"] for clip in video["clips"][:2]] == [1.25, 1.25]
    assert video["clips"][2]["playback_rate"] == 1.0

    overlay = next(track for track in sequence["tracks"] if track["id"] == "overlay")
    assert overlay["clips"][0]["timeline_start"] == 1600
    assert overlay["clips"][0]["duration"] == 2400
    assert overlay["clips"][0]["source_duration"] == 2400
    assert overlay["clips"][1]["timeline_start"] == 9000

    music = next(track for track in sequence["tracks"] if track["id"] == "audio")
    assert music["clips"][0]["duration"] == 13000
    assert music["clips"][0]["source_duration"] == 13000

    assert sequence["captions"][0]["start"] == 800
    assert sequence["captions"][0]["duration"] == 2400
    assert sequence["captions"][1]["start"] == 9000


def test_retime_scope_splits_primary_clip_at_scope_boundary():
    sequence = _sequence()
    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    video["clips"] = [
        {
            "id": "long",
            "asset_id": "a",
            "timeline_start": 0,
            "duration": 15000,
            "source_start": 0,
            "source_duration": 15000,
            "playback_rate": 1.0,
            "transition_in": {"kind": "fade", "duration": 500},
            "transition_out": {"kind": "fade", "duration": 500},
            "metadata": {"ai_plan_id": "plan"},
        }
    ]

    _, operations = pacing_operations(
        instruction="Make the first 10 seconds faster at 1.25x",
        sequence=sequence,
        scope_start=0,
        scope_end=10000,
    )
    apply_retime_scope(sequence, operations[0]["payload"])

    clips = video["clips"]
    assert len(clips) == 2
    assert clips[0]["timeline_start"] == 0
    assert clips[0]["duration"] == 8000
    assert clips[0]["source_start"] == 0
    assert clips[0]["source_duration"] == 10000
    assert clips[0]["playback_rate"] == 1.25
    assert clips[0]["transition_in"]["duration"] == 500
    assert clips[0]["transition_out"] is None

    assert clips[1]["timeline_start"] == 8000
    assert clips[1]["duration"] == 5000
    assert clips[1]["source_start"] == 10000
    assert clips[1]["source_duration"] == 5000
    assert clips[1]["playback_rate"] == 1.0
    assert clips[1]["transition_in"] is None
    assert clips[1]["transition_out"]["duration"] == 500


def test_retime_scope_refuses_locked_synchronized_track():
    sequence = _sequence()
    overlay = next(track for track in sequence["tracks"] if track["id"] == "overlay")
    overlay["locked"] = True
    _, operations = pacing_operations(
        instruction="Make the first 10 seconds faster",
        sequence=sequence,
        scope_start=0,
        scope_end=10000,
    )
    try:
        apply_retime_scope(sequence, operations[0]["payload"])
    except ValueError as exc:
        assert "locked" in str(exc)
        assert "lose sync" in str(exc)
    else:
        raise AssertionError("locked synchronized track must block pacing")


def test_retime_scope_refuses_user_authored_overlay_inside_scope():
    sequence = _sequence()
    overlay = next(track for track in sequence["tracks"] if track["id"] == "overlay")
    overlay["clips"][0]["metadata"] = {}
    _, operations = pacing_operations(
        instruction="Make the first 10 seconds faster",
        sequence=sequence,
        scope_start=0,
        scope_end=10000,
    )
    try:
        apply_retime_scope(sequence, operations[0]["payload"])
    except ValueError as exc:
        assert "user-authored" in str(exc)
    else:
        raise AssertionError("user-authored overlap must not be retimed automatically")


def test_pacing_factor_above_quality_cap_is_rejected():
    try:
        pacing_operations(
            instruction="Make the first 10 seconds faster at 1.8x",
            sequence=_sequence(),
            scope_start=0,
            scope_end=10000,
        )
    except ValueError as exc:
        assert "1.05x to 1.50x" in str(exc)
    else:
        raise AssertionError("unsafe pacing factor should be rejected")
