"""Localized Create-With-Me planning and deterministic mutation.

The planner intentionally supports a narrow set of timeline components first:
captions, AI B-roll overlays, and AI/user-selected music beds. Primary story clips
are preserved until we can guarantee sequence-wide ripple semantics.
"""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from typing import Any

from models.project_state import ProjectStateDocument


def _active_sequence(state: dict) -> dict:
    sequence = next(
        (
            item
            for item in state.get("sequences", [])
            if item.get("id") == state.get("active_sequence_id")
        ),
        None,
    )
    if not sequence:
        raise ValueError("Active sequence is unavailable")
    return sequence


def _ticks_per_second(sequence: dict) -> float:
    timebase = sequence.get("timebase") or {}
    return float(timebase.get("numerator") or 1000) / float(
        timebase.get("denominator") or 1
    )


def _timeline_end_ticks(sequence: dict) -> int:
    ends = [0]
    for track in sequence.get("tracks") or []:
        for clip in track.get("clips") or []:
            ends.append(int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0))
    for cue in sequence.get("captions") or []:
        ends.append(int(cue.get("start") or 0) + int(cue.get("duration") or 0))
    return max(ends)


def _contained(start: int, duration: int, scope_start: int, scope_end: int) -> bool:
    """True only when mutating the whole item cannot leak outside approved scope."""
    end = start + duration
    return start >= scope_start and end <= scope_end


def _derive_scope(
    *,
    instruction: str,
    sequence: dict,
    explicit_start_sec: float | None,
    explicit_end_sec: float | None,
) -> tuple[float, float]:
    tps = _ticks_per_second(sequence)
    total_sec = max(0.1, _timeline_end_ticks(sequence) / tps)
    lowered = instruction.lower()

    if explicit_start_sec is not None or explicit_end_sec is not None:
        start = min(max(0.0, float(explicit_start_sec or 0.0)), max(0.0, total_sec - 0.001))
        requested_end = float(explicit_end_sec if explicit_end_sec is not None else total_sec)
        end = min(max(start + 0.001, requested_end), total_sec)
        return start, end

    first_match = re.search(
        r"(?:first|opening|intro(?:duction)?)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds?)",
        lowered,
    )
    if first_match:
        return 0.0, min(total_sec, float(first_match.group(1)))

    if any(term in lowered for term in ("intro", "opening", "beginning")):
        return 0.0, min(total_sec, 10.0)

    last_match = re.search(
        r"(?:last|final|ending)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|secs|seconds?)",
        lowered,
    )
    if last_match:
        length = float(last_match.group(1))
        return max(0.0, total_sec - length), total_sec

    if any(term in lowered for term in ("ending", "outro", "at the end")):
        return max(0.0, total_sec - 10.0), total_sec

    return 0.0, total_sec


def _operation(
    *,
    operation: str,
    component: str,
    payload: dict,
    reason: str,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "operation": operation,
        "component": component,
        "payload": payload,
        "reason": reason,
    }


def _caption_operations(
    *,
    instruction: str,
    sequence: dict,
    scope_start: int,
    scope_end: int,
) -> tuple[list[str], list[dict]]:
    lowered = instruction.lower()
    mentions = any(term in lowered for term in ("caption", "captions", "subtitle", "subtitles"))
    if not mentions:
        return [], []

    captions = [
        cue
        for cue in sequence.get("captions") or []
        if _contained(
            int(cue.get("start") or 0),
            int(cue.get("duration") or 0),
            scope_start,
            scope_end,
        )
    ]
    operations: list[dict] = []
    intents: list[str] = []

    remove = any(
        term in lowered
        for term in (
            "remove caption",
            "remove subtitle",
            "delete caption",
            "delete subtitle",
            "hide caption",
            "hide subtitle",
            "no caption",
            "no subtitle",
        )
    )
    if remove:
        intents.append("remove_captions")
        for cue in captions:
            operations.append(
                _operation(
                    operation="remove_caption",
                    component="captions",
                    payload={
                        "sequence_id": sequence["id"],
                        "caption_id": cue["id"],
                    },
                    reason="Caption is fully contained in the requested edit scope.",
                )
            )
        return intents, operations

    style_patch: dict[str, Any] = {}
    style_reasons: list[str] = []
    if any(term in lowered for term in ("minimal", "simpler", "simple captions", "simple subtitles")):
        style_patch["preset"] = "minimal"
        style_reasons.append("use a minimal caption preset")
    if any(term in lowered for term in ("smaller", "reduce caption", "reduce subtitle", "shrink")):
        style_patch["size_scale"] = 0.85
        style_reasons.append("reduce caption size")
    if any(term in lowered for term in ("larger", "bigger", "increase caption", "increase subtitle")):
        style_patch["size_scale"] = 1.15
        style_reasons.append("increase caption size")
    if any(term in lowered for term in ("move captions lower", "move subtitles lower", "captions lower", "subtitles lower", "lower on screen")):
        style_patch["vertical_position"] = "lower"
        style_reasons.append("move captions lower")
    if any(term in lowered for term in ("move captions higher", "move subtitles higher", "captions higher", "subtitles higher", "higher on screen")):
        style_patch["vertical_position"] = "higher"
        style_reasons.append("move captions higher")

    if style_patch:
        intents.append("restyle_captions")
        for cue in captions:
            operations.append(
                _operation(
                    operation="update_caption",
                    component="captions",
                    payload={
                        "sequence_id": sequence["id"],
                        "caption_id": cue["id"],
                        "style": style_patch,
                    },
                    reason="; ".join(style_reasons).capitalize() + " within the requested scope.",
                )
            )
    return intents, operations


