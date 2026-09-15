"""Deterministic fitting of user-selected music to an output timeline."""
from __future__ import annotations


class MusicFitError(ValueError):
    pass


def plan_loop_segments(
    *,
    output_duration_ticks: int,
    asset_duration_ticks: int,
    source_start_ticks: int,
    requested_crossfade_ticks: int,
) -> tuple[list[dict], dict]:
    """Fit a music asset across the output using bounded overlapping loops.

    The first segment begins at the user-selected source offset. If more music
    is required, later segments restart from source zero. Adjacent loop
    segments overlap by a bounded crossfade so the canonical timeline can
    execute a fade-out/fade-in seam without renderer-specific looping state.
    """
    output_duration = int(output_duration_ticks)
    asset_duration = int(asset_duration_ticks)
    source_start = int(source_start_ticks)
    requested_crossfade = max(0, int(requested_crossfade_ticks))

    if output_duration <= 0:
        raise MusicFitError("output duration must be positive")
    if asset_duration <= 0:
        raise MusicFitError("music asset duration must be positive")
    if source_start < 0 or source_start >= asset_duration:
        raise MusicFitError("music source start must be inside the asset")

    first_available = asset_duration - source_start
    if output_duration <= first_available:
        return (
            [
                {
                    "timeline_start": 0,
                    "duration": output_duration,
                    "source_start": source_start,
                    "source_duration": output_duration,
                }
            ],
            {
                "fit_mode": "single",
                "segment_count": 1,
                "loop_count": 0,
                "crossfade_ticks": 0,
            },
        )

    shortest_loop_span = min(first_available, asset_duration)
    max_safe_crossfade = max(0, shortest_loop_span // 4)
    crossfade = min(requested_crossfade, max_safe_crossfade)
    if crossfade <= 0:
        raise MusicFitError(
            "music is too short for a safe loop crossfade at this timebase"
        )

    segments: list[dict] = [
        {
            "timeline_start": 0,
            "duration": first_available,
            "source_start": source_start,
            "source_duration": first_available,
        }
    ]
    timeline_end = first_available

    while timeline_end < output_duration:
        timeline_start = max(0, timeline_end - crossfade)
        remaining = output_duration - timeline_start
        duration = min(asset_duration, remaining)
        if duration <= crossfade:
            raise MusicFitError("loop segment would not advance the timeline")
        segments.append(
            {
                "timeline_start": timeline_start,
                "duration": duration,
                "source_start": 0,
                "source_duration": duration,
            }
        )
        timeline_end = timeline_start + duration

    return segments, {
        "fit_mode": "loop",
        "segment_count": len(segments),
        "loop_count": len(segments) - 1,
        "crossfade_ticks": crossfade,
        "requested_crossfade_ticks": requested_crossfade,
        "crossfade_capped": crossfade < requested_crossfade,
    }


def attach_loop_transitions(
    segments: list[dict],
    *,
    seam_crossfade_ticks: int,
    intro_fade_ticks: int,
    outro_fade_ticks: int,
) -> list[dict]:
    """Attach canonical fades to music segments.

    Seam fades are added only where segments overlap. The first/last segments
    retain the overall music-bed intro/outro fades.
    """
    if not segments:
        return []

    result = [dict(segment) for segment in segments]
    count = len(result)
    for index, segment in enumerate(result):
        transition_in = None
        transition_out = None

        if index == 0 and intro_fade_ticks > 0:
            transition_in = {
                "kind": "fade",
                "duration": min(intro_fade_ticks, segment["duration"]),
            }
        elif index > 0 and seam_crossfade_ticks > 0:
            transition_in = {
                "kind": "fade",
                "duration": min(seam_crossfade_ticks, segment["duration"]),
            }

        if index == count - 1 and outro_fade_ticks > 0:
            transition_out = {
                "kind": "fade",
                "duration": min(outro_fade_ticks, segment["duration"]),
            }
        elif index < count - 1 and seam_crossfade_ticks > 0:
            transition_out = {
                "kind": "fade",
                "duration": min(seam_crossfade_ticks, segment["duration"]),
            }

        segment["transition_in"] = transition_in
        segment["transition_out"] = transition_out

    return result
