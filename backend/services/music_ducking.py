"""Planning policy for deterministic speech-responsive music ducking."""
from __future__ import annotations

from models.ai_plan import CreateAIEditPlanRequest


def apply_music_ducking_policy(
    plan: dict,
    body: CreateAIEditPlanRequest,
) -> dict:
    """Attach validated ducking settings to proposed music-bed operations.

    The policy only configures signal processing. It never fabricates speech
    timings: the renderer derives attenuation from the actual program audio.
    """
    for operation in plan.get("operations") or []:
        if operation.get("operation") != "add_music_bed":
            continue

        payload = operation.setdefault("payload", {})
        metadata = payload.setdefault("metadata", {})
        if body.music_ducking:
            ducking = {
                "enabled": True,
                "threshold": body.music_duck_threshold,
                "ratio": body.music_duck_ratio,
                "attack_ms": body.music_duck_attack_ms,
                "release_ms": body.music_duck_release_ms,
                "makeup": 1.0,
            }
            payload["ducking"] = ducking
            metadata.update(
                {
                    "music_ducking": True,
                    "music_duck_threshold": body.music_duck_threshold,
                    "music_duck_ratio": body.music_duck_ratio,
                    "music_duck_attack_ms": body.music_duck_attack_ms,
                    "music_duck_release_ms": body.music_duck_release_ms,
                    "music_ducking_source": "program_audio_sidechain",
                }
            )
            operation["reason"] = (
                f"{operation.get('reason', '').rstrip()} with deterministic "
                "speech-responsive sidechain ducking"
            ).strip()
        else:
            payload["ducking"] = None
            metadata["music_ducking"] = False
            metadata["music_ducking_source"] = "disabled_by_request"

    return plan
