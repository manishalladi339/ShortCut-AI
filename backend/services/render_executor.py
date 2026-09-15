"""FFmpeg execution for deterministic ShortCut AI render plans.

This executor supports:
- multiple video/overlay clips and tracks
- overlapping visual clips via ordered compositing
- clip transforms: scale, position, rotation, opacity
- source audio plus standalone audio-track mixing
- playback-rate and volume changes
- timeline gaps
- caption burn-in

Unsupported effect metadata still fails explicitly at higher layers rather than
being silently ignored.
"""
from __future__ import annotations

import math
import subprocess
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import settings
from models.render_plan import RenderPlan
from services.storage import materialize


class RenderExecutionError(RuntimeError):
    pass


def _ticks_to_seconds(ticks: int, numerator: int, denominator: int) -> float:
    return ticks * denominator / numerator


def _atempo_chain(rate: float) -> str:
    if rate <= 0:
        raise RenderExecutionError("playback rate must be positive")
    remaining = rate
    stages: list[float] = []
    while remaining > 2.0:
        stages.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        stages.append(0.5)
        remaining /= 0.5
    stages.append(remaining)
    return ",".join(f"atempo={value:.8f}" for value in stages)


def _transition_seconds(
    transition,
    *,
    numerator: int,
    denominator: int,
    clip_duration_sec: float,
) -> float:
    if transition is None:
        return 0.0
    if transition.kind != "fade":
        raise RenderExecutionError(f"unsupported transition kind: {transition.kind}")
    duration = _ticks_to_seconds(transition.duration, numerator, denominator)
    if duration <= 0 or duration > clip_duration_sec + 1e-6:
        raise RenderExecutionError("transition duration must fit inside the clip")
    return duration


