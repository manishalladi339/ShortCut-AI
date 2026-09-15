"""Speaker-aware semantic-unit tests."""
from services.semantic_units import build_semantic_units


def test_semantic_units_split_on_speaker_change_when_requested():
    segments = [
        {"start": 0.0, "end": 3.0, "text": "Hello.", "speaker": "A"},
        {"start": 3.0, "end": 6.0, "text": "Hi.", "speaker": "B"},
    ]
    units = build_semantic_units(
        segments=segments,
        scenes=[],
        split_on_speaker=True,
    )
    assert len(units) == 2
    assert units[0]["speakers"] == ["A"]
    assert units[1]["speakers"] == ["B"]
