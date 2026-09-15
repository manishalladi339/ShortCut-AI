"""Audio extraction for speech/media intelligence."""
from __future__ import annotations

import subprocess
from pathlib import Path

from core.config import settings


class AudioExtractError(RuntimeError):
    pass


def extract_mono_16k(source: Path, destination: Path) -> None:
    command = [
        settings.FFMPEG_PATH,
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise AudioExtractError(str(exc)) from exc
    if completed.returncode != 0:
        raise AudioExtractError((completed.stderr or "audio extraction failed")[-3000:])
