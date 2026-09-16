"""Conservative sequence-wide pacing changes for Create With Me."""
from __future__ import annotations

import hashlib
import re
import uuid
from copy import deepcopy
from typing import Any


def _operation(*, payload: dict, reason: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "operation": "retime_scope",
        "component": "story",
        "payload": payload,
        "reason": reason,
    }


def _retime_factor(instruction: str) -> float | None:
    lowered = instruction.lower()
    requested = bool(
        re.search(r"\bspeed\s+up\b", lowered)
        or re.search(r"\bmake\b.+\bfaster\b", lowered)
        or re.search(r"\b(?:faster|quicker)\s+(?:pace|pacing)\b", lowered)
        or re.search(r"\btighten\s+(?:the\s+)?(?:pace|pacing)\b", lowered)
    )
    if not requested:
        return None

    explicit = re.search(r"\b(1(?:\.\d+)?|2(?:\.0+)?)\s*[x×]\b", lowered)
    if explicit:
        factor = float(explicit.group(1))
        if factor < 1.05 or factor > 1.5:
            raise ValueError(
                "Scoped pacing currently supports speed-up factors from 1.05x to 1.50x."
            )
        return round(factor, 3)

    if re.search(r"\b(?:much|way|significantly)\s+faster\b", lowered):
        return 1.25
    if re.search(r"\b(?:slightly|a\s+bit)\s+faster\b", lowered):
        return 1.10
    return 1.15


def pacing_operations(
    *,
    instruction: str,
    sequence: dict,
    scope_start: int,
    scope_end: int,
) -> tuple[list[str], list[dict]]:
    factor = _retime_factor(instruction)
    if factor is None:
        return [], []
    if scope_end <= scope_start:
        raise ValueError("Pacing scope must have positive duration")

    primary = [
        clip
        for track in (sequence.get("tracks") or [])
        if track.get("kind") == "video"
        for clip in (track.get("clips") or [])
        if int(clip.get("timeline_start") or 0) < scope_end
        and int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0)
        > scope_start
    ]
    if not primary:
        return ["tighten_pacing"], []

    old_duration = scope_end - scope_start
    new_duration = max(1, round(old_duration / factor))
    removed = old_duration - new_duration
    if removed <= 0:
        raise ValueError("Pacing factor does not shorten the requested scope")

    tps = float((sequence.get("timebase") or {}).get("numerator") or 1000) / float(
        (sequence.get("timebase") or {}).get("denominator") or 1
    )
    return ["tighten_pacing"], [
        _operation(
            payload={
                "sequence_id": sequence["id"],
                "scope_start": scope_start,
                "scope_end": scope_end,
                "speed_factor": factor,
                "original_duration_ticks": old_duration,
                "retimed_duration_ticks": new_duration,
                "removed_duration_ticks": removed,
                "primary_clip_ids": [str(clip.get("id") or "") for clip in primary],
            },
            reason=(
                f"Speed the selected story region from {old_duration / tps:.2f}s "
                f"to {new_duration / tps:.2f}s at {factor:.2f}x and ripple "
                f"{removed / tps:.2f}s out of synchronized timeline content."
            ),
        )
    ]


def _map_tick(tick: int, *, start: int, end: int, factor: float) -> int:
    if tick <= start:
        return tick
    compressed_end = start + round((end - start) / factor)
    if tick >= end:
        return tick - (end - compressed_end)
    return start + round((tick - start) / factor)


def _segment_id(clip_id: str, start: int, end: int, index: int) -> str:
    digest = hashlib.sha1(f"{clip_id}:{start}:{end}:{index}".encode("utf-8")).hexdigest()[:12]
    return f"pace-{digest}"


def _fit_transition(transition: dict | None, duration: int) -> dict | None:
    if not transition:
        return None
    if int(transition.get("duration") or 0) <= duration:
        return deepcopy(transition)
    return None


def _split_and_retime_video_clip(
    clip: dict,
    *,
    scope_start: int,
    scope_end: int,
    factor: float,
) -> list[dict]:
    start = int(clip.get("timeline_start") or 0)
    duration = int(clip.get("duration") or 0)
    end = start + duration
    if duration <= 0:
        return []

    if end <= scope_start:
        return [deepcopy(clip)]
    if start >= scope_end:
        shifted = deepcopy(clip)
        shifted["timeline_start"] = _map_tick(
            start, start=scope_start, end=scope_end, factor=factor
        )
        return [shifted]

    boundaries = [start]
    if start < scope_start < end:
        boundaries.append(scope_start)
    if start < scope_end < end:
        boundaries.append(scope_end)
    boundaries.append(end)
    boundaries = sorted(set(boundaries))

    source_start = int(clip.get("source_start") or 0)
    source_duration = int(clip.get("source_duration") or duration)
    pieces: list[dict] = []

    for index, (seg_start, seg_end) in enumerate(zip(boundaries, boundaries[1:])):
        seg_duration = seg_end - seg_start
        if seg_duration <= 0:
            continue

        rel_start = (seg_start - start) / duration
        rel_end = (seg_end - start) / duration
        seg_source_start = source_start + round(source_duration * rel_start)
        seg_source_end = source_start + round(source_duration * rel_end)
        seg_source_duration = max(1, seg_source_end - seg_source_start)

        paced = seg_start >= scope_start and seg_end <= scope_end
        new_start = _map_tick(
            seg_start, start=scope_start, end=scope_end, factor=factor
        )
        new_end = _map_tick(
            seg_end, start=scope_start, end=scope_end, factor=factor
        )
        new_duration = max(1, new_end - new_start)
        new_rate = seg_source_duration / new_duration

        if new_rate > 8.0:
            raise ValueError(
                "Scoped pacing would exceed the renderer's maximum playback rate"
            )

        piece = deepcopy(clip)
        piece["id"] = (
            str(clip["id"])
            if len(boundaries) == 2
            else _segment_id(str(clip["id"]), seg_start, seg_end, index)
        )
        piece["timeline_start"] = new_start
        piece["duration"] = new_duration
        piece["source_start"] = seg_source_start
        piece["source_duration"] = seg_source_duration
        piece["playback_rate"] = round(new_rate, 8)
        piece["transition_in"] = (
            _fit_transition(clip.get("transition_in"), new_duration)
            if index == 0
            else None
        )
        piece["transition_out"] = (
            _fit_transition(clip.get("transition_out"), new_duration)
            if index == len(boundaries) - 2
            else None
        )
        piece["metadata"] = {
            **(clip.get("metadata") or {}),
            "pacing_retimed": paced,
            "pacing_factor": factor if paced else 1.0,
            "pacing_parent_clip_id": str(clip.get("id") or ""),
        }
        pieces.append(piece)

    return pieces


