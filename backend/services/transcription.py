"""Provider abstraction for speech transcription and optional diarization."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import wave
from typing import Protocol

import httpx

from core.config import settings


class TranscriptionError(RuntimeError):
    pass


class TranscriptionProvider(Protocol):
    async def transcribe(self, audio_path: Path) -> dict: ...


class OpenAITranscriptionProvider:
    CHUNK_SECONDS = 600

    async def transcribe(self, audio_path: Path) -> dict:
        # Workers extract mono 16 kHz PCM. Ten-minute WAV chunks stay below
        # the provider upload limit and preserve absolute source timestamps.
        with wave.open(str(audio_path), "rb") as source:
            rate = source.getframerate()
            chunk_frames = int(rate * self.CHUNK_SECONDS)
            if source.getnframes() <= chunk_frames:
                return await self._transcribe_chunk(audio_path)
            merged = {
                "text": "",
                "words": [],
                "segments": [],
                "speakers": [],
                "diarized": False,
                "provider": "openai-compatible",
                "model": settings.TRANSCRIPTION_MODEL,
                "language": None,
            }
            texts = []
            with TemporaryDirectory(prefix="shortcut-speech-") as tmp:
                index = 0
                while True:
                    offset = source.tell() / rate
                    pcm = source.readframes(chunk_frames)
                    if not pcm:
                        break
                    path = Path(tmp) / f"part-{index}.wav"
                    with wave.open(str(path), "wb") as output:
                        output.setparams(source.getparams())
                        output.writeframes(pcm)
                    part = await self._transcribe_chunk(path)
                    texts.append(part.get("text", ""))
                    merged["language"] = merged["language"] or part.get("language")
                    merged["diarized"] = merged["diarized"] or part.get(
                        "diarized", False
                    )
                    for key in ("words", "segments"):
                        for row in part.get(key, []):
                            row = {
                                **row,
                                "start": row.get("start", 0) + offset,
                                "end": row.get("end", 0) + offset,
                            }
                            if row.get("speaker") is not None:
                                # Diarization IDs are local to each provider request.
                                row["speaker"] = f"part{index+1}:{row['speaker']}"
                            merged[key].append(row)
                    merged["speakers"].extend(
                        f"part{index+1}:{speaker}"
                        for speaker in part.get("speakers", [])
                    )
                    path.unlink()
                    index += 1
            merged["text"] = " ".join(texts).strip()
            return merged

    async def _transcribe_chunk(self, audio_path: Path) -> dict:
        if not settings.OPENAI_API_KEY:
            raise TranscriptionError("OPENAI_API_KEY is required for transcription")

        headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
        diarize = "transcribe-diarize" in settings.TRANSCRIPTION_MODEL.lower()
        if diarize:
            data = {
                "model": settings.TRANSCRIPTION_MODEL,
                "response_format": "diarized_json",
                "chunking_strategy": "auto",
            }
        else:
            data = {
                "model": settings.TRANSCRIPTION_MODEL,
                "response_format": "verbose_json",
                "timestamp_granularities[]": ["word", "segment"],
            }

        try:
            async with httpx.AsyncClient(
                timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC
            ) as client:
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
                f"transcription provider returned {response.status_code}: "
                f"{response.text[:1000]}"
            )

        payload = response.json()
        segments = payload.get("segments") or []
        speakers = sorted(
            {
                str(segment.get("speaker")).strip()
                for segment in segments
                if segment.get("speaker") not in (None, "")
            }
        )
        return {
            "text": payload.get("text", ""),
            "language": payload.get("language"),
            "words": payload.get("words") or [],
            "segments": segments,
            "speakers": speakers,
            "diarized": diarize,
            "provider": "openai-compatible",
            "model": settings.TRANSCRIPTION_MODEL,
        }


def get_transcription_provider() -> TranscriptionProvider:
    provider = settings.TRANSCRIPTION_PROVIDER.lower()
    if provider == "openai":
        return OpenAITranscriptionProvider()
    raise TranscriptionError(f"unsupported transcription provider: {provider}")
