"""Tests for deterministic fade/slide transition rendering helpers."""
from models.render_plan import RenderTransition
from services.render_executor import (
    _transition_kind,
    _transition_position_expressions,
    _transition_seconds,
)


def test_transition_seconds_accepts_directional_slide():
    transition = RenderTransition(kind="slide_left", duration=250)
    value = _transition_seconds(
        transition,
        numerator=1000,
        denominator=1,
        clip_duration_sec=3.0,
    )
    assert value == 0.25
    assert _transition_kind(transition) == "slide_left"


def test_slide_in_from_left_moves_from_off_canvas_to_base_position():
    transition = RenderTransition(kind="slide_left", duration=250)
    x, y = _transition_position_expressions(
        base_x="(W-w)/2",
        base_y="(H-h)/2",
        transition_in=transition,
        transition_out=None,
        transition_in_sec=0.25,
        transition_out_sec=0.0,
        timeline_start=2.0,
        target_duration=4.0,
    )
    assert "-w" in x
    assert "(W-w)/2" in x
    assert "2.25000000" in x
    assert y != ""


def test_slide_out_to_right_uses_canvas_width_as_exit_target():
    transition = RenderTransition(kind="slide_right", duration=400)
    x, _ = _transition_position_expressions(
        base_x="(W-w)/2",
        base_y="(H-h)/2",
        transition_in=None,
        transition_out=transition,
        transition_in_sec=0.0,
        transition_out_sec=0.4,
        timeline_start=1.0,
        target_duration=5.0,
    )
    assert "(W)" in x or "W" in x
    assert "5.60000000" in x


def test_fade_transition_does_not_change_overlay_position_expression():
    fade = RenderTransition(kind="fade", duration=200)
    x, y = _transition_position_expressions(
        base_x="base-x",
        base_y="base-y",
        transition_in=fade,
        transition_out=fade,
        transition_in_sec=0.2,
        transition_out_sec=0.2,
        timeline_start=0.0,
        target_duration=2.0,
    )
    assert x == "base-x"
    assert y == "base-y"
