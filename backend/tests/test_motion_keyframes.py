"""Tests for normalized transform keyframes and FFmpeg interpolation helpers."""
import pytest
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


def _keyframes():
    return [
        {
            "at": 0.0,
            "scale": 1.0,
            "position_x": 0.0,
            "position_y": 0.0,
            "easing": "ease_in_out",
        },
        {
            "at": 1.0,
            "scale": 1.08,
            "position_x": 10.0,
            "position_y": -5.0,
            "easing": "ease_in_out",
        },
    ]


def test_project_state_requires_motion_to_span_full_clip_progress():
    valid = ClipTransform(keyframes=_keyframes())
    assert valid.keyframes[0].at == 0.0
    assert valid.keyframes[-1].at == 1.0

    with pytest.raises(ValidationError):
        ClipTransform(
            keyframes=[
                {
                    "at": 0.2,
                    "scale": 1.0,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "easing": "linear",
                },
                {
                    "at": 1.0,
                    "scale": 1.1,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "easing": "linear",
                },
            ]
        )


def test_project_state_rejects_duplicate_keyframe_progress():
    with pytest.raises(ValidationError):
        ClipTransform(
            keyframes=[
                {
                    "at": 0.0,
                    "scale": 1.0,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "easing": "linear",
                },
                {
                    "at": 0.0,
                    "scale": 1.1,
                    "position_x": 0.0,
                    "position_y": 0.0,
                    "easing": "linear",
                },
            ]
        )


def test_easing_expressions_are_bounded_and_deterministic():
    assert _ease_expression("p", "linear") == "clip(p,0,1)"
    assert "3-2*" in _ease_expression("p", "ease_in_out")
    assert "1-(1-" in _ease_expression("p", "ease_out")


def test_keyframe_expression_interpolates_between_two_points():
    expression = _keyframe_expression(
        _keyframes(),
        field="scale",
        progress_expression="p",
        fallback=1.0,
    )
    assert "1.00000000" in expression
    assert "1.08000000" in expression
    assert "lte((p),1.00000000)" in expression


def test_motion_expressions_use_local_scale_and_global_overlay_time():
    scale, x, y = _motion_expressions(
        {"scale": 1.0, "position_x": 0.0, "position_y": 0.0, "keyframes": _keyframes()},
        target_duration=4.0,
        timeline_start=7.0,
    )
    assert "t/4.00000000" in scale
    assert "t-7.00000000" in x
    assert "t-7.00000000" in y


def test_static_transform_keeps_constant_expressions():
    scale, x, y = _motion_expressions(
        {"scale": 1.25, "position_x": 20, "position_y": -30},
        target_duration=4.0,
        timeline_start=0.0,
    )
    assert scale == "1.25000000"
    assert x == "20.00000000"
    assert y == "-30.00000000"



def _motion_state(*, reframe: bool = True):
    metadata = {"ai_plan_id": "plan"}
    if reframe:
        metadata["reframe"] = {
            "strategy": "single_visible_subject",
            "confidence": 0.9,
        }
    return {
        "project_id": "p",
        "user_id": "u",
        "version": 3,
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
                                "volume": 1.0,
                                "transform": {
                                    "scale": 3.2 if reframe else 1.0,
                                    "position_x": -120.0 if reframe else 0.0,
                                    "position_y": 10.0 if reframe else 0.0,
                                    "rotation_deg": 0.0,
                                    "opacity": 1.0,
                                    "keyframes": [],
                                },
                                "metadata": metadata,
                            },
                            {
                                "id": "after",
                                "asset_id": "a",
                                "timeline_start": 10000,
                                "duration": 10000,
                                "source_start": 10000,
                                "source_duration": 10000,
                                "playback_rate": 1.0,
                                "volume": 1.0,
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
                                "volume": 0.0,
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


def test_scoped_push_in_starts_from_existing_smart_reframe():
    state = _motion_state()
    proposal = build_constrained_proposal(
        project_id="p",
        user_id="u",
        state=state,
        instruction="Slowly zoom in on this shot",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    assert proposal["interpreted_intents"] == ["push_in"]
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["operation"] == "set_motion_keyframes"
    keyframes = operation["payload"]["keyframes"]
    assert keyframes[0]["scale"] == 3.2
    assert keyframes[0]["position_x"] == -120.0
    assert keyframes[1]["scale"] == 3.36

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    clip = changed["sequences"][0]["tracks"][0]["clips"][0]
    assert clip["transform"]["scale"] == 3.2
    assert clip["transform"]["keyframes"] == keyframes
    assert clip["timeline_start"] == 0
    assert clip["source_duration"] == 10000


def test_pan_right_uses_camera_direction_and_compensating_zoom():
    proposal = build_constrained_proposal(
        project_id="p",
        user_id="u",
        state=_motion_state(),
        instruction="Pan right",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    keyframes = proposal["operations"][0]["payload"]["keyframes"]
    assert keyframes[1]["position_x"] < keyframes[0]["position_x"]
    assert keyframes[1]["scale"] > keyframes[0]["scale"]


def test_pan_refuses_uncropped_clip_when_edge_coverage_is_unproven():
    with pytest.raises(ValueError, match="no matching timeline items"):
        build_constrained_proposal(
            project_id="p",
            user_id="u",
            state=_motion_state(reframe=False),
            instruction="Pan right",
            scope_start_sec=0,
            scope_end_sec=10,
        )


def test_broll_subtle_motion_targets_overlay_only():
    proposal = build_constrained_proposal(
        project_id="p",
        user_id="u",
        state=_motion_state(),
        instruction="Add subtle motion to the B-roll",
        scope_start_sec=1,
        scope_end_sec=4,
    )
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["component"] == "broll"
    assert operation["payload"]["clip_id"] == "broll"


def test_remove_motion_preserves_static_smart_reframe():
    state = _motion_state()
    clip = state["sequences"][0]["tracks"][0]["clips"][0]
    clip["transform"]["keyframes"] = _keyframes()

    proposal = build_constrained_proposal(
        project_id="p",
        user_id="u",
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


def test_motion_exact_scope_does_not_touch_adjacent_clip():
    proposal = build_constrained_proposal(
        project_id="p",
        user_id="u",
        state=_motion_state(),
        instruction="Push in",
        scope_start_sec=0,
        scope_end_sec=10,
    )
    assert [op["payload"]["clip_id"] for op in proposal["operations"]] == ["primary"]
