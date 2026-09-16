"""Localized Create-With-Me planning and deterministic mutation.

The planner supports localized caption/B-roll/music edits plus a conservative
sequence-wide speaker-removal operation. Story edits are applied atomically with
global ripple semantics so synchronized timeline content cannot silently drift.
"""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from typing import Any

from models.project_state import ProjectStateDocument
from services.scoped_pacing import apply_retime_scope, pacing_operations


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


_NUMBER_WORDS = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "thirteen": 13.0,
    "fourteen": 14.0,
    "fifteen": 15.0,
    "sixteen": 16.0,
    "seventeen": 17.0,
    "eighteen": 18.0,
    "nineteen": 19.0,
    "twenty": 20.0,
}


def _duration_token_value(token: str) -> float:
    lowered = token.strip().lower()
    if lowered in _NUMBER_WORDS:
        return _NUMBER_WORDS[lowered]
    return float(lowered)


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
        r"(?:first|opening|intro(?:duction)?)\s+"
        r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
        r"nineteen|twenty)\s*(?:s|sec|secs|seconds?)",
        lowered,
    )
    if first_match:
        return 0.0, min(total_sec, _duration_token_value(first_match.group(1)))

    if any(term in lowered for term in ("intro", "opening", "beginning")):
        return 0.0, min(total_sec, 10.0)

    last_match = re.search(
        r"(?:last|final|ending)\s+"
        r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
        r"nineteen|twenty)\s*(?:s|sec|secs|seconds?)",
        lowered,
    )
    if last_match:
        length = _duration_token_value(last_match.group(1))
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


def _merge_tick_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _deleted_before(tick: int, intervals: list[tuple[int, int]]) -> int:
    deleted = 0
    for start, end in intervals:
        if tick <= start:
            break
        deleted += max(0, min(tick, end) - start)
    return deleted


def _deleted_overlap(
    start: int,
    end: int,
    intervals: list[tuple[int, int]],
) -> int:
    return sum(
        max(0, min(end, removed_end) - max(start, removed_start))
        for removed_start, removed_end in intervals
    )


def _available_primary_speakers(sequence: dict) -> list[str]:
    return sorted(
        {
            str((clip.get("metadata") or {}).get("primary_speaker"))
            for track in (sequence.get("tracks") or [])
            if track.get("kind") == "video"
            for clip in (track.get("clips") or [])
            if (clip.get("metadata") or {}).get("primary_speaker")
        }
    )


def _resolve_speaker_target(instruction: str, available: list[str]) -> str | None:
    lowered = instruction.lower()
    normalized = lowered.replace("-", "_").replace(" ", "_")

    for speaker in available:
        value = speaker.lower()
        if value in lowered or value in normalized:
            return speaker

    letter = re.search(r"\bspeaker\s+([a-z])\b", lowered)
    if letter:
        candidate = f"speaker_{ord(letter.group(1)) - ord('a')}"
        return next(
            (speaker for speaker in available if speaker.lower() == candidate),
            None,
        )

    number = re.search(r"\bspeaker[_\s-]?(\d+)\b", lowered)
    if number:
        candidate = f"speaker_{number.group(1)}"
        return next(
            (speaker for speaker in available if speaker.lower() == candidate),
            None,
        )
    return None


