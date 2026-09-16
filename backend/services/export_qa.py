"""Post-render export quality analysis.

This module deliberately separates:
1) deterministic timeline checks from the RenderPlan; and
2) signal checks on the actual rendered file using FFmpeg.

QA never changes ProjectState and warnings never invalidate an otherwise valid export.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import settings
from models.render_plan import RenderPlan


_BLACK_RE = re.compile(
    r"black_start:(?P<start>[0-9.]+)\s+black_end:(?P<end>[0-9.]+)\s+black_duration:(?P<duration>[0-9.]+)"
)
_SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<start>[0-9.]+)")
_SILENCE_END_RE = re.compile(
    r"silence_end:\s*(?P<end>[0-9.]+)\s*\|\s*silence_duration:\s*(?P<duration>[0-9.]+)"
)
_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(?P<value>-?[0-9.]+)\s*dB")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(?P<value>-?[0-9.]+)\s*dB")


def _sec(plan: RenderPlan, ticks: int) -> float:
    return ticks * plan.timebase_denominator / plan.timebase_numerator


def _issue(
    code: str,
    severity: str,
    category: str,
    message: str,
    *,
    start_sec: float | None = None,
    end_sec: float | None = None,
    evidence: dict[str, Any] | None = None,
    suggested_action: str | None = None,
    auto_fixable: bool = False,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "category": category,
        "message": message,
        "start_sec": round(start_sec, 3) if start_sec is not None else None,
        "end_sec": round(end_sec, 3) if end_sec is not None else None,
        "evidence": evidence or {},
        "suggested_action": suggested_action,
        "auto_fixable": auto_fixable,
    }


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not intervals:
        return []
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 1e-6:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def analyze_plan_quality(plan: RenderPlan) -> tuple[list[dict], list[dict]]:
    """Check timeline continuity, B-roll repetition and caption readability."""
    issues: list[dict] = []
    checks: list[dict] = []
    total_duration = _sec(plan, plan.duration_ticks)

    primary = [
        clip
        for clip in plan.clips
        if clip.track_kind == "video"
    ]
    primary_intervals = _merge_intervals(
        [
            (
                _sec(plan, clip.timeline_start),
                _sec(plan, clip.timeline_start + clip.duration),
            )
            for clip in primary
        ]
    )
    gap_count = 0
    cursor = 0.0
    for start, end in primary_intervals:
        if start - cursor >= 0.25:
            gap_count += 1
            issues.append(
                _issue(
                    "timeline.primary_visual_gap",
                    "warning",
                    "timeline",
                    "Primary visual track has an uncovered timeline gap that may render as black.",
                    start_sec=cursor,
                    end_sec=start,
                    evidence={"gap_duration_sec": round(start - cursor, 3)},
                    suggested_action="Review the primary video track and cover or intentionally approve the gap.",
                )
            )
        cursor = max(cursor, end)
    if total_duration - cursor >= 0.25:
        gap_count += 1
        issues.append(
            _issue(
                "timeline.primary_visual_gap",
                "warning",
                "timeline",
                "Primary visual track ends before the export timeline.",
                start_sec=cursor,
                end_sec=total_duration,
                evidence={"gap_duration_sec": round(total_duration - cursor, 3)},
                suggested_action="Trim the sequence end or extend the intended final visual.",
            )
        )
    checks.append(
        {
            "id": "timeline_continuity",
            "status": "warning" if gap_count else "passed",
            "summary": (
                f"Found {gap_count} uncovered primary visual gap(s)."
                if gap_count
                else "Primary visual timeline is continuously covered."
            ),
            "details": {"gap_count": gap_count},
        }
    )

    overlays = sorted(
        [clip for clip in plan.clips if clip.track_kind == "overlay"],
        key=lambda clip: (clip.timeline_start, clip.clip_id),
    )
    repeated_count = 0
    for previous, current in zip(overlays, overlays[1:]):
        previous_end = _sec(plan, previous.timeline_start + previous.duration)
        current_start = _sec(plan, current.timeline_start)
        if (
            previous.asset_id == current.asset_id
            and current_start - previous_end <= 8.0
        ):
            repeated_count += 1
            issues.append(
                _issue(
                    "visual.repeated_broll_source",
                    "warning",
                    "visual",
                    "The same B-roll source is reused again within a short interval.",
                    start_sec=current_start,
                    end_sec=_sec(plan, current.timeline_start + current.duration),
                    evidence={
                        "asset_id": current.asset_id,
                        "previous_clip_id": previous.clip_id,
                        "clip_id": current.clip_id,
                    },
                    suggested_action="Consider a different grounded visual or keep the primary shot.",
                    auto_fixable=False,
                )
            )
    checks.append(
        {
            "id": "broll_repetition",
            "status": "warning" if repeated_count else "passed",
            "summary": (
                f"Found {repeated_count} nearby repeated B-roll source(s)."
                if repeated_count
                else "No nearby repeated B-roll sources detected."
            ),
            "details": {"repeated_source_count": repeated_count},
        }
    )

    captions = sorted(plan.captions, key=lambda cue: (cue.start, cue.id))
    caption_issue_count = 0
    previous_end = -1
    for cue in captions:
        start = _sec(plan, cue.start)
        end = _sec(plan, cue.start + cue.duration)
        duration = max(0.001, end - start)
        words = len([word for word in cue.text.split() if word.strip()])
        reading_rate = words / duration

        if cue.start < previous_end:
            caption_issue_count += 1
            issues.append(
                _issue(
                    "captions.overlap",
                    "warning",
                    "captions",
                    "Caption cues overlap in time.",
                    start_sec=start,
                    end_sec=end,
                    evidence={"caption_id": cue.id},
                    suggested_action="Review caption timing so simultaneous cues are intentional.",
                    auto_fixable=True,
                )
            )
        previous_end = max(previous_end, cue.start + cue.duration)

        if reading_rate > 4.5 and words >= 5:
            caption_issue_count += 1
            issues.append(
                _issue(
                    "captions.reading_rate",
                    "warning",
                    "captions",
                    "Caption may disappear too quickly for comfortable reading.",
                    start_sec=start,
                    end_sec=end,
                    evidence={
                        "caption_id": cue.id,
                        "words": words,
                        "words_per_second": round(reading_rate, 2),
                    },
                    suggested_action="Shorten the caption text or increase its on-screen duration.",
                )
            )

        if len(cue.text.strip()) > 120:
            caption_issue_count += 1
            issues.append(
                _issue(
                    "captions.long_text",
                    "warning",
                    "captions",
                    "Caption contains a large amount of text for one cue.",
                    start_sec=start,
                    end_sec=end,
                    evidence={
                        "caption_id": cue.id,
                        "character_count": len(cue.text.strip()),
                    },
                    suggested_action="Split this cue into shorter caption phrases.",
                    auto_fixable=True,
                )
            )

        if end > total_duration + 0.05:
            caption_issue_count += 1
            issues.append(
                _issue(
                    "captions.out_of_bounds",
                    "error",
                    "captions",
                    "Caption extends beyond the export duration.",
                    start_sec=start,
                    end_sec=end,
                    evidence={"caption_id": cue.id, "export_duration_sec": total_duration},
                    suggested_action="Trim the caption to the sequence duration.",
                    auto_fixable=True,
                )
            )

    checks.append(
        {
            "id": "caption_readability",
            "status": (
                "failed"
                if any(issue["severity"] == "error" and issue["category"] == "captions" for issue in issues)
                else "warning"
                if caption_issue_count
                else "passed"
            ),
            "summary": (
                f"Found {caption_issue_count} caption timing/readability issue(s)."
                if caption_issue_count
                else "Caption timing and reading-rate checks passed."
            ),
            "details": {
                "caption_count": len(captions),
                "issue_count": caption_issue_count,
            },
        }
    )
    return issues, checks


def parse_ffmpeg_signal_output(stderr: str) -> dict:
    black_segments = []
    for match in _BLACK_RE.finditer(stderr):
        black_segments.append(
            {
                "start_sec": float(match.group("start")),
                "end_sec": float(match.group("end")),
                "duration_sec": float(match.group("duration")),
            }
        )

    silence_segments = []
    pending_start: float | None = None
    for line in stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group("start"))
        end_match = _SILENCE_END_RE.search(line)
        if end_match:
            end = float(end_match.group("end"))
            duration = float(end_match.group("duration"))
            start = pending_start if pending_start is not None else max(0.0, end - duration)
            silence_segments.append(
                {
                    "start_sec": start,
                    "end_sec": end,
                    "duration_sec": duration,
                }
            )
            pending_start = None

    mean_match = _MEAN_VOLUME_RE.search(stderr)
    max_match = _MAX_VOLUME_RE.search(stderr)
    return {
        "black_segments": black_segments,
        "silence_segments": silence_segments,
        "mean_volume_db": float(mean_match.group("value")) if mean_match else None,
        "max_volume_db": float(max_match.group("value")) if max_match else None,
    }


def _run_signal_analysis(path: Path) -> dict:
    command = [
        settings.FFMPEG_PATH,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vf",
        "blackdetect=d=0.25:pix_th=0.10",
        "-af",
        "silencedetect=noise=-42dB:d=0.8,volumedetect",
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=min(settings.RENDER_TIMEOUT_SEC, 120),
        check=False,
    )
    # FFmpeg analysis normally returns 0. Preserve stderr even on a nonzero
    # result so QA can degrade to an explicit unavailable check.
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "ffmpeg QA failed")[-2000:])
    return parse_ffmpeg_signal_output(completed.stderr or "")


def _signal_issues(signal: dict) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    black = [
        segment
        for segment in signal.get("black_segments") or []
        if float(segment.get("duration_sec") or 0.0) >= 0.35
    ]
    for segment in black:
        issues.append(
            _issue(
                "visual.black_segment",
                "warning",
                "visual",
                "Rendered video contains a sustained near-black segment.",
                start_sec=segment["start_sec"],
                end_sec=segment["end_sec"],
                evidence={"duration_sec": round(segment["duration_sec"], 3)},
                suggested_action="Review whether this black segment is intentional or caused by an uncovered visual gap.",
            )
        )
    checks = [
        {
            "id": "black_frames",
            "status": "warning" if black else "passed",
            "summary": (
                f"Found {len(black)} sustained near-black segment(s)."
                if black
                else "No sustained near-black segments detected."
            ),
            "details": {"segment_count": len(black)},
        }
    ]

    long_silence = [
        segment
        for segment in signal.get("silence_segments") or []
        if float(segment.get("duration_sec") or 0.0) >= 3.0
    ]
    for segment in long_silence:
        issues.append(
            _issue(
                "audio.long_silence",
                "warning",
                "audio",
                "Rendered audio contains an extended silent section.",
                start_sec=segment["start_sec"],
                end_sec=segment["end_sec"],
                evidence={"duration_sec": round(segment["duration_sec"], 3)},
                suggested_action="Check whether the silence is intentional or caused by a missing/trimmed audio source.",
            )
        )

    mean_volume = signal.get("mean_volume_db")
    max_volume = signal.get("max_volume_db")
    if mean_volume is not None and mean_volume < -35.0:
        issues.append(
            _issue(
                "audio.low_average_level",
                "warning",
                "audio",
                "Average output level is very quiet.",
                evidence={"mean_volume_db": round(mean_volume, 2)},
                suggested_action="Review dialogue gain and final mix loudness.",
                auto_fixable=True,
            )
        )
    if max_volume is not None and max_volume >= -0.1:
        issues.append(
            _issue(
                "audio.peak_near_zero",
                "warning",
                "audio",
                "Output peaks are extremely close to digital full scale.",
                evidence={"max_volume_db": round(max_volume, 2)},
                suggested_action="Lower the final mix slightly to preserve headroom.",
                auto_fixable=True,
            )
        )
    audio_warning_count = len(
        [issue for issue in issues if issue["category"] == "audio"]
    )
    checks.append(
        {
            "id": "audio_signal",
            "status": "warning" if audio_warning_count else "passed",
            "summary": (
                f"Found {audio_warning_count} audio signal warning(s)."
                if audio_warning_count
                else "Audio silence and level checks passed."
            ),
            "details": {
                "long_silence_count": len(long_silence),
                "mean_volume_db": mean_volume,
                "max_volume_db": max_volume,
            },
        }
    )
    return issues, checks


def analyze_export(path: Path, plan: RenderPlan) -> dict:
    issues, checks = analyze_plan_quality(plan)
    try:
        signal = _run_signal_analysis(path)
        signal_issues, signal_checks = _signal_issues(signal)
        issues.extend(signal_issues)
        checks.extend(signal_checks)
    except Exception as exc:
        checks.extend(
            [
                {
                    "id": "black_frames",
                    "status": "warning",
                    "summary": "Rendered-file visual analysis was unavailable.",
                    "details": {"error": str(exc)[:500]},
                },
                {
                    "id": "audio_signal",
                    "status": "warning",
                    "summary": "Rendered-file audio analysis was unavailable.",
                    "details": {"error": str(exc)[:500]},
                },
            ]
        )
        issues.append(
            _issue(
                "qa.signal_analysis_unavailable",
                "info",
                "timeline",
                "ShortCut could not complete file-level signal analysis, but the export passed core render validation.",
                evidence={"error": str(exc)[:500]},
            )
        )

    errors = sum(issue["severity"] == "error" for issue in issues)
    warnings = sum(issue["severity"] == "warning" for issue in issues)
    status = "failed" if errors else "warnings" if warnings else "passed"
    return {
        "status": status,
        "issue_count": len(issues),
        "warning_count": warnings,
        "error_count": errors,
        "issues": issues,
        "checks": checks,
        "generated_at": datetime.now(timezone.utc),
    }
