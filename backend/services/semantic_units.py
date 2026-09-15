"""Build retrieval-ready semantic units from transcript and scene timing."""
from __future__ import annotations


def build_semantic_units(
    *,
    segments: list[dict],
    scenes: list[dict],
    max_window_sec: float = 30.0,
) -> list[dict]:
    """Create time-aligned chunks without inventing semantic content.

    Units preserve transcript wording and timing. Later embedding/LLM stages can
    enrich these units, but this deterministic step remains auditable.
    """
    if not segments:
        return []

    units: list[dict] = []
    current: list[dict] = []
    window_start = float(segments[0].get("start", 0.0))

    scene_starts = {round(float(scene["start"]), 3) for scene in scenes[1:]}

    def flush() -> None:
        nonlocal current, window_start
        if not current:
            return
        text = " ".join(str(item.get("text", "")).strip() for item in current).strip()
        if text:
            units.append(
                {
                    "index": len(units),
                    "start": float(current[0].get("start", 0.0)),
                    "end": float(current[-1].get("end", current[-1].get("start", 0.0))),
                    "text": text,
                    "segment_count": len(current),
                }
            )
        current = []

    for segment in segments:
        start = float(segment.get("start", 0.0))
        if current and (
            start - window_start >= max_window_sec
            or round(start, 3) in scene_starts
        ):
            flush()
            window_start = start
        current.append(segment)

    flush()
    return units