def _speaker_removal_operations(
    *,
    instruction: str,
    sequence: dict,
    scope_start: int,
    scope_end: int,
) -> tuple[list[str], list[dict]]:
    lowered = instruction.lower()
    wants_removal = bool(
        re.search(r"\b(?:remove|delete|cut)\s+(?:out\s+)?(?:all\s+of\s+)?speaker", lowered)
    )
    if not wants_removal:
        return [], []

    available = _available_primary_speakers(sequence)
    target = _resolve_speaker_target(instruction, available)
    if not target:
        names = ", ".join(available) if available else "none"
        raise ValueError(
            "Could not resolve the requested speaker from diarized primary clips. "
            f"Available speaker labels: {names}."
        )

    matching: list[dict] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "video":
            continue
        if track.get("locked"):
            raise ValueError("Primary video track is locked; speaker removal was not proposed.")
        for clip in track.get("clips") or []:
            metadata = clip.get("metadata") or {}
            if metadata.get("primary_speaker") != target:
                continue
            if not _contained(
                int(clip.get("timeline_start") or 0),
                int(clip.get("duration") or 0),
                scope_start,
                scope_end,
            ):
                continue
            matching.append(clip)

    if not matching:
        return [f"remove_{target}"], []

    intervals = _merge_tick_intervals(
        [
            (
                int(clip["timeline_start"]),
                int(clip["timeline_start"]) + int(clip["duration"]),
            )
            for clip in matching
        ]
    )
    total_removed = sum(end - start for start, end in intervals)
    tps = _ticks_per_second(sequence)
    operation = _operation(
        operation="remove_speaker_ripple",
        component="story",
        payload={
            "sequence_id": sequence["id"],
            "speaker": target,
            "clip_ids": [clip["id"] for clip in matching],
            "removed_intervals": [
                {"start": start, "end": end} for start, end in intervals
            ],
            "removed_duration_ticks": total_removed,
        },
        reason=(
            f"Remove {len(matching)} diarized primary clip"
            f"{'' if len(matching) == 1 else 's'} for {target} and ripple "
            f"{total_removed / tps:.2f}s out of the complete sequence."
        ),
    )
    return [f"remove_{target}"], [operation]