def _run(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.RENDER_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RenderExecutionError(
            "ffmpeg is not installed or FFMPEG_PATH is invalid"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderExecutionError("render timed out") from exc

    if completed.returncode != 0:
        raise RenderExecutionError((completed.stderr or "ffmpeg failed").strip()[-6000:])


def _srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def _write_srt(plan: RenderPlan, destination: Path) -> None:
    blocks: list[str] = []
    for index, cue in enumerate(plan.captions, start=1):
        start_sec = _ticks_to_seconds(
            cue.start, plan.timebase_numerator, plan.timebase_denominator
        )
        end_sec = _ticks_to_seconds(
            cue.start + cue.duration,
            plan.timebase_numerator,
            plan.timebase_denominator,
        )
        text = cue.text.replace("\r", " ").strip()
        blocks.append(
            f"{index}\n{_srt_time(start_sec)} --> {_srt_time(end_sec)}\n{text}\n"
        )
    destination.write_text("\n".join(blocks), encoding="utf-8")


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def execute(plan: RenderPlan, output_path: Path) -> dict:
    """Render a deterministic timeline to H.264/AAC MP4."""
    visual_clips = [
        clip for clip in plan.clips if clip.track_kind in {"video", "overlay"}
    ]
    audio_clips = [
        clip
        for clip in plan.clips
        if clip.track_kind == "audio"
        or (
            clip.track_kind in {"video", "overlay"}
            and bool(clip.metadata.get("_asset_audio_codec"))
        )
    ]

    if not visual_clips:
        raise RenderExecutionError("render requires at least one visual clip")

    duration_sec = _ticks_to_seconds(
        plan.duration_ticks, plan.timebase_numerator, plan.timebase_denominator
    )
    if duration_sec <= 0:
        raise RenderExecutionError("render duration must be positive")

    ordered_visuals = sorted(
        visual_clips,
        key=lambda clip: (clip.track_index, clip.timeline_start, clip.clip_id),
    )

    with TemporaryDirectory(prefix="shortcut-render-") as tmp:
        root = Path(tmp)
        composed = root / "composed.mp4"

        command: list[str] = [
            settings.FFMPEG_PATH,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={plan.width}x{plan.height}:r=30:d={duration_sec:.6f}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=stereo:d={duration_sec:.6f}",
        ]

        clip_input_index: dict[str, int] = {}
        with ExitStack() as stack:
            for clip in plan.clips:
                suffix = Path(clip.source_storage_key).suffix
                source = stack.enter_context(materialize(clip.source_storage_key, suffix=suffix))
                input_index = 2 + len(clip_input_index)
                clip_input_index[clip.clip_id] = input_index

                if clip.metadata.get("_asset_kind") == "image":
                    command.extend(["-loop", "1", "-framerate", "30", "-i", str(source)])
                else:
                    command.extend(["-i", str(source)])

            filters: list[str] = []
            current_video = "0:v"

            for idx, clip in enumerate(ordered_visuals):
                input_index = clip_input_index[clip.clip_id]
                source_start = _ticks_to_seconds(
                    clip.source_start, plan.timebase_numerator, plan.timebase_denominator
                )
                source_duration = _ticks_to_seconds(
                    clip.source_duration, plan.timebase_numerator, plan.timebase_denominator
                )
                target_duration = _ticks_to_seconds(
                    clip.duration, plan.timebase_numerator, plan.timebase_denominator
                )
                timeline_start = _ticks_to_seconds(
                    clip.timeline_start, plan.timebase_numerator, plan.timebase_denominator
                )

                transform = clip.metadata.get("_transform", {})
                scale = float(transform.get("scale", 1.0))
                pos_x = float(transform.get("position_x", 0.0))
                pos_y = float(transform.get("position_y", 0.0))
                rotation = float(transform.get("rotation_deg", 0.0))
                opacity = float(transform.get("opacity", 1.0))
                if not 0 <= opacity <= 1:
                    raise RenderExecutionError("opacity must be between 0 and 1")

                source_label = f"{input_index}:v"
                prepared = f"vprep{idx}"
                rotation_radians = rotation * math.pi / 180.0

                # Fades are evaluated before the clip is shifted onto the timeline.
                # This keeps transition times clip-local: fade-in starts at zero and
                # fade-out starts at target_duration - fade_out.
                visual_filter = (
                    f"[{source_label}]"
                    f"trim=start={source_start:.6f}:duration={source_duration:.6f},"
                    f"setpts=(PTS-STARTPTS)/{clip.playback_rate},"
                    f"trim=duration={target_duration:.6f},"
                    f"scale={plan.width}:{plan.height}:force_original_aspect_ratio=decrease,"
                    f"scale=iw*{scale:.8f}:ih*{scale:.8f},"
                    "format=rgba,"
                )
                if abs(rotation) > 0.000001:
                    visual_filter += (
                        f"rotate={rotation_radians:.10f}:"
                        "ow=rotw(iw):oh=roth(ih):c=none,"
                    )
                fade_in = _transition_seconds(
                    clip.transition_in,
                    numerator=plan.timebase_numerator,
                    denominator=plan.timebase_denominator,
                    clip_duration_sec=target_duration,
                )
                fade_out = _transition_seconds(
                    clip.transition_out,
                    numerator=plan.timebase_numerator,
                    denominator=plan.timebase_denominator,
                    clip_duration_sec=target_duration,
                )
                if fade_in > 0:
                    visual_filter += f"fade=t=in:st=0:d={fade_in:.6f}:alpha=1,"
                if fade_out > 0:
                    fade_out_start = max(0.0, target_duration - fade_out)
                    visual_filter += (
                        f"fade=t=out:st={fade_out_start:.6f}:"
                        f"d={fade_out:.6f}:alpha=1,"
                    )
                visual_filter += (
                    f"colorchannelmixer=aa={opacity:.8f},"
                    f"setpts=PTS+{timeline_start:.6f}/TB"
                    f"[{prepared}]"
                )
                filters.append(visual_filter)

                out_label = f"vout{idx}"
                filters.append(
                    f"[{current_video}][{prepared}]"
                    f"overlay=x='(W-w)/2+{pos_x:.4f}':"
                    f"y='(H-h)/2+{pos_y:.4f}':"
                    "eof_action=pass:shortest=0"
                    f"[{out_label}]"
                )
                current_video = out_label

            audio_labels = ["1:a"]
            for idx, clip in enumerate(audio_clips):
                input_index = clip_input_index[clip.clip_id]
                source_start = _ticks_to_seconds(
                    clip.source_start, plan.timebase_numerator, plan.timebase_denominator
                )
                source_duration = _ticks_to_seconds(
                    clip.source_duration, plan.timebase_numerator, plan.timebase_denominator
                )
                target_duration = _ticks_to_seconds(
                    clip.duration, plan.timebase_numerator, plan.timebase_denominator
                )
                delay_ms = round(
                    _ticks_to_seconds(
                        clip.timeline_start,
                        plan.timebase_numerator,
                        plan.timebase_denominator,
                    )
                    * 1000
                )
                label = f"amixsrc{idx}"
                fade_in = _transition_seconds(
                    clip.transition_in,
                    numerator=plan.timebase_numerator,
                    denominator=plan.timebase_denominator,
                    clip_duration_sec=target_duration,
                )
                fade_out = _transition_seconds(
                    clip.transition_out,
                    numerator=plan.timebase_numerator,
                    denominator=plan.timebase_denominator,
                    clip_duration_sec=target_duration,
                )
                audio_filter = (
                    f"[{input_index}:a]"
                    f"atrim=start={source_start:.6f}:duration={source_duration:.6f},"
                    "asetpts=PTS-STARTPTS,"
                    f"{_atempo_chain(clip.playback_rate)},"
                    f"atrim=duration={target_duration:.6f},"
                )
                if fade_in > 0:
                    audio_filter += f"afade=t=in:st=0:d={fade_in:.6f},"
                if fade_out > 0:
                    audio_filter += (
                        f"afade=t=out:st={max(0.0, target_duration - fade_out):.6f}:"
                        f"d={fade_out:.6f},"
                    )
                audio_filter += (
                    f"volume={clip.volume:.8f},"
                    f"adelay={delay_ms}|{delay_ms}"
                    f"[{label}]"
                )
                filters.append(audio_filter)
                audio_labels.append(label)

            mix_inputs = "".join(f"[{label}]" for label in audio_labels)
            filters.append(
                f"{mix_inputs}amix=inputs={len(audio_labels)}:"
                f"duration=longest:normalize=0,"
                f"atrim=duration={duration_sec:.6f},"
                "aresample=48000[aout]"
            )

            filter_complex = ";".join(filters)
            command.extend(
                [
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    f"[{current_video}]",
                    "-map",
                    "[aout]",
                    "-t",
                    f"{duration_sec:.6f}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(composed),
                ]
            )
            _run(command)

        if plan.captions:
            srt_path = root / "captions.srt"
            _write_srt(plan, srt_path)
            _run(
                [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-i",
                    str(composed),
                    "-vf",
                    f"subtitles='{_escape_filter_path(srt_path)}'",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )
        else:
            output_path.write_bytes(composed.read_bytes())

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RenderExecutionError("renderer did not produce a valid output file")

    return {
        "bytes": output_path.stat().st_size,
        "duration_sec": duration_sec,
        "visual_clip_count": len(visual_clips),
        "audio_source_count": len(audio_clips),
        "caption_count": len(plan.captions),
    }
