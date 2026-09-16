"""Two-pass FFmpeg loudness mastering for finished ShortCut renders."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.config import settings


class AudioMasteringError(RuntimeError):
    pass


_LOUDNORM_JSON_RE = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.DOTALL)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AudioMasteringError(f"invalid loudness measurement: {value!r}") from exc


def parse_loudnorm_json(stderr: str) -> dict[str, float | str]:
    """Extract the final loudnorm JSON object from FFmpeg stderr."""
    matches = _LOUDNORM_JSON_RE.findall(stderr or "")
    if not matches:
        raise AudioMasteringError("ffmpeg loudnorm did not return measurement JSON")

    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError as exc:
        raise AudioMasteringError("ffmpeg loudnorm returned invalid JSON") from exc

    required = (
        "input_i",
        "input_tp",
        "input_lra",
        "input_thresh",
        "output_i",
        "output_tp",
        "output_lra",
        "output_thresh",
        "target_offset",
    )
    for key in required:
        if key not in payload:
            raise AudioMasteringError(f"loudnorm measurement missing {key}")

    return {
        "input_i": _float(payload["input_i"]),
        "input_tp": _float(payload["input_tp"]),
        "input_lra": _float(payload["input_lra"]),
        "input_thresh": _float(payload["input_thresh"]),
        "output_i": _float(payload["output_i"]),
        "output_tp": _float(payload["output_tp"]),
        "output_lra": _float(payload["output_lra"]),
        "output_thresh": _float(payload["output_thresh"]),
        "target_offset": _float(payload["target_offset"]),
        "normalization_type": str(payload.get("normalization_type") or ""),
    }


def has_measurable_signal(measurement: dict[str, float | str]) -> bool:
    """Return whether first-pass loudness values can safely drive pass two."""
    numeric_keys = (
        "input_i",
        "input_tp",
        "input_lra",
        "input_thresh",
        "target_offset",
    )
    return all(math.isfinite(float(measurement[key])) for key in numeric_keys)


def build_measure_filter(
    *,
    target_lufs: float,
    true_peak_dbtp: float,
    loudness_range: float,
) -> str:
    return (
        f"loudnorm=I={target_lufs:.2f}:"
        f"TP={true_peak_dbtp:.2f}:"
        f"LRA={loudness_range:.2f}:"
        "print_format=json"
    )


def build_master_filter(
    measurement: dict[str, float | str],
    *,
    target_lufs: float,
    true_peak_dbtp: float,
    loudness_range: float,
) -> str:
    return (
        f"loudnorm=I={target_lufs:.2f}:"
        f"TP={true_peak_dbtp:.2f}:"
        f"LRA={loudness_range:.2f}:"
        f"measured_I={float(measurement['input_i']):.4f}:"
        f"measured_TP={float(measurement['input_tp']):.4f}:"
        f"measured_LRA={float(measurement['input_lra']):.4f}:"
        f"measured_thresh={float(measurement['input_thresh']):.4f}:"
        f"offset={float(measurement['target_offset']):.4f}:"
        "linear=true:"
        "print_format=json"
    )


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.RENDER_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AudioMasteringError(
            "ffmpeg is not installed or FFMPEG_PATH is invalid"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioMasteringError("audio mastering timed out") from exc

    if completed.returncode != 0:
        raise AudioMasteringError(
            (completed.stderr or "ffmpeg audio mastering failed").strip()[-6000:]
        )
    return completed


def master_audio(input_path: Path, output_path: Path) -> dict:
    """Master the first audio stream and copy the already-rendered video stream."""
    target_lufs = float(settings.AUDIO_TARGET_LUFS)
    true_peak = float(settings.AUDIO_TRUE_PEAK_DBTP)
    loudness_range = float(settings.AUDIO_TARGET_LRA)

    first_pass = _run(
        [
            settings.FFMPEG_PATH,
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-map",
            "0:a:0",
            "-af",
            build_measure_filter(
                target_lufs=target_lufs,
                true_peak_dbtp=true_peak,
                loudness_range=loudness_range,
            ),
            "-f",
            "null",
            "-",
        ]
    )
    measured = parse_loudnorm_json(first_pass.stderr or "")

    if not has_measurable_signal(measured):
        shutil.copyfile(input_path, output_path)
        return {
            "status": "skipped_no_signal",
            "target_lufs": target_lufs,
            "target_true_peak_dbtp": true_peak,
            "target_lra": loudness_range,
            "before": {
                "integrated_lufs": measured["input_i"],
                "true_peak_dbtp": measured["input_tp"],
                "lra": measured["input_lra"],
            },
            "after": None,
        }

    second_pass = _run(
        [
            settings.FFMPEG_PATH,
            "-y",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c:v",
            "copy",
            "-af",
            build_master_filter(
                measured,
                target_lufs=target_lufs,
                true_peak_dbtp=true_peak,
                loudness_range=loudness_range,
            ),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    applied = parse_loudnorm_json(second_pass.stderr or "")

    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise AudioMasteringError("audio mastering did not produce an output file")

    return {
        "status": "applied",
        "target_lufs": target_lufs,
        "target_true_peak_dbtp": true_peak,
        "target_lra": loudness_range,
        "normalization_type": applied.get("normalization_type") or "",
        "before": {
            "integrated_lufs": measured["input_i"],
            "true_peak_dbtp": measured["input_tp"],
            "lra": measured["input_lra"],
        },
        "after": {
            "integrated_lufs": applied["output_i"],
            "true_peak_dbtp": applied["output_tp"],
            "lra": applied["output_lra"],
        },
    }