def _apply_speaker_ripple(sequence: dict, payload: dict) -> None:
    target = str(payload.get("speaker") or "")
    selected_ids = {str(value) for value in (payload.get("clip_ids") or [])}
    if not target or not selected_ids:
        raise ValueError("Speaker-removal proposal is missing its grounded clip selection")

    selected: list[dict] = []
    for track in sequence.get("tracks") or []:
        if track.get("kind") != "video":
            continue
        for clip in track.get("clips") or []:
            if clip.get("id") not in selected_ids:
                continue
            if (clip.get("metadata") or {}).get("primary_speaker") != target:
                raise ValueError("Speaker-removal target no longer matches the proposal")
            selected.append(clip)

    if {clip.get("id") for clip in selected} != selected_ids:
        raise ValueError("One or more speaker-removal clips no longer exist")

    intervals = _merge_tick_intervals(
        [
            (
                int(clip["timeline_start"]),
                int(clip["timeline_start"]) + int(clip["duration"]),
            )
            for clip in selected
        ]
    )
    if not intervals:
        raise ValueError("Speaker-removal proposal has no valid timeline intervals")

    earliest = intervals[0][0]
    for track in sequence.get("tracks") or []:
        clips = track.get("clips") or []
        if track.get("locked") and any(
            int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0)
            > earliest
            for clip in clips
        ):
            raise ValueError(
                f"Track '{track.get('name') or track.get('id')}' is locked and would lose sync"
            )

        next_clips: list[dict] = []
        for clip in clips:
            clip_id = str(clip.get("id") or "")
            start = int(clip.get("timeline_start") or 0)
            duration = int(clip.get("duration") or 0)
            end = start + duration

            if track.get("kind") == "video" and clip_id in selected_ids:
                continue

            overlap = _deleted_overlap(start, end, intervals)
            if track.get("kind") == "video" and overlap > 0:
                raise ValueError(
                    "Another primary video clip overlaps the removed speaker range; "
                    "ShortCut refused to create an ambiguous ripple edit"
                )

            shifted = deepcopy(clip)
            new_start = start - _deleted_before(start, intervals)
            new_end = end - _deleted_before(end, intervals)
            new_duration = max(0, new_end - new_start)

            if overlap > 0:
                metadata = clip.get("metadata") or {}
                kind = track.get("kind")
                safe_ai_overlay = kind == "overlay" and bool(
                    metadata.get("broll") or metadata.get("ai_plan_id")
                )
                safe_music = kind == "audio" and bool(metadata.get("music_bed"))
                if not (safe_ai_overlay or safe_music):
                    raise ValueError(
                        "A user-authored or non-music clip overlaps the speaker range; "
                        "ShortCut refused to truncate it automatically"
                    )
                if new_duration <= 0:
                    continue

                ratio = new_duration / max(1, duration)
                shifted["duration"] = new_duration
                shifted["source_duration"] = max(
                    1,
                    round(int(clip.get("source_duration") or duration) * ratio),
                )
                shifted["transition_in"] = None
                shifted["transition_out"] = None
                shifted["metadata"] = {
                    **metadata,
                    "ripple_trimmed": True,
                    "ripple_removed_speaker": target,
                }

            shifted["timeline_start"] = new_start
            next_clips.append(shifted)

        track["clips"] = next_clips

    next_captions: list[dict] = []
    for cue in sequence.get("captions") or []:
        start = int(cue.get("start") or 0)
        duration = int(cue.get("duration") or 0)
        end = start + duration
        overlap = _deleted_overlap(start, end, intervals)
        if overlap >= duration and duration > 0:
            style = cue.get("style") or {}
            if style.get("source") == "transcript" or style.get("ai_plan_id"):
                continue
            raise ValueError(
                "A user-authored caption is fully inside the removed speaker range"
            )
        if overlap > 0:
            raise ValueError(
                "A caption crosses the speaker-removal boundary; "
                "ShortCut refused to truncate its text automatically"
            )

        shifted = deepcopy(cue)
        shifted["start"] = start - _deleted_before(start, intervals)
        next_captions.append(shifted)

    sequence["captions"] = next_captions


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

    caption_subject = r"(?:caption|captions|subtitle|subtitles)"
    remove = bool(
        re.search(
            rf"\b(?:remove|delete|hide)\s+(?:the\s+)?(?:all\s+)?{caption_subject}\b",
            lowered,
        )
        or re.search(rf"\bno\s+{caption_subject}\b", lowered)
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
    if re.search(
        rf"\b(?:minimal|simpler|simple)\s+(?:the\s+)?{caption_subject}\b|"
        rf"\b{caption_subject}\s+(?:more\s+)?(?:minimal|simpler|simple)\b",
        lowered,
    ):
        style_patch["preset"] = "minimal"
        style_reasons.append("use a minimal caption preset")
    if re.search(
        rf"\b(?:make\s+)?(?:the\s+)?{caption_subject}\s+(?:a\s+)?(?:bit\s+)?smaller\b|"
        rf"\b(?:smaller|shrink|reduce)\s+(?:the\s+)?{caption_subject}\b",
        lowered,
    ):
        style_patch["size_scale"] = 0.85
        style_reasons.append("reduce caption size")
    if re.search(
        rf"\b(?:make\s+)?(?:the\s+)?{caption_subject}\s+(?:a\s+)?(?:bit\s+)?(?:larger|bigger)\b|"
        rf"\b(?:larger|bigger|increase)\s+(?:the\s+)?{caption_subject}\b",
        lowered,
    ):
        style_patch["size_scale"] = 1.15
        style_reasons.append("increase caption size")
    if re.search(
        rf"\b(?:move\s+)?(?:the\s+)?{caption_subject}\s+lower\b|"
        rf"\b{caption_subject}\s+lower\s+on\s+screen\b",
        lowered,
    ):
        style_patch["vertical_position"] = "lower"
        style_reasons.append("move captions lower")
    if re.search(
        rf"\b(?:move\s+)?(?:the\s+)?{caption_subject}\s+higher\b|"
        rf"\b{caption_subject}\s+higher\s+on\s+screen\b",
        lowered,
    ):
        style_patch["vertical_position"] = "higher"
        style_reasons.append("move captions higher")

    if re.search(
        rf"\b(?:social|bold|punchy)\s+{caption_subject}\b|"
        rf"\b{caption_subject}\s+(?:more\s+)?(?:social|bold|punchy)\b",
        lowered,
    ):
        style_patch["preset"] = "social"
        style_reasons.append("use a bold social caption preset")

    animation: str | None = None
    if (
        re.search(
            rf"\b(?:remove|disable|turn\s+off)\s+(?:the\s+)?(?:{caption_subject}\s+)?animation\b",
            lowered,
        )
        or re.search(rf"\bstatic\s+{caption_subject}\b", lowered)
    ):
        animation = "none"
        style_reasons.append("disable caption animation")
    elif (
        re.search(
            rf"\b(?:make\s+)?(?:the\s+)?{caption_subject}\s+(?:pop|bounce|punch)\b",
            lowered,
        )
        or re.search(rf"\b(?:pop|bouncy|punchy)\s+{caption_subject}\b", lowered)
        or re.search(rf"\banimated\s+{caption_subject}\b", lowered)
    ):
        animation = "pop"
        style_reasons.append("use pop caption animation")
    elif (
        re.search(
            rf"\b(?:slide|move)\s+(?:the\s+)?{caption_subject}\s+up\b",
            lowered,
        )
        or re.search(rf"\b{caption_subject}\s+(?:slide|rise)\s+up\b", lowered)
    ):
        animation = "slide_up"
        style_reasons.append("use slide-up caption animation")
    elif (
        re.search(
            rf"\bfade\s+(?:the\s+)?{caption_subject}\s+in\b",
            lowered,
        )
        or re.search(rf"\b{caption_subject}\s+(?:fade|fade\s+in)\b", lowered)
    ):
        animation = "fade"
        style_reasons.append("use fade caption animation")

    if animation is not None:
        style_patch["animation"] = animation

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
    removes = bool(
        re.search(
            r"\b(?:remove|delete|hide|clear)\s+(?:the\s+)?(?:all\s+)?(?:b-roll|broll|b\s+roll|overlays?)\b",
            lowered,
        )
    )
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

    music_subject = r"(?:background\s+)?music(?:\s+bed)?"
    mode = None
    if re.search(rf"\b(?:remove|delete)\s+(?:the\s+)?{music_subject}\b", lowered) or re.search(
        rf"\bno\s+{music_subject}\b", lowered
    ):
        mode = "remove_music"
    elif re.search(rf"\b(?:mute|silence)\s+(?:the\s+)?{music_subject}\b", lowered):
        mode = "mute_music"
    elif (
        re.search(rf"\b(?:lower|reduce|decrease)\s+(?:the\s+)?{music_subject}\b", lowered)
        or re.search(rf"\bturn\s+down\s+(?:the\s+)?{music_subject}\b", lowered)
        or re.search(rf"\bmake\s+(?:the\s+)?{music_subject}\s+quieter\b", lowered)
    ):
        mode = "lower_music"
    elif (
        re.search(rf"\b(?:raise|increase)\s+(?:the\s+)?{music_subject}\b", lowered)
        or re.search(rf"\bturn\s+up\s+(?:the\s+)?{music_subject}\b", lowered)
        or re.search(rf"\bmake\s+(?:the\s+)?{music_subject}\s+louder\b", lowered)
    ):
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
    additional_intents: list[str] | None = None,
    additional_operations: list[dict] | None = None,
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
    for planner in (
        pacing_operations,
        _speaker_removal_operations,
        _caption_operations,
        _broll_operations,
        _music_operations,
    ):
        next_intents, next_operations = planner(
            instruction=instruction,
            sequence=sequence,
            scope_start=scope_start,
            scope_end=scope_end,
        )
        intents.extend(next_intents)
        operations.extend(next_operations)

    intents.extend(additional_intents or [])
    operations.extend(additional_operations or [])

    if not intents:
        raise ValueError(
            "Create With Me currently supports scoped pacing changes, diarized "
            "speaker removal with sequence-wide ripple, semantic B-roll "
            "replacement/removal, caption restyling/removal, and music "
            "volume/removal."
        )

    structural = [
        operation
        for operation in operations
        if operation.get("operation") in {"retime_scope", "remove_speaker_ripple"}
    ]
    if structural and len(operations) > len(structural):
        raise ValueError(
            "Structural story edits must be reviewed separately from caption, "
            "B-roll, or music changes. Apply the story change first, then build "
            "a second constrained edit proposal."
        )
    if len(structural) > 1:
        raise ValueError(
            "Only one structural story edit can be reviewed in a constrained "
            "proposal at a time."
        )

    if not operations:
        raise ValueError(
            "The instruction was understood, but there are no matching timeline "
            "items inside the requested scope."
        )

    touched = sorted({operation["component"] for operation in operations})
    touched_labels = {
        "story": "primary story clips",
        "captions": "captions",
        "broll": "B-roll",
        "music": "music",
    }
    preserved = [
        component
        for component in ("primary story clips", "captions", "B-roll", "music")
        if component not in {touched_labels.get(value, value) for value in touched}
    ]
    preserve_rules = [
        f"Preserve all timeline content outside {start_sec:.2f}s–{end_sec:.2f}s.",
    ]
    if "story" in touched:
        preserve_rules.append(
            "Ripple synchronized timeline items globally while preserving retained "
            "primary clip source ranges and ordering."
        )
    else:
        preserve_rules.append("Do not regenerate or reorder primary story clips.")
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

        if op == "retime_scope":
            if component != "story":
                raise ValueError("Pacing operation has invalid component")
            apply_retime_scope(sequence, payload)
            continue

        if op == "remove_speaker_ripple":
            if component != "story":
                raise ValueError("Speaker-removal operation has invalid component")
            _apply_speaker_ripple(sequence, payload)
            continue

        if op == "replace_broll":
            if component != "broll":
                raise ValueError("B-roll replacement has invalid component")
            track = next(
                (
                    item
                    for item in sequence.get("tracks") or []
                    if item.get("id") == payload.get("track_id")
                ),
                None,
            )
            if not track or track.get("kind") != "overlay" or track.get("locked"):
                raise ValueError("B-roll replacement target track is unavailable or locked")
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
                raise ValueError("B-roll replacement target no longer exists")
            metadata = clip.get("metadata") or {}
            if not (metadata.get("broll") or metadata.get("ai_plan_id")):
                raise ValueError("Proposal cannot replace a non-AI overlay")

            replacement_asset_id = str(payload.get("asset_id") or "")
            source_start = int(payload.get("source_start") or 0)
            source_duration = int(payload.get("source_duration") or 0)
            if not replacement_asset_id or source_start < 0 or source_duration <= 0:
                raise ValueError("B-roll replacement source range is invalid")
            if source_duration != int(clip.get("duration") or 0):
                raise ValueError(
                    "B-roll replacement must preserve the exact timeline-slot duration"
                )

            old_asset_id = clip.get("asset_id")
            clip["asset_id"] = replacement_asset_id
            clip["source_start"] = source_start
            clip["source_duration"] = source_duration
            clip["metadata"] = {
                **metadata,
                "broll": True,
                "semantic_replacement": True,
                "replacement_from_asset_id": old_asset_id,
                "source_intelligence_id": payload.get("source_intelligence_id"),
                "source_observation_index": payload.get("source_observation_index"),
                "broll_relevance_score": payload.get("relevance_score"),
                "replacement_query": payload.get("replacement_query"),
            }
            continue

        if op == "repair_caption":
            if component != "captions":
                raise ValueError("QA caption repair has invalid component")
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
                raise ValueError("QA repair target caption no longer exists")

            replacements = deepcopy(payload.get("replacements") or [])
            if not replacements:
                raise ValueError("QA caption repair contains no replacement cues")
            ids = [str(item.get("id") or "") for item in replacements]
            if any(not item for item in ids) or len(ids) != len(set(ids)):
                raise ValueError("QA caption repair contains invalid replacement IDs")

            original_start = int(cue.get("start") or 0)
            original_end = original_start + int(cue.get("duration") or 0)
            normalized_original = " ".join(str(cue.get("text") or "").split())
            normalized_replacement = " ".join(
                " ".join(str(item.get("text") or "").split())
                for item in replacements
            ).strip()
            if normalized_replacement != normalized_original:
                raise ValueError("QA caption repair must preserve the original caption text")

            previous_end = None
            for item in sorted(
                replacements,
                key=lambda value: (int(value.get("start") or 0), str(value.get("id") or "")),
            ):
                start = int(item.get("start") or 0)
                duration = int(item.get("duration") or 0)
                end = start + duration
                if duration <= 0 or start < original_start or end > original_end:
                    raise ValueError(
                        "QA caption repair must stay inside the original caption interval"
                    )
                if previous_end is not None and start < previous_end:
                    raise ValueError("QA caption repair replacement cues cannot overlap")
                previous_end = end

            sequence["captions"] = [
                item
                for item in sequence.get("captions") or []
                if item.get("id") != caption_id
            ] + replacements
            sequence["captions"].sort(
                key=lambda item: (int(item.get("start") or 0), str(item.get("id") or ""))
            )
            continue

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
