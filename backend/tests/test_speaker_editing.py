"""Tests for speaker-aware planning controls."""
from services.speaker_editing import normalize_speakers, primary_speaker, speaker_allowed


def test_normalizes_unique_speaker_labels():
    assert normalize_speakers({"speakers": ["A", "A", " B ", ""]}) == ["A", "B"]


def test_include_filter_requires_matching_diarized_speaker():
    assert speaker_allowed(["B"], include=["B"])
    assert not speaker_allowed(["A"], include=["B"])
    assert not speaker_allowed([], include=["B"])


def test_exclude_filter_rejects_matching_speaker():
    assert not speaker_allowed(["A"], exclude=["A"])
    assert speaker_allowed(["B"], exclude=["A"])


def test_primary_speaker_only_when_unit_is_single_speaker():
    assert primary_speaker(["A"]) == "A"
    assert primary_speaker(["A", "B"]) is None
    assert primary_speaker([]) is None
