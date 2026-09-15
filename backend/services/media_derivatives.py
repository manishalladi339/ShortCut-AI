"""FFmpeg-derived media artifacts: proxy, thumbnail and waveform."""
from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from core.config import settings
from services.storage import StorageBackend


class MediaDerivativeError(RuntimeError):
    pass


def _run(command: list[str], timeout: int) -> None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise MediaDerivativeError("ffmpeg is not installed or FFMPEG_PATH is invalid") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaDerivativeError("ffmpeg derivative generation timed out") from exc

    if completed.returncode != 0:
        raise MediaDerivativeError((completed.stderr or "ffmpeg failed").strip()[-2000:])


def generate(
    *,
    source_path: Path,
    asset: dict,
    storage: StorageBackend,
) -> dict[str, Any]:
    """Generate practical editing derivatives and upload them to object storage."""
    with TemporaryDirectory(prefix="shortcut-derivatives-") as tmp:
        root = Path(tmp)
        results: dict[str, Any] = {}
        base = f"users/{asset['user_id']}/derived/{asset['id']}"

        if asset["kind"] in {"video", "image"}:
            thumb = root / "thumbnail.jpg"
            if asset["kind"] == "video":
                command = [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-ss",
                    "00:00:00.500",
                    "-i",
                    str(source_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:-2",
                    str(thumb),
                ]
            else:
                command = [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-i",
                    str(source_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:-2",
                    str(thumb),
                ]
            _run(command, settings.MEDIA_DERIVATIVE_TIMEOUT_SEC)
            key = f"{base}/thumbnail.jpg"
            storage.upload_file(key, thumb, content_type="image/jpeg")
            results["thumbnail"] = {"storage_key": key, "mime_type": "image/jpeg"}

        if asset["kind"] == "video":
            proxy = root / "proxy.mp4"
            _run(
                [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-i",
                    str(source_path),
                    "-vf",
                    "scale='min(1280,iw)':-2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "25",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(proxy),
                ],
                settings.MEDIA_DERIVATIVE_TIMEOUT_SEC,
            )
            key = f"{base}/proxy.mp4"
            storage.upload_file(key, proxy, content_type="video/mp4")
            results["proxy"] = {"storage_key": key, "mime_type": "video/mp4"}

        if asset["kind"] in {"video", "audio"}:
            waveform = root / "waveform.png"
            _run(
                [
                    settings.FFMPEG_PATH,
                    "-y",
                    "-i",
                    str(source_path),
                    "-filter_complex",
                    "showwavespic=s=1200x240:split_channels=1",
                    "-frames:v",
                    "1",
                    str(waveform),
                ],
                settings.MEDIA_DERIVATIVE_TIMEOUT_SEC,
            )
            key = f"{base}/waveform.png"
            storage.upload_file(key, waveform, content_type="image/png")
            results["waveform"] = {"storage_key": key, "mime_type": "image/png"}

        return results
