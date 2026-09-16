"""FFmpeg execution for deterministic ShortCut AI render plans.

This executor supports:
- multiple video/overlay clips and tracks
- overlapping visual clips via ordered compositing
- clip transforms: scale, position, rotation, opacity
- source audio plus standalone audio-track mixing
- deterministic speech-responsive music ducking via sidechain compression
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
from services.caption_rendering import build_ass_document
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


def _is_speech_sidechain_source(clip) -> bool:
    """Return whether this clip should drive music ducking.

    Create For Me speech normally comes from the primary video track. Explicit
    voiceover/speech metadata allows future standalone narration to opt in
    without treating sound effects or unrelated audio tracks as speech.
    """
    if clip.volume <= 0:
        return False
    if clip.ducking and clip.ducking.enabled:
        return False
    if clip.track_kind == "video":
        return bool(clip.metadata.get("_asset_audio_codec"))
    return bool(
        clip.metadata.get("speech_source")
        or clip.metadata.get("voiceover")
    )


def _sidechain_options(ducking) -> str:
    return (
        f"threshold={ducking.threshold:.8f}:"
        f"ratio={ducking.ratio:.8f}:"
        f"attack={ducking.attack_ms:.6f}:"
        f"release={ducking.release_ms:.6f}:"
        f"makeup={ducking.makeup:.8f}"
    )


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

            prepared_audio: list[tuple[object, str]] = []
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
                    "aresample=48000,"
                    "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"adelay={delay_ms}|{delay_ms}"
                    f"[{label}]"
                )
                filters.append(audio_filter)
                prepared_audio.append((clip, label))

            ducked_audio = [
                (clip, label)
                for clip, label in prepared_audio
                if clip.ducking and clip.ducking.enabled
            ]
            speech_audio = [
                (clip, label)
                for clip, label in prepared_audio
                if _is_speech_sidechain_source(clip)
            ]

            final_audio_labels: list[str] = ["1:a"]
            if ducked_audio and speech_audio:
                speech_input_labels = "".join(
                    f"[{label}]" for _, label in speech_audio
                )
                if len(speech_audio) == 1:
                    speech_bus = speech_audio[0][1]
                else:
                    speech_bus = "speechbus"
                    filters.append(
                        f"{speech_input_labels}amix=inputs={len(speech_audio)}:"
                        "duration=longest:normalize=0"
                        f"[{speech_bus}]"
                    )

                split_outputs = ["speechfinal"] + [
                    f"speechsc{index}" for index in range(len(ducked_audio))
                ]
                split_labels = "".join(f"[{label}]" for label in split_outputs)
                filters.append(
                    f"[{speech_bus}]asplit={len(split_outputs)}{split_labels}"
                )
                final_audio_labels.append("speechfinal")

                speech_label_set = {label for _, label in speech_audio}
                ducked_label_set = {label for _, label in ducked_audio}
                for clip, label in prepared_audio:
                    if label not in speech_label_set and label not in ducked_label_set:
                        final_audio_labels.append(label)

                for index, (clip, label) in enumerate(ducked_audio):
                    ducked_label = f"duckedmusic{index}"
                    filters.append(
                        f"[{label}][speechsc{index}]"
                        f"sidechaincompress={_sidechain_options(clip.ducking)}"
                        f"[{ducked_label}]"
                    )
                    final_audio_labels.append(ducked_label)
            else:
                final_audio_labels.extend(label for _, label in prepared_audio)

            mix_inputs = "".join(f"[{label}]" for label in final_audio_labels)
            filters.append(
                f"{mix_inputs}amix=inputs={len(final_audio_labels)}:"
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
            ass_path = root / "captions.ass"
            ass_path.write_text(build_ass_document(plan), encoding="utf-8")
            _run(
                [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-i",
                    str(composed),
                    "-vf",
                    f"subtitles='{_escape_filter_path(ass_path)}'",
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
        "ducked_audio_source_count": len(ducked_audio),
        "caption_count": len(plan.captions),
    }
