"""Speaker-aware planner helpers grounded in diarized transcript labels."""
from __future__ import annotations


def normalize_speakers(unit: dict) -> list[str]:
    labels = []
    for value in unit.get("speakers") or []:
        label = str(value).strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def speaker_allowed(
    speakers: list[str],
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> bool:
    include_set = {str(value).strip() for value in (include or []) if str(value).strip()}
    exclude_set = {str(value).strip() for value in (exclude or []) if str(value).strip()}
    speaker_set = set(speakers)

    if include_set and not (speaker_set & include_set):
        return False
    if exclude_set and (speaker_set & exclude_set):
        return False
    return True


def primary_speaker(speakers: list[str]) -> str | None:
    return speakers[0] if len(speakers) == 1 else None
