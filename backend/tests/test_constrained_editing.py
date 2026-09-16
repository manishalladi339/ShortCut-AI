"""Tests for localized Create-With-Me planning and safe mutation."""
from services.constrained_editing import (
    apply_constrained_operations,
    build_constrained_proposal,
)


def _state():
    return {
        "project_id": "project-1",
        "user_id": "user-1",
        "version": 4,
        "active_sequence_id": "seq",
        "created_at": "2026-09-16T00:00:00+00:00",
        "updated_at": "2026-09-16T00:00:00+00:00",
        "sequences": [
            {
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
                                "id": "primary",
                                "asset_id": "a",
                                "timeline_start": 0,
                                "duration": 20000,
                                "source_start": 0,
                                "source_duration": 20000,
                                "metadata": {"ai_plan_id": "plan"},
                            }
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
                                "id": "broll-1",
                                "asset_id": "b",
                                "timeline_start": 2000,
                                "duration": 3000,
                                "source_start": 0,
                                "source_duration": 3000,
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            },
                            {
                                "id": "broll-2",
                                "asset_id": "b",
                                "timeline_start": 15000,
                                "duration": 3000,
                                "source_start": 3000,
                                "source_duration": 3000,
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            },
                        ],
                    },
                    {
                        "id": "audio",
                        "kind": "audio",
                        "name": "Audio",
                        "locked": False,
                        "muted": False,
                        "clips": [
                            {
                                "id": "music",
                                "asset_id": "m",
                                "timeline_start": 0,
                                "duration": 20000,
                                "source_start": 0,
                                "source_duration": 20000,
                                "volume": 0.12,
                                "metadata": {"ai_plan_id": "plan", "music_bed": True},
                            }
                        ],
                    },
                ],
                "captions": [
                    {
                        "id": "cap-1",
                        "start": 1000,
                        "duration": 3000,
                        "text": "First caption",
                        "style": {"source": "transcript"},
                    },
                    {
                        "id": "cap-2",
                        "start": 12000,
                        "duration": 3000,
                        "text": "Second caption",
                        "style": {"source": "transcript"},
                    },
                ],
            }
        ],
    }


def test_caption_change_is_scoped_and_preserves_story_clips():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Make the captions smaller in the first 5 seconds",
    )
    assert proposal["interpreted_intents"] == ["restyle_captions"]
    assert proposal["scope_start_sec"] == 0
    assert proposal["scope_end_sec"] == 5
    assert len(proposal["operations"]) == 1
    assert proposal["operations"][0]["payload"]["caption_id"] == "cap-1"

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    sequence = changed["sequences"][0]
    assert sequence["captions"][0]["style"]["size_scale"] == 0.85
    assert "size_scale" not in sequence["captions"][1]["style"]
    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    assert video["clips"][0]["id"] == "primary"
    assert video["clips"][0]["duration"] == 20000


def test_remove_broll_only_removes_overlays_inside_scope():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove B-roll from the intro",
    )
    assert proposal["scope_end_sec"] == 10
    assert len(proposal["operations"]) == 1

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    overlay = next(
        track for track in changed["sequences"][0]["tracks"] if track["id"] == "overlay"
    )
    assert [clip["id"] for clip in overlay["clips"]] == ["broll-2"]


def test_lower_music_keeps_non_music_tracks_untouched():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Lower the music",
    )
    assert proposal["interpreted_intents"] == ["lower_music"]
    assert len(proposal["operations"]) == 1

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    music = next(
        track for track in changed["sequences"][0]["tracks"] if track["id"] == "audio"
    )["clips"][0]
    assert music["volume"] == 0.06
    assert changed["sequences"][0]["tracks"][0]["clips"][0]["id"] == "primary"


def test_unsupported_primary_cut_request_is_rejected():
    try:
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=_state(),
            instruction="Make the first ten seconds faster",
        )
    except ValueError as exc:
        assert "Primary story cuts are preserved" in str(exc)
    else:
        raise AssertionError("unsupported primary-cut request should fail")
