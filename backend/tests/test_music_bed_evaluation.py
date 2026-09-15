"""Planner evaluation coverage for user-selected music beds."""
from services.planner_evaluation import evaluate_plan


def test_music_bed_is_grounded_by_explicit_user_asset_selection():
    plan = {
        "candidates": [],
        "operations": [
            {
                "operation": "add_music_bed",
                "payload": {
                    "asset_id": "music-1",
                    "duration": 4000,
                    "volume": 0.12,
                    "transition_in": {"kind": "fade", "duration": 500},
                    "transition_out": {"kind": "fade", "duration": 500},
                    "metadata": {
                        "music_bed": True,
                        "user_selected_music": True,
                    },
                },
            }
        ],
    }

    result = evaluate_plan(plan)

    assert result["music_bed_count"] == 1
    assert result["all_operations_grounded"] is True
    assert result["transitions_valid"] is True


def test_music_bed_rejects_invalid_fade_contract_in_evaluation():
    plan = {
        "candidates": [],
        "operations": [
            {
                "operation": "add_music_bed",
                "payload": {
                    "asset_id": "music-1",
                    "duration": 1000,
                    "volume": 0.12,
                    "transition_in": {"kind": "fade", "duration": 1500},
                    "metadata": {
                        "music_bed": True,
                        "user_selected_music": True,
                    },
                },
            }
        ],
    }
    assert evaluate_plan(plan)["transitions_valid"] is False
