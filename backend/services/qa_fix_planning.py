"""Build reviewable ProjectState repairs from Export QA evidence."""
from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from copy import deepcopy
from typing import Any


_SUPPORTED_CODES = {
    "captions.overlap",
    "captions.long_text",
    "captions.out_of_bounds",
}


def _active_export_sequence(state: dict, export_doc: dict) -> dict:
    sequence_id = str(export_doc.get("sequence_id") or state.get("active_sequence_id") or "")
    sequence = next(
        (
            item
            for item in state.get("sequences") or []
            if str(item.get("id") or "") == sequence_id
        ),
        None,
    )
    if not sequence:
        raise ValueError("The sequence used by this export no longer exists")
    return sequence


def _ticks_per_second(sequence: dict) -> float:
    timebase = sequence.get("timebase") or {}
    return float(timebase.get("numerator") or 1000) / float(
        timebase.get("denominator") or 1
    )


def _primary_visual_end(sequence: dict) -> int:
    ends = [
        int(clip.get("timeline_start") or 0) + int(clip.get("duration") or 0)
        for track in (sequence.get("tracks") or [])
        if track.get("kind") == "video"
        for clip in (track.get("clips") or [])
    ]
    if ends:
        return max(ends)
    return max(
        [
            int(cue.get("start") or 0) + int(cue.get("duration") or 0)
            for cue in (sequence.get("captions") or [])
        ]
        or [1]
    )


def _replacement_id(caption_id: str, index: int) -> str:
    digest = hashlib.sha1(f"{caption_id}:qa:{index}".encode("utf-8")).hexdigest()[:12]
    return f"qa-{digest}"


def _split_text(text: str, max_chars: int = 90) -> list[str]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    chunks: list[list[str]] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(current)
    return [" ".join(chunk) for chunk in chunks if chunk]


def _allocate_durations(total: int, chunks: list[str], min_ticks: int) -> list[int] | None:
    if not chunks:
        return None
    if len(chunks) == 1:
        return [total]
    if total < len(chunks) * min_ticks:
        return None

    weights = [max(1, len(chunk.split())) for chunk in chunks]
    weight_total = sum(weights)
    durations = [
        max(min_ticks, round(total * weight / weight_total))
        for weight in weights
    ]
    diff = total - sum(durations)
    durations[-1] += diff
    if durations[-1] < min_ticks:
        needed = min_ticks - durations[-1]
        for index in range(len(durations) - 2, -1, -1):
            available = durations[index] - min_ticks
            take = min(available, needed)
            durations[index] -= take
            durations[-1] += take
            needed -= take
            if needed <= 0:
                break
    if sum(durations) != total or any(value < min_ticks for value in durations):
        return None
    return durations


def _repair_parts(
    *,
    cue: dict,
    start: int,
    duration: int,
    codes: set[str],
    export_id: str,
    min_ticks: int,
) -> tuple[list[dict], set[str]]:
    applied_codes = set(codes)
    text = str(cue.get("text") or "").strip()
    chunks = [text]
    if "captions.long_text" in codes:
        proposed = _split_text(text)
        durations = _allocate_durations(duration, proposed, min_ticks)
        if len(proposed) > 1 and durations:
            chunks = proposed
        else:
            applied_codes.discard("captions.long_text")

    durations = _allocate_durations(duration, chunks, min_ticks)
    if not durations:
        raise ValueError("Caption is too short to repair safely")

    style = {
        **(cue.get("style") or {}),
        "qa_repaired": True,
        "qa_source_export_id": export_id,
        "qa_issue_codes": sorted(applied_codes),
    }

    parts: list[dict] = []
    cursor = start
    for index, (chunk, part_duration) in enumerate(zip(chunks, durations)):
        parts.append(
            {
                "id": (
                    str(cue["id"])
                    if len(chunks) == 1
                    else _replacement_id(str(cue["id"]), index)
                ),
                "start": cursor,
                "duration": part_duration,
                "text": chunk,
                "style": deepcopy(style),
            }
        )
        cursor += part_duration
    return parts, applied_codes


