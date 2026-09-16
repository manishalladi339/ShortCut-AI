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


def _normalized_box(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    try:
        x = float(value.get("x"))
        y = float(value.get("y"))
        width = float(value.get("width"))
        height = float(value.get("height"))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    width = max(0.001, min(1.0 - x, width))
    height = max(0.001, min(1.0 - y, height))
    if width <= 0 or height <= 0:
        return None
    return {
        "x": round(x, 6),
        "y": round(y, 6),
        "width": round(width, 6),
        "height": round(height, 6),
    }


def _normalized_subjects(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for index, item in enumerate(value[:8]):
        if not isinstance(item, dict):
            continue
        box = _normalized_box(item.get("box"))
        if not box:
            continue
        label = str(item.get("label") or f"person_{index + 1}").strip()[:80]
        try:
            prominence = max(0.0, min(1.0, float(item.get("prominence") or 0.0)))
        except (TypeError, ValueError):
            prominence = 0.0
        raw_speaking = item.get("speaking_likelihood")
        try:
            speaking = (
                max(0.0, min(1.0, float(raw_speaking)))
                if raw_speaking is not None
                else None
            )
        except (TypeError, ValueError):
            speaking = None
        result.append(
            {
                "label": label or f"person_{index + 1}",
                "box": box,
                "prominence": round(prominence, 4),
                "speaking_likelihood": (
                    round(speaking, 4) if speaking is not None else None
                ),
            }
        )
    return result


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
                    "text_on_screen (string or null), editing_notes (array), and subjects "
                    "(array). subjects should contain only clearly visible people. Each "
                    "subject must have a frame-local label, box={x,y,width,height} using "
                    "normalized 0..1 coordinates, prominence 0..1, and "
                    "speaking_likelihood 0..1 or null. speaking_likelihood may use only "
                    "visible mouth/posture cues in that frame. Do not infer names, identity, "
                    "or link a person across frames."
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
                    "subjects": _normalized_subjects(row.get("subjects")),
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
                "subjects": [],
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