def _broll_operations(
    *,
    instruction: str,
    sequence: dict,
    scope_start: int,
    scope_end: int,
) -> tuple[list[str], list[dict]]:
    lowered = instruction.lower()
    mentions_broll = any(term in lowered for term in ("b-roll", "broll", "b roll", "overlay"))
    removes = any(term in lowered for term in ("remove", "delete", "hide", "clear"))
    if not (mentions_broll and removes):
        return [], []

    operations: list[dict] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "overlay" or track.get("locked"):
            continue
        for clip in track.get("clips") or []:
            if not _contained(
                int(clip.get("timeline_start") or 0),
                int(clip.get("duration") or 0),
                scope_start,
                scope_end,
            ):
                continue
            metadata = clip.get("metadata") or {}
            if metadata.get("broll") or metadata.get("ai_plan_id"):
                operations.append(
                    _operation(
                        operation="remove_clip",
                        component="broll",
                        payload={
                            "sequence_id": sequence["id"],
                            "track_id": track["id"],
                            "clip_id": clip["id"],
                        },
                        reason="AI B-roll overlaps the requested edit scope.",
                    )
                )
    return ["remove_broll"], operations


def _music_operations(
    *,
    instruction: str,
    sequence: dict,
    scope_start: int,
    scope_end: int,
) -> tuple[list[str], list[dict]]:
    lowered = instruction.lower()
    if not any(term in lowered for term in ("music", "music bed", "background audio")):
        return [], []

    mode = None
    if any(term in lowered for term in ("remove music", "delete music", "no music")):
        mode = "remove_music"
    elif any(term in lowered for term in ("mute music", "silence music")):
        mode = "mute_music"
    elif any(term in lowered for term in ("lower music", "quieter music", "reduce music", "turn down music")):
        mode = "lower_music"
    elif any(term in lowered for term in ("raise music", "louder music", "increase music", "turn up music")):
        mode = "raise_music"
    if mode is None:
        return [], []

    operations: list[dict] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "audio" or track.get("locked"):
            continue
        for clip in track.get("clips") or []:
            metadata = clip.get("metadata") or {}
            if not metadata.get("music_bed"):
                continue
            if not _contained(
                int(clip.get("timeline_start") or 0),
                int(clip.get("duration") or 0),
                scope_start,
                scope_end,
            ):
                continue
            payload = {
                "sequence_id": sequence["id"],
                "track_id": track["id"],
                "clip_id": clip["id"],
            }
            if mode == "remove_music":
                operations.append(
                    _operation(
                        operation="remove_clip",
                        component="music",
                        payload=payload,
                        reason="Music bed overlaps the requested edit scope.",
                    )
                )
            else:
                current = float(clip.get("volume", 1.0))
                if mode == "mute_music":
                    volume = 0.0
                elif mode == "lower_music":
                    volume = max(0.0, round(current * 0.5, 4))
                else:
                    volume = min(4.0, round(current * 1.25, 4))
                operations.append(
                    _operation(
                        operation="set_clip_properties",
                        component="music",
                        payload={**payload, "volume": volume},
                        reason=f"Adjust the music bed from volume {current:.3f} to {volume:.3f}.",
                    )
                )
    return [mode], operations


