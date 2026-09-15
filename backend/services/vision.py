"""Visual-understanding provider abstraction for representative video frames."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Protocol

import httpx

from core.config import settings


class VisionError(RuntimeError):
    pass


class VisionProvider(Protocol):
    async def analyze_frames(self, frames: list[dict]) -> list[dict]: ...


def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class OpenAIVisionProvider:
    async def analyze_frames(self, frames: list[dict]) -> list[dict]:
        if not frames:
            return []
        if not settings.OPENAI_API_KEY:
            raise VisionError("OPENAI_API_KEY is required for visual analysis")

        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Analyze these representative video frames in order. Return JSON only "
                    "with a top-level 'frames' array. Each item must include: index, "
                    "description, shot_type, people_count, visible_objects (array), "
                    "text_on_screen (string or null), and editing_notes (array). "
                    "Describe only what is visibly supported; do not infer identity."
                ),
            }
        ]
        for frame in frames:
            content.append(
                {
                    "type": "text",
                    "text": f"Frame index {frame['index']} at {frame['time']:.3f}s",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _data_url(frame["path"])},
                }
            )

        try:
            async with httpx.AsyncClient(timeout=settings.AI_PLANNER_TIMEOUT_SEC) as client:
                response = await client.post(
                    f"{settings.OPENAI_API_BASE.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.VISION_MODEL,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": content}],
                    },
                )
        except httpx.HTTPError as exc:
            raise VisionError(str(exc)) from exc

        if response.status_code >= 400:
            raise VisionError(
                f"vision provider returned {response.status_code}: {response.text[:1200]}"
            )

        try:
            payload = response.json()
            result = json.loads(payload["choices"][0]["message"]["content"])
            rows = result.get("frames") or []
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise VisionError("vision provider returned invalid JSON") from exc

        by_index = {int(frame["index"]): frame for frame in frames}
        normalized: list[dict] = []
        for row in rows:
            try:
                index = int(row["index"])
            except (KeyError, TypeError, ValueError):
                continue
            source = by_index.get(index)
            if source is None:
                continue
            normalized.append(
                {
                    "index": index,
                    "time": source["time"],
                    "description": str(row.get("description") or "").strip(),
                    "shot_type": str(row.get("shot_type") or "unknown").strip(),
                    "people_count": max(0, int(row.get("people_count") or 0)),
                    "visible_objects": [
                        str(item).strip()
                        for item in (row.get("visible_objects") or [])
                        if str(item).strip()
                    ],
                    "text_on_screen": (
                        str(row.get("text_on_screen")).strip()
                        if row.get("text_on_screen") not in (None, "")
                        else None
                    ),
                    "editing_notes": [
                        str(item).strip()
                        for item in (row.get("editing_notes") or [])
                        if str(item).strip()
                    ],
                    "provider": "openai-compatible",
                    "model": settings.VISION_MODEL,
                }
            )
        normalized.sort(key=lambda item: item["index"])
        return normalized


class DisabledVisionProvider:
    async def analyze_frames(self, frames: list[dict]) -> list[dict]:
        return [
            {
                "index": frame["index"],
                "time": frame["time"],
                "description": "",
                "shot_type": "unknown",
                "people_count": 0,
                "visible_objects": [],
                "text_on_screen": None,
                "editing_notes": [],
                "provider": "disabled",
                "model": None,
            }
            for frame in frames
        ]


def get_vision_provider() -> VisionProvider:
    provider = settings.VISION_PROVIDER.lower()
    if provider == "openai":
        return OpenAIVisionProvider()
    if provider == "disabled":
        return DisabledVisionProvider()
    raise VisionError(f"unsupported vision provider: {provider}")