def build_qa_fix_proposal(
    *,
    project_id: str,
    user_id: str,
    state: dict,
    export_doc: dict,
) -> dict:
    report = export_doc.get("qa_report") or {}
    issues = report.get("issues") or []
    sequence = _active_export_sequence(state, export_doc)
    tps = _ticks_per_second(sequence)
    min_ticks = max(1, round(0.30 * tps))
    visual_end = _primary_visual_end(sequence)

    captions = sorted(
        [deepcopy(cue) for cue in (sequence.get("captions") or [])],
        key=lambda cue: (int(cue.get("start") or 0), str(cue.get("id") or "")),
    )
    by_id = {str(cue.get("id") or ""): cue for cue in captions}

    codes_by_caption: dict[str, set[str]] = defaultdict(set)
    for issue in issues:
        if not issue.get("auto_fixable"):
            continue
        code = str(issue.get("code") or "")
        if code not in _SUPPORTED_CODES:
            continue
        caption_id = str((issue.get("evidence") or {}).get("caption_id") or "")
        if caption_id in by_id:
            codes_by_caption[caption_id].add(code)

    operations: list[dict] = []
    for index, cue in enumerate(captions):
        caption_id = str(cue.get("id") or "")
        codes = codes_by_caption.get(caption_id)
        if not codes:
            continue

        original_start = int(cue.get("start") or 0)
        original_duration = int(cue.get("duration") or 0)
        original_end = original_start + original_duration
        start = original_start
        end = original_end
        applied_codes = set(codes)

        if "captions.overlap" in codes and index > 0:
            previous = captions[index - 1]
            previous_end = int(previous.get("start") or 0) + int(
                previous.get("duration") or 0
            )
            if previous_end > start and original_end - previous_end >= min_ticks:
                start = previous_end
            else:
                applied_codes.discard("captions.overlap")

        if "captions.out_of_bounds" in codes and end > visual_end:
            end = visual_end
            if end - start < min_ticks:
                applied_codes.discard("captions.out_of_bounds")
                end = original_end

        duration = end - start
        if duration < min_ticks:
            continue

        parts, actually_applied = _repair_parts(
            cue=cue,
            start=start,
            duration=duration,
            codes=applied_codes,
            export_id=str(export_doc["id"]),
            min_ticks=min_ticks,
        )
        if not actually_applied:
            continue

        operations.append(
            {
                "id": str(uuid.uuid4()),
                "operation": "repair_caption",
                "component": "captions",
                "payload": {
                    "sequence_id": sequence["id"],
                    "caption_id": caption_id,
                    "replacements": parts,
                    "qa_issue_codes": sorted(actually_applied),
                    "source_export_id": str(export_doc["id"]),
                },
                "reason": (
                    "Repair caption from Export QA: "
                    + ", ".join(code.replace("captions.", "") for code in sorted(actually_applied))
                    + "."
                ),
            }
        )

    if not operations:
        raise ValueError(
            "This export has no currently supported safe QA fixes. "
            "Other QA findings remain review recommendations."
        )

    visual_end_sec = visual_end / tps
    return {
        "project_id": project_id,
        "user_id": user_id,
        "project_state_version": int(state["version"]),
        "status": "proposed",
        "instruction": f"Repair safe QA findings from export {str(export_doc['id'])[:8]}",
        "interpreted_intents": ["fix_export_qa"],
        "scope_start_sec": 0.0,
        "scope_end_sec": max(0.001, round(visual_end_sec, 3)),
        "preserve_rules": [
            "Preserve every primary story clip, source range, B-roll decision and music decision.",
            "Only repair caption cues explicitly identified by this export's QA report.",
            "Do not apply fixes if ProjectState has changed since the reviewed export.",
        ],
        "summary": (
            f"Proposed {len(operations)} safe caption QA repair"
            f"{'' if len(operations) == 1 else 's'} from the finished export."
        ),
        "operations": operations,
    }
