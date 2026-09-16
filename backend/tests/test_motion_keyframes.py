"""Tests for normalized transform keyframes and FFmpeg interpolation helpers."""
import pytest
from pydantic import ValidationError

from models.project_state import ClipTransform
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
