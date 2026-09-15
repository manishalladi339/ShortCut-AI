"""FFprobe adapter for media metadata extraction."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from core.config import settings


class MediaProbeError(RuntimeError):
    pass


def probe(path: Path) -> dict[str, Any]:
    command = [
        settings.FFPROBE_PATH,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.MEDIA_PROBE_TIMEOUT_SEC,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaProbeError("ffprobe is not installed or FFPROBE_PATH is invalid") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError("ffprobe timed out") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or "ffprobe failed").strip()
        raise MediaProbeError(detail)

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("ffprobe returned invalid JSON") from exc

    streams = payload.get("streams", [])
    format_info = payload.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def _float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    duration = _float(format_info.get("duration"))
    if duration is None:
        duration = _float((video or audio or {}).get("duration"))

    return {
        "duration_sec": duration,
        "width": (video or {}).get("width"),
        "height": (video or {}).get("height"),
        "video_codec": (video or {}).get("codec_name"),
        "audio_codec": (audio or {}).get("codec_name"),
        "sample_rate": int(audio["sample_rate"]) if audio and str(audio.get("sample_rate", "")).isdigit() else None,
        "channels": (audio or {}).get("channels"),
        "format_name": format_info.get("format_name"),
        "bit_rate": int(format_info["bit_rate"]) if str(format_info.get("bit_rate", "")).isdigit() else None,
    }
