"""Tests for conservative speaker-turn pacing."""
from services.conversation_pacing import rebalance_speaker_runs


def _item(name: str, speaker: str, role: str = "body") -> dict:
    return {
        "text": name,
        "primary_speaker": speaker,
        "narrative_role": role,
        "reasons": [],
    }


def test_breaks_long_body_run_when_alternate_speaker_is_available():
    ordered = [
        _item("hook", "A", "hook"),
        _item("a1", "A"),
        _item("a2", "A"),
        _item("b1", "B"),
        _item("payoff", "A", "payoff"),
    ]
    result = rebalance_speaker_runs(ordered, max_same_speaker_run=2)
    assert [item["text"] for item in result] == [
        "hook",
        "a1",
        "b1",
        "a2",
        "payoff",
    ]
    assert "speaker-turn pacing reorder" in result[2]["reasons"]


def test_preserves_hook_and_payoff_positions():
    ordered = [
        _item("hook", "A", "hook"),
        _item("a1", "A"),
        _item("payoff", "A", "payoff"),
        _item("b1", "B"),
    ]
    result = rebalance_speaker_runs(ordered, max_same_speaker_run=1)
    assert result[0]["text"] == "hook"
    assert result[2]["text"] == "payoff"


def test_unknown_speaker_does_not_force_reorder():
    ordered = [
        _item("a", "A"),
        {"text": "unknown", "primary_speaker": None, "narrative_role": "body", "reasons": []},
        _item("a2", "A"),
    ]
    assert rebalance_speaker_runs(
        ordered, max_same_speaker_run=1
    ) == ordered
