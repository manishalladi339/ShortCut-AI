"""Deterministic semantic-unit tests."""
from services.semantic_units import build_semantic_units


def test_semantic_units_preserve_transcript_text_and_timing():
    segments = [
        {"start": 0.0, "end": 4.0, "text": "First idea."},
        {"start": 4.0, "end": 9.0, "text": "Second idea."},
        {"start": 31.0, "end": 36.0, "text": "Later idea."},
    ]
    units = build_semantic_units(segments=segments, scenes=[])
    assert len(units) == 2
    assert units[0]["text"] == "First idea. Second idea."
    assert units[0]["start"] == 0.0
    assert units[0]["end"] == 9.0
    assert units[1]["text"] == "Later idea."


def test_scene_boundary_can_start_new_unit():
    segments = [
        {"start": 0.0, "end": 3.0, "text": "Before cut."},
        {"start": 5.0, "end": 8.0, "text": "After cut."},
    ]
    scenes = [
        {"start": 0.0, "end": 5.0, "score": None},
        {"start": 5.0, "end": 10.0, "score": 0.8},
    ]
    units = build_semantic_units(segments=segments, scenes=scenes)
    assert [item["text"] for item in units] == ["Before cut.", "After cut."]
