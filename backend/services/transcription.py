"""Provider abstraction for speech transcription.

The production adapter uses the OpenAI-compatible audio transcription REST API
and requests verbose JSON with segment/word timestamps. Tests can inject a
fake provider through the same protocol.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import httpx

from core.config import settings


class TranscriptionError(RuntimeError):
    pass


class TranscriptionProvider(Protocol):
    async def transcribe(self, audio_path: Path) -> dict: ...


class OpenAITranscriptionProvider:
    async def transcribe(self, audio_path: Path) -> dict:
        if not settings.OPENAI_API_KEY:
            raise TranscriptionError("OPENAI_API_KEY is required for transcription")

        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        data = {
            "model": settings.TRANSCRIPTION_MODEL,
            "response_format": "verbose_json",
            "timestamp_granularities[]": ["word", "segment"],
        }
        try:
            async with httpx.AsyncClient(timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC) as client:
                with audio_path.open("rb") as handle:
                    response = await client.post(
                        f"{settings.OPENAI_API_BASE.rstrip('/')}/audio/transcriptions",
                        headers=headers,
                        data=data,
                        files={"file": (audio_path.name, handle, "audio/wav")},
                    )
        except httpx.HTTPError as exc:
            raise TranscriptionError(str(exc)) from exc

        if response.status_code >= 400:
            raise TranscriptionError(
                f"transcription provider returned {response.status_code}: {response.text[:1000]}"
            )
        payload = response.json()
        return {
            "text": payload.get("text", ""),
            "language": payload.get("language"),
            "words": payload.get("words") or [],
            "segments": payload.get("segments") or [],
            "provider": "openai-compatible",
            "model": settings.TRANSCRIPTION_MODEL,
        }


def get_transcription_provider() -> TranscriptionProvider:
    provider = settings.TRANSCRIPTION_PROVIDER.lower()
    if provider == "openai":
        return OpenAITranscriptionProvider()
    raise TranscriptionError(f"unsupported transcription provider: {provider}")
