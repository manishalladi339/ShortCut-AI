"""Tests for deterministic music-ducking planning policy."""
from models.ai_plan import CreateAIEditPlanRequest
from models.project_state import AudioDucking, Clip
from services.music_ducking import apply_music_ducking_policy
from services.planner_evaluation import evaluate_plan


def _plan() -> dict:
    return {
        "candidates": [],
        "operations": [
            {
                "id": "music-op",
                "operation": "add_music_bed",
                "payload": {
                    "asset_id": "music",
                    "duration": 5000,
                    "volume": 0.12,
                    "metadata": {
                        "music_bed": True,
                        "user_selected_music": True,
                    },
                },
                "reason": "User-selected music bed",
            }
        ],
    }


def test_policy_attaches_valid_sidechain_configuration():
    plan = _plan()
    body = CreateAIEditPlanRequest(
        music_asset_id="music",
        music_ducking=True,
        music_duck_threshold=0.025,
        music_duck_ratio=10.0,
        music_duck_attack_ms=15.0,
        music_duck_release_ms=250.0,
    )

    apply_music_ducking_policy(plan, body)
    ducking = plan["operations"][0]["payload"]["ducking"]

    assert AudioDucking(**ducking).ratio == 10.0
    assert ducking["threshold"] == 0.025
    assert ducking["attack_ms"] == 15.0
    assert ducking["release_ms"] == 250.0
    assert plan["operations"][0]["payload"]["metadata"]["music_ducking"] is True

    evaluation = evaluate_plan(plan)
    assert evaluation["ducked_music_bed_count"] == 1
    assert evaluation["ducking_valid"] is True


def test_policy_can_explicitly_disable_ducking():
    plan = _plan()
    body = CreateAIEditPlanRequest(
        music_asset_id="music",
        music_ducking=False,
    )

    apply_music_ducking_policy(plan, body)

    assert plan["operations"][0]["payload"]["ducking"] is None
    assert plan["operations"][0]["payload"]["metadata"]["music_ducking"] is False
    assert evaluate_plan(plan)["ducked_music_bed_count"] == 0


def test_clip_rejects_out_of_range_ducking_settings():
    try:
        Clip(
            id="clip",
            asset_id="music",
            timeline_start=0,
            duration=1000,
            source_start=0,
            source_duration=1000,
            ducking={"enabled": True, "ratio": 50.0},
        )
    except Exception:
        return
    raise AssertionError("invalid sidechain ratio should be rejected")
