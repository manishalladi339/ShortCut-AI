"""Tests for behavior-derived Creator Memory."""
from datetime import datetime, timezone

from services.creator_memory import (
    creator_allows_broll,
    creator_caption_style,
    derive_creator_memory,
)


def _op(operation_id: str, operation: str, component: str | None = None, **payload):
    item = {
        "id": operation_id,
        "operation": operation,
        "payload": payload,
        "reason": "",
    }
    if component:
        item["component"] = component
    return item


def test_memory_learns_caption_style_and_lower_broll_density():
    plans = []
    for index in range(3):
        plans.append(
            {
                "status": "applied",
                "operations": [
                    _op(f"b{index}", "add_broll_overlay"),
                    _op(f"c{index}", "add_caption"),
                ],
                "applied_operation_ids": [f"c{index}"],
                "skipped_operation_ids": [f"b{index}"],
            }
        )

    proposals = [
        {
            "status": "applied",
            "applied_operation_ids": ["style-1", "remove-b-1"],
            "operations": [
                {
                    **_op(
                        "style-1",
                        "update_caption",
                        "captions",
                        style={
                            "preset": "minimal",
                            "size_scale": 0.85,
                            "vertical_position": "lower",
                        },
                    ),
                    "reason": "Creator restyled captions",
                },
                {
                    **_op("remove-b-1", "remove_clip", "broll"),
                    "reason": "Creator removed B-roll",
                },
            ],
        }
    ]

    memory = derive_creator_memory(
        user_id="user-1",
        plans=plans,
        feedback=[
            {"outcome": "accepted"},
            {"outcome": "modified"},
        ],
        constrained_proposals=proposals,
        now=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    assert memory["optional_operation_preferences"]["broll"]["keep_ratio"] == 0.0
    assert memory["preferences"]["broll_density_multiplier"] == 0.6
    assert memory["preferences"]["caption_style"] == {
        "preset": "minimal",
        "vertical_position": "lower",
        "size_scale": 0.85,
    }
    assert creator_caption_style(memory)["preset"] == "minimal"
    assert creator_allows_broll(memory, 0) is True
    assert creator_allows_broll(memory, 1) is False
    assert "fewer B-roll inserts" in memory["summary"]


def test_memory_requires_evidence_before_adapting():
    memory = derive_creator_memory(
        user_id="user-1",
        plans=[],
        feedback=[],
        constrained_proposals=[],
        now=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    assert memory["evidence_count"] == 0
    assert creator_caption_style(memory) == {}
    assert creator_allows_broll(memory, 1) is True


def test_music_volume_preference_uses_applied_adjustments_only():
    proposal = {
        "status": "applied",
        "applied_operation_ids": ["music-1"],
        "operations": [
            {
                **_op(
                    "music-1",
                    "set_clip_properties",
                    "music",
                    volume=0.06,
                ),
                "reason": "Adjust the music bed from volume 0.120 to 0.060.",
            },
            {
                **_op(
                    "music-2",
                    "set_clip_properties",
                    "music",
                    volume=0.20,
                ),
                "reason": "Adjust the music bed from volume 0.120 to 0.200.",
            },
        ],
    }
    memory = derive_creator_memory(
        user_id="user-1",
        plans=[],
        feedback=[],
        constrained_proposals=[proposal],
        now=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    assert memory["preferences"]["music_volume_multiplier"] == 0.5
