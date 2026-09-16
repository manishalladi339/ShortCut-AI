"""Tests for deterministic caption styling in exported video."""
from models.render_plan import RenderCaption, RenderPlan
from services.caption_rendering import build_ass_document


def _plan(style: dict) -> RenderPlan:
    return RenderPlan(
        project_id="project-1",
        project_state_version=3,
        sequence_id="seq",
        width=1080,
        height=1920,
        timebase_numerator=1000,
        timebase_denominator=1,
        duration_ticks=5000,
        clips=[],
        captions=[
            RenderCaption(
                id="caption-1",
                start=1000,
                duration=2500,
                text="Hello {creator}\nSecond line",
                style=style,
            )
        ],
    )


def test_ass_caption_honors_smaller_lower_minimal_style():
    document = build_ass_document(
        _plan(
            {
                "size_scale": 0.85,
                "vertical_position": "lower",
                "preset": "minimal",
            }
        )
    )

    assert "PlayResX: 1080" in document
    assert "PlayResY: 1920" in document
    assert r"\pos(540,1766)" in document
    assert r"\fs59" in document
    assert r"\bord1" in document
    assert "0:00:01.00,0:00:03.50" in document
    assert "Hello (creator)" in document
    assert r"\NSecond line" in document


def test_ass_caption_defaults_are_deterministic():
    document = build_ass_document(_plan({}))
    assert r"\pos(540,1651)" in document
    assert r"\fs69" in document
    assert r"\bord2" in document


def test_ass_caption_clamps_untrusted_size_scale():
    document = build_ass_document(_plan({"size_scale": 100}))
    assert r"\fs138" in document