def _retime_nonvideo_clip(
    clip: dict,
    *,
    track_kind: str,
    scope_start: int,
    scope_end: int,
    factor: float,
) -> dict:
    start = int(clip.get("timeline_start") or 0)
    duration = int(clip.get("duration") or 0)
    end = start + duration

    if end <= scope_start:
        return deepcopy(clip)
    if start >= scope_end:
        shifted = deepcopy(clip)
        shifted["timeline_start"] = _map_tick(
            start, start=scope_start, end=scope_end, factor=factor
        )
        return shifted

    metadata = clip.get("metadata") or {}
    safe_overlay = track_kind == "overlay" and bool(
        metadata.get("broll") or metadata.get("ai_plan_id")
    )
    safe_music = track_kind == "audio" and bool(metadata.get("music_bed"))
    if not (safe_overlay or safe_music):
        raise ValueError(
            "A user-authored or non-music clip overlaps the pacing scope; "
            "ShortCut refused to retime it automatically"
        )

    new_start = _map_tick(start, start=scope_start, end=scope_end, factor=factor)
    new_end = _map_tick(end, start=scope_start, end=scope_end, factor=factor)
    new_duration = max(1, new_end - new_start)

    shifted = deepcopy(clip)
    shifted["timeline_start"] = new_start
    shifted["duration"] = new_duration
    source_duration = int(clip.get("source_duration") or duration)
    shifted["source_duration"] = max(
        1,
        round(source_duration * new_duration / max(1, duration)),
    )
    shifted["transition_in"] = _fit_transition(
        clip.get("transition_in"), new_duration
    )
    shifted["transition_out"] = _fit_transition(
        clip.get("transition_out"), new_duration
    )
    shifted["metadata"] = {
        **metadata,
        "pacing_retimed": True,
        "pacing_factor": factor,
    }
    return shifted


def apply_retime_scope(sequence: dict, payload: dict) -> None:
    scope_start = int(payload.get("scope_start") or 0)
    scope_end = int(payload.get("scope_end") or 0)
    factor = float(payload.get("speed_factor") or 0.0)
    if scope_start < 0 or scope_end <= scope_start:
        raise ValueError("Pacing proposal has an invalid scope")
    if factor < 1.05 or factor > 1.5:
        raise ValueError("Pacing proposal has an unsupported speed factor")

    expected_ids = {
        str(value) for value in (payload.get("primary_clip_ids") or []) if str(value)
    }
    current_ids = {
        str(clip.get("id") or "")
        for track in (sequence.get("tracks") or [])
        if track.get("kind") == "video"
        for clip in (track.get("clips") or [])
        if int(clip.get("timeline_start") or 0) < scope_end
        and int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0)
        > scope_start
    }
    if expected_ids != current_ids:
        raise ValueError("Pacing target clips no longer match the reviewed proposal")

    for track in sequence.get("tracks") or []:
        clips = track.get("clips") or []
        affected = any(
            int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0)
            > scope_start
            for clip in clips
        )
        if track.get("locked") and affected:
            raise ValueError(
                f"Track '{track.get('name') or track.get('id')}' is locked and would lose sync"
            )

        if track.get("kind") == "video":
            next_clips: list[dict] = []
            for clip in clips:
                next_clips.extend(
                    _split_and_retime_video_clip(
                        clip,
                        scope_start=scope_start,
                        scope_end=scope_end,
                        factor=factor,
                    )
                )
            track["clips"] = next_clips
            continue

        track["clips"] = [
            _retime_nonvideo_clip(
                clip,
                track_kind=str(track.get("kind") or ""),
                scope_start=scope_start,
                scope_end=scope_end,
                factor=factor,
            )
            for clip in clips
        ]

    for cue in sequence.get("captions") or []:
        start = int(cue.get("start") or 0)
        end = start + int(cue.get("duration") or 0)
        new_start = _map_tick(
            start, start=scope_start, end=scope_end, factor=factor
        )
        new_end = _map_tick(
            end, start=scope_start, end=scope_end, factor=factor
        )
        cue["start"] = new_start
        cue["duration"] = max(1, new_end - new_start)
        cue["style"] = {
            **(cue.get("style") or {}),
            "pacing_retimed": (
                start < scope_end and end > scope_start
            ),
            "pacing_factor": factor,
        }
