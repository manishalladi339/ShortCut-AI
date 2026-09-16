"""Tests for scoped visual transition planning and mutation."""
import pytest

from services.constrained_editing import (
    apply_constrained_operations,
    build_constrained_proposal,
)


def _state():
    return {
        "project_id": "project-1",
        "user_id": "user-1",
        "version": 7,
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
                                "duration": 10000,
                                "source_start": 2000,
                                "source_duration": 10000,
                                "playback_rate": 1.0,
                                "volume": 1.0,
                                "transform": {
                                    "scale": 1.2,
                                    "position_x": 0.0,
                                    "position_y": 0.0,
                                    "rotation_deg": 0.0,
                                    "opacity": 1.0,
                                    "keyframes": [],
                                },
                                "metadata": {"ai_plan_id": "plan"},
                            }
                        ],
                    },
                    {
                        "id": "overlay",
                        "kind": "overlay",
                        "name": "B-roll",
                        "locked": False,
                        "muted": False,
                        "clips": [
                            {
                                "id": "broll-ai",
                                "asset_id": "b",
                                "timeline_start": 1000,
                                "duration": 3000,
                                "source_start": 0,
                                "source_duration": 3000,
                                "playback_rate": 1.0,
                                "volume": 0.0,
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            },
                            {
                                "id": "overlay-user",
                                "asset_id": "c",
                                "timeline_start": 5000,
                                "duration": 2000,
                                "source_start": 0,
                                "source_duration": 2000,
                                "playback_rate": 1.0,
                                "volume": 0.0,
                                "metadata": {"user_authored": True},
                            },
                        ],
                    },
                ],
                "captions": [
                    {
                        "id": "cap",
                        "start": 1000,
                        "duration": 2000,
                        "text": "Caption",
                        "style": {},
                    }
                ],
            }
        ],
    }


def test_slide_story_in_from_left_preserves_timeline_and_source_geometry():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Slide this shot in from the left",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    assert proposal["interpreted_intents"] == ["slide_left_in"]
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["operation"] == "set_clip_transition"
    assert operation["component"] == "story"
    assert operation["payload"]["transition_in"]["kind"] == "slide_left"

    before = state["sequences"][0]["tracks"][0]["clips"][0]
    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    after = changed["sequences"][0]["tracks"][0]["clips"][0]
    assert after["timeline_start"] == before["timeline_start"]
    assert after["duration"] == before["duration"]
    assert after["source_start"] == before["source_start"]
    assert after["source_duration"] == before["source_duration"]
    assert after["transition_in"]["kind"] == "slide_left"


def test_fade_story_out_sets_only_exit_transition():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Fade this shot out",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    operation = proposal["operations"][0]
    assert "transition_in" not in operation["payload"]
    assert operation["payload"]["transition_out"]["kind"] == "fade"
    assert operation["payload"]["transition_out"]["duration"] == 250


def test_slow_transition_duration_is_capped_to_half_short_clip():
    state = _state()
    clip = state["sequences"][0]["tracks"][0]["clips"][0]
    clip["duration"] = 500
    clip["source_duration"] = 500
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Smooth fade this shot out",
        scope_start_sec=0,
        scope_end_sec=0.5,
    )
    transition = proposal["operations"][0]["payload"]["transition_out"]
    assert transition["duration"] == 250


def test_fade_broll_targets_only_ai_overlay():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Fade the B-roll out",
        scope_start_sec=0,
        scope_end_sec=8,
    )
    assert proposal["interpreted_intents"] == ["fade_transition"]
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["component"] == "broll"
    assert operation["payload"]["clip_id"] == "broll-ai"


def test_caption_fade_is_not_misread_as_story_transition():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Fade the captions in",
    )
    assert proposal["interpreted_intents"] == ["restyle_captions"]
    assert all(
        operation["operation"] == "update_caption"
        for operation in proposal["operations"]
    )
    assert proposal["operations"][0]["payload"]["style"]["animation"] == "fade"


def test_remove_transition_preserves_other_clip_properties():
    state = _state()
    clip = state["sequences"][0]["tracks"][0]["clips"][0]
    clip["transition_in"] = {"kind": "slide_right", "duration": 250}
    clip["transition_out"] = {"kind": "fade", "duration": 250}

    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove the transition from this shot",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    after = changed["sequences"][0]["tracks"][0]["clips"][0]
    assert after["transition_in"] is None
    assert after["transition_out"] is None
    assert after["duration"] == 10000
    assert after["source_start"] == 2000
    assert after["source_duration"] == 10000
    assert after["transform"]["scale"] == 1.2


def test_slide_requires_direction():
    with pytest.raises(ValueError, match="need a direction"):
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=_state(),
            instruction="Slide this shot",
            scope_start_sec=0,
            scope_end_sec=10,
        )


def test_transition_scope_does_not_mutate_boundary_crossing_clip():
    with pytest.raises(ValueError, match="no matching timeline items"):
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=_state(),
            instruction="Fade this shot out",
            scope_start_sec=0,
            scope_end_sec=5,
        )


def test_transition_apply_refuses_user_authored_broll():
    state = _state()
    operation = {
        "id": "bad",
        "operation": "set_clip_transition",
        "component": "broll",
        "payload": {
            "sequence_id": "seq",
            "track_id": "overlay",
            "clip_id": "overlay-user",
            "transition_out": {"kind": "fade", "duration": 200},
        },
        "reason": "unsafe",
    }
    with pytest.raises(ValueError, match="non-AI B-roll"):
        apply_constrained_operations(state=state, operations=[operation])
