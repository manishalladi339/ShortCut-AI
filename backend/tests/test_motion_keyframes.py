"""Tests for normalized transform motion keyframes and constrained motion edits."""
from pydantic import ValidationError

from models.project_state import ClipTransform
from services.constrained_editing import (
    apply_constrained_operations,
    build_constrained_proposal,
)
from services.render_executor import (
    _ease_expression,
    _keyframe_expression,
    _motion_expressions,
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
                                "duration": 10000,
                                "source_start": 0,
                                "source_duration": 10000,
                                "playback_rate": 1.0,
                                "transform": {
                                    "scale": 3.2,
                                    "position_x": -120.0,
                                    "position_y": 10.0,
                                    "rotation_deg": 0.0,
                                    "opacity": 1.0,
                                    "keyframes": [],
                                },
                                "metadata": {
                                    "ai_plan_id": "plan",
                                    "reframe": {
                                        "strategy": "single_visible_subject",
                                        "confidence": 0.9,
                                    },
                                },
                            },
                            {
                                "id": "after",
                                "asset_id": "a",
                                "timeline_start": 10000,
                                "duration": 10000,
                                "source_start": 10000,
                                "source_duration": 10000,
                                "playback_rate": 1.0,
                                "transform": {
                                    "scale": 1.0,
                                    "position_x": 0.0,
                                    "position_y": 0.0,
                                    "rotation_deg": 0.0,
                                    "opacity": 1.0,
                                    "keyframes": [],
                                },
                                "metadata": {"ai_plan_id": "plan"},
                            },
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
                                "id": "broll",
                                "asset_id": "b",
                                "timeline_start": 1000,
                                "duration": 3000,
                                "source_start": 0,
                                "source_duration": 3000,
                                "playback_rate": 1.0,
                                "transform": {
                                    "scale": 1.0,
                                    "position_x": 0.0,
                                    "position_y": 0.0,
                                    "rotation_deg": 0.0,
                                    "opacity": 1.0,
                                    "keyframes": [],
                                },
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            }
                        ],
                    },
                ],
                "captions": [],
            }
        ],
    }