def build_constrained_proposal(
    *,
    project_id: str,
    user_id: str,
    state: dict,
    instruction: str,
    scope_start_sec: float | None = None,
    scope_end_sec: float | None = None,
) -> dict:
    sequence = _active_sequence(state)
    tps = _ticks_per_second(sequence)
    start_sec, end_sec = _derive_scope(
        instruction=instruction,
        sequence=sequence,
        explicit_start_sec=scope_start_sec,
        explicit_end_sec=scope_end_sec,
    )
    scope_start = round(start_sec * tps)
    scope_end = max(scope_start + 1, round(end_sec * tps))

    intents: list[str] = []
    operations: list[dict] = []
    for planner in (_caption_operations, _broll_operations, _music_operations):
        next_intents, next_operations = planner(
            instruction=instruction,
            sequence=sequence,
            scope_start=scope_start,
            scope_end=scope_end,
        )
        intents.extend(next_intents)
        operations.extend(next_operations)

    if not intents:
        raise ValueError(
            "This first constrained editor supports caption restyling/removal, "
            "AI B-roll removal, and music volume/removal. Primary story cuts are "
            "preserved until sequence-wide ripple editing is available."
        )
    if not operations:
        raise ValueError(
            "The instruction was understood, but there are no matching timeline "
            "items inside the requested scope."
        )

    touched = sorted({operation["component"] for operation in operations})
    preserved = [
        component
        for component in ("primary story clips", "captions", "B-roll", "music")
        if component.lower().replace("-", "") not in {
            value.lower().replace("-", "") for value in touched
        }
    ]
    preserve_rules = [
        f"Preserve all timeline content outside {start_sec:.2f}s–{end_sec:.2f}s.",
        "Do not regenerate or reorder primary story clips.",
    ]
    if preserved:
        preserve_rules.append("Preserve untouched components: " + ", ".join(preserved) + ".")

    return {
        "project_id": project_id,
        "user_id": user_id,
        "project_state_version": int(state["version"]),
        "status": "proposed",
        "instruction": instruction.strip(),
        "interpreted_intents": intents,
        "scope_start_sec": round(start_sec, 3),
        "scope_end_sec": round(end_sec, 3),
        "preserve_rules": preserve_rules,
        "summary": (
            f"Proposed {len(operations)} localized change"
            f"{'' if len(operations) == 1 else 's'} to "
            + ", ".join(touched)
            + f" between {start_sec:.2f}s and {end_sec:.2f}s."
        ),
        "operations": operations,
    }


def apply_constrained_operations(
    *,
    state: dict,
    operations: list[dict],
) -> dict:
    """Apply only the restricted proposal operation set to an in-memory state."""
    candidate = deepcopy(state)
    sequence_by_id = {
        sequence["id"]: sequence for sequence in candidate.get("sequences") or []
    }

    for operation in operations:
        payload = operation.get("payload") or {}
        sequence = sequence_by_id.get(str(payload.get("sequence_id") or ""))
        if not sequence:
            raise ValueError("Proposal target sequence no longer exists")

        op = operation.get("operation")
        component = operation.get("component")
        if op in {"update_caption", "remove_caption"}:
            if component != "captions":
                raise ValueError("Caption operation has invalid component")
            caption_id = str(payload.get("caption_id") or "")
            cue = next(
                (
                    item
                    for item in sequence.get("captions") or []
                    if item.get("id") == caption_id
                ),
                None,
            )
            if not cue:
                raise ValueError("Proposal target caption no longer exists")
            if op == "remove_caption":
                sequence["captions"] = [
                    item
                    for item in sequence.get("captions") or []
                    if item.get("id") != caption_id
                ]
            else:
                style = payload.get("style") or {}
                cue["style"] = {**(cue.get("style") or {}), **style}
            continue

        if op not in {"remove_clip", "set_clip_properties"}:
            raise ValueError("Proposal contains unsupported mutation")

        track = next(
            (
                item
                for item in sequence.get("tracks") or []
                if item.get("id") == payload.get("track_id")
            ),
            None,
        )
        if not track or track.get("locked"):
            raise ValueError("Proposal target track is unavailable or locked")

        expected_kind = "overlay" if component == "broll" else "audio"
        if track.get("kind") != expected_kind:
            raise ValueError("Proposal cannot mutate that track kind")

        clip_id = str(payload.get("clip_id") or "")
        clip = next(
            (
                item
                for item in track.get("clips") or []
                if item.get("id") == clip_id
            ),
            None,
        )
        if not clip:
            raise ValueError("Proposal target clip no longer exists")

        metadata = clip.get("metadata") or {}
        if component == "broll" and not (metadata.get("broll") or metadata.get("ai_plan_id")):
            raise ValueError("Proposal cannot remove a non-AI overlay")
        if component == "music" and not metadata.get("music_bed"):
            raise ValueError("Proposal cannot mutate non-music audio")

        if op == "remove_clip":
            track["clips"] = [
                item for item in track.get("clips") or [] if item.get("id") != clip_id
            ]
        else:
            if set(payload) - {"sequence_id", "track_id", "clip_id", "volume"}:
                raise ValueError("Music proposal contains unsupported properties")
            if "volume" in payload:
                clip["volume"] = float(payload["volume"])

    # Validate the complete resulting state before persistence.
    return ProjectStateDocument(**candidate).model_dump()
