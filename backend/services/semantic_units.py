"""Build retrieval-ready semantic units from transcript and scene timing."""
from __future__ import annotations


def build_semantic_units(
    *,
    segments: list[dict],
    scenes: list[dict],
    max_window_sec: float = 30.0,
    split_on_speaker: bool = True,
) -> list[dict]:
    """Create auditable time-aligned chunks from transcript segments."""
    if not segments:
        return []

    units: list[dict] = []
    current: list[dict] = []
    window_start = float(segments[0].get("start", 0.0))
    current_speaker = segments[0].get("speaker")

    scene_starts = {round(float(scene["start"]), 3) for scene in scenes[1:]}

    def flush() -> None:
        nonlocal current
        if not current:
            return
        text = " ".join(str(item.get("text", "")).strip() for item in current).strip()
        if text:
            speakers = sorted(
                {
                    str(item.get("speaker")).strip()
                    for item in current
                    if item.get("speaker") not in (None, "")
                }
            )
            units.append(
                {
                    "index": len(units),
                    "start": float(current[0].get("start", 0.0)),
                    "end": float(
                        current[-1].get("end", current[-1].get("start", 0.0))
                    ),
                    "text": text,
                    "segment_count": len(current),
                    "speakers": speakers,
                }
            )
        current = []

    for segment in segments:
        start = float(segment.get("start", 0.0))
        speaker = segment.get("speaker")
        speaker_changed = (
            split_on_speaker
            and current
            and speaker not in (None, "")
            and current_speaker not in (None, "")
            and speaker != current_speaker
        )
        if current and (
            start - window_start >= max_window_sec
            or round(start, 3) in scene_starts
            or speaker_changed
        ):
            flush()
            window_start = start
        if not current:
            current_speaker = speaker
            window_start = start
        current.append(segment)

    flush()
    return units