def test_clip_transform_requires_normalized_start_and_end_keyframes():
    value = ClipTransform(
        keyframes=[
            {
                "at": 0.0,
                "scale": 1.0,
                "position_x": 0,
                "position_y": 0,
                "easing": "ease_in_out",
            },
            {
                "at": 1.0,
                "scale": 1.1,
                "position_x": -20,
                "position_y": 0,
                "easing": "ease_in_out",
            },
        ]
    )
    assert value.keyframes[1].at == 1.0

    for invalid in (
        [
            {
                "at": 0.2,
                "scale": 1.0,
                "position_x": 0,
                "position_y": 0,
                "easing": "linear",
            },
            {
                "at": 1.0,
                "scale": 1.1,
                "position_x": 0,
                "position_y": 0,
                "easing": "linear",
            },
        ],
        [
            {
                "at": 0.0,
                "scale": 1.0,
                "position_x": 0,
                "position_y": 0,
                "easing": "linear",
            }
        ],
        [
            {
                "at": 0.0,
                "scale": 1.0,
                "position_x": 0,
                "position_y": 0,
                "easing": "linear",
            },
            {
                "at": 0.8,
                "scale": 1.1,
                "position_x": 0,
                "position_y": 0,
                "easing": "linear",
            },
        ],
    ):
        try:
            ClipTransform(keyframes=invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid normalized motion keyframes must fail")


def test_easing_expressions_are_bounded_and_supported():
    linear = _ease_expression("p", "linear")
    ease_in = _ease_expression("p", "ease_in")
    ease_out = _ease_expression("p", "ease_out")
    ease_both = _ease_expression("p", "ease_in_out")

    assert "clip(p,0,1)" in linear
    assert "*" in ease_in
    assert "1-" in ease_out
    assert "3-2" in ease_both


def test_keyframe_expression_builds_piecewise_interpolation():
    expression = _keyframe_expression(
        [
            {
                "at": 0.0,
                "scale": 1.0,
                "position_x": 0.0,
                "position_y": 0.0,
                "easing": "linear",
            },
            {
                "at": 0.5,
                "scale": 1.1,
                "position_x": -20.0,
                "position_y": 0.0,
                "easing": "ease_out",
            },
            {
                "at": 1.0,
                "scale": 1.2,
                "position_x": -40.0,
                "position_y": 0.0,
                "easing": "ease_out",
            },
        ],
        field="scale",
        progress_expression="p",
        fallback=1.0,
    )
    assert "lte((p),0.50000000)" in expression
    assert "lte((p),1.00000000)" in expression
    assert "1.20000000" in expression


def test_motion_expressions_use_local_scale_and_global_overlay_time():
    scale, x, y = _motion_expressions(
        {
            "scale": 1.0,
            "position_x": 0.0,
            "position_y": 0.0,
            "keyframes": [
                {
                    "at": 0.0,
                    "scale": 1.0,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "easing": "ease_in_out",
                },
                {
                    "at": 1.0,
                    "scale": 1.1,
                    "position_x": -50.0,
                    "position_y": 10.0,
                    "easing": "ease_in_out",
                },
            ],
        },
        target_duration=5.0,
        timeline_start=12.0,
    )
    assert "t/5.00000000" in scale
    assert "t-12.00000000" in x
    assert "t-12.00000000" in y


def test_push_in_preserves_smart_reframe_as_starting_frame():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Slowly zoom in on this shot",
        scope_start_sec=0,
        scope_end_sec=10,
    )

    assert proposal["interpreted_intents"] == ["add_motion"]
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["operation"] == "set_clip_motion"
    keyframes = operation["payload"]["keyframes"]
    assert keyframes[0]["scale"] == 3.2
    assert keyframes[0]["position_x"] == -120.0
    assert keyframes[1]["scale"] == 3.36
    assert keyframes[1]["position_x"] == -120.0

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    clip = changed["sequences"][0]["tracks"][0]["clips"][0]
    assert clip["transform"]["scale"] == 3.2
    assert clip["transform"]["position_x"] == -120.0
    assert clip["transform"]["keyframes"] == keyframes
    assert clip["timeline_start"] == 0
    assert clip["source_start"] == 0
    assert clip["source_duration"] == 10000


def test_pan_right_uses_camera_direction_without_changing_timing():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Pan right",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    keyframes = proposal["operations"][0]["payload"]["keyframes"]
    assert keyframes[0]["position_x"] == -120.0
    assert keyframes[1]["position_x"] < -120.0

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    clip = changed["sequences"][0]["tracks"][0]["clips"][0]
    assert clip["duration"] == 10000
    assert clip["source_duration"] == 10000


def test_broll_motion_targets_overlay_only():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Add a subtle zoom in to the B-roll",
        scope_start_sec=1,
        scope_end_sec=4,
    )
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["component"] == "broll"
    assert operation["payload"]["clip_id"] == "broll"


def test_remove_motion_clears_only_keyframes():
    state = _state()
    clip = state["sequences"][0]["tracks"][0]["clips"][0]
    clip["transform"]["keyframes"] = [
        {
            "at": 0.0,
            "scale": 3.2,
            "position_x": -120,
            "position_y": 10,
            "easing": "ease_in_out",
        },
        {
            "at": 1.0,
            "scale": 3.4,
            "position_x": -120,
            "position_y": 10,
            "easing": "ease_in_out",
        },
    ]
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove the motion",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    result = changed["sequences"][0]["tracks"][0]["clips"][0]["transform"]
    assert result["keyframes"] == []
    assert result["scale"] == 3.2
    assert result["position_x"] == -120.0


def test_motion_scope_does_not_touch_adjacent_primary_clip():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Push in",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    assert [op["payload"]["clip_id"] for op in proposal["operations"]] == ["primary"]
