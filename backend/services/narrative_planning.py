"""Narrative structuring for grounded edit-plan candidates.

A deterministic baseline is always available. An OpenAI-compatible provider can
optionally refine ordering and audience framing without inventing new source clips.
"""
from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from core.config import settings


class NarrativePlanningError(RuntimeError):
    pass


class NarrativeProvider(Protocol):
    async def structure(
        self,
        *,
        objective: str,
        project: dict,
        candidates: list[dict],
        target_audience: str | None,
        project_intelligence: dict | None = None,
    ) -> dict: ...


def _candidate_key(item: dict) -> str:
    return f"{item['asset_id']}:{item['unit_index']}"


def deterministic_structure(
    *,
    objective: str,
    project: dict,
    candidates: list[dict],
    target_audience: str | None,
    project_intelligence: dict | None = None,
) -> dict:
    if not candidates:
        return {
            "audience_profile": {},
            "narrative_summary": "",
            "ordered_keys": [],
            "roles": {},
            "caption_suggestion": "",
            "cta_suggestion": "",
        }

    ranked = sorted(
        candidates,
        key=lambda item: (-item["final_score"], item["asset_id"], item["start"]),
    )

    hook = ranked[0]
    remaining = ranked[1:]
    payoff = None
    payoff_terms = (
        "result", "therefore", "so", "finally", "lesson", "because",
        "what happened", "the answer", "that is why", "this is why",
    )
    for item in remaining:
        text = item["text"].lower()
        if any(term in text for term in payoff_terms):
            payoff = item
            break
    if payoff is None and remaining:
        payoff = remaining[-1]

    body_items = [
        item for item in candidates
        if item is not hook and item is not payoff
    ]
    body_items.sort(key=lambda item: (item["asset_id"], item["start"]))

    ordered = [hook, *body_items]
    if payoff is not None:
        ordered.append(payoff)

    roles: dict[str, str] = {}
    for index, item in enumerate(ordered):
        key = _candidate_key(item)
        if index == 0:
            roles[key] = "hook"
        elif index == len(ordered) - 1 and len(ordered) > 1:
            roles[key] = "payoff"
        else:
            roles[key] = "body"

    platforms = project.get("target_platforms") or []
    audience_profile = {
        "description": (
            target_audience.strip()
            if target_audience and target_audience.strip()
            else "General audience aligned to the project objective"
        ),
        "platforms": platforms,
        "content_type": project.get("content_type"),
        "desired_style": project.get("desired_style"),
    }
    hook_text = hook["text"].strip()
    caption = hook_text if len(hook_text) <= 140 else hook_text[:137].rstrip() + "..."
    cta = "Watch to the end for the key takeaway." if len(ordered) > 1 else ""

    return {
        "audience_profile": audience_profile,
        "narrative_summary": (
            "Open with the strongest grounded hook, progress through supporting "
            "evidence across the project"
            + (
                f" and its {len(project_intelligence.get('topic_clusters') or [])} "
                "identified topic clusters"
                if project_intelligence
                else ""
            )
            + ", and close on a payoff/takeaway."
        ),
        "ordered_keys": [_candidate_key(item) for item in ordered],
        "roles": roles,
        "caption_suggestion": caption,
        "cta_suggestion": cta,
        "provider": "deterministic",
        "model": None,
    }


class OpenAINarrativeProvider:
    async def structure(
        self,
        *,
        objective: str,
        project: dict,
        candidates: list[dict],
        target_audience: str | None,
        project_intelligence: dict | None = None,
    ) -> dict:
        if not settings.OPENAI_API_KEY:
            raise NarrativePlanningError("OPENAI_API_KEY is required for narrative planning")

        candidate_rows = [
            {
                "key": _candidate_key(item),
                "text": item["text"],
                "score": item["final_score"],
                "start": item["start"],
                "end": item["end"],
            }
            for item in candidates
        ]
        prompt = {
            "objective": objective,
            "target_audience": target_audience,
            "project": {
                "content_type": project.get("content_type"),
                "desired_style": project.get("desired_style"),
                "target_platforms": project.get("target_platforms") or [],
            },
            "project_intelligence": {
                "summary": (project_intelligence or {}).get("summary"),
                "topic_clusters": [
                    {
                        "id": topic.get("id"),
                        "label": topic.get("label"),
                        "unit_count": topic.get("unit_count"),
                        "asset_ids": topic.get("asset_ids") or [],
                    }
                    for topic in ((project_intelligence or {}).get("topic_clusters") or [])[:8]
                ],
                "visual_library": (project_intelligence or {}).get("visual_library") or {},
            },
            "candidates": candidate_rows,
            "rules": [
                "Use only the supplied candidate keys.",
                "Do not invent source material.",
                "Every candidate may appear at most once.",
                "Assign each selected key one of: hook, body, payoff.",
                "Prefer a coherent story over raw score order.",
                "Return valid JSON only.",
            ],
            "output_schema": {
                "audience_profile": {
                    "description": "string",
                    "needs": ["string"],
                    "platforms": ["string"],
                },
                "narrative_summary": "string",
                "ordered_keys": ["candidate-key"],
                "roles": {"candidate-key": "hook|body|payoff"},
                "caption_suggestion": "string",
                "cta_suggestion": "string",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=settings.AI_PLANNER_TIMEOUT_SEC) as client:
                response = await client.post(
                    f"{settings.OPENAI_API_BASE.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.NARRATIVE_MODEL,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You are a grounded video narrative planner. "
                                    "Never invent clips or facts not present in the supplied candidates."
                                ),
                            },
                            {"role": "user", "content": json.dumps(prompt)},
                        ],
                    },
                )
        except httpx.HTTPError as exc:
            raise NarrativePlanningError(str(exc)) from exc

        if response.status_code >= 400:
            raise NarrativePlanningError(
                f"narrative provider returned {response.status_code}: "
                f"{response.text[:1200]}"
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise NarrativePlanningError("narrative provider returned invalid JSON") from exc

        valid_keys = {_candidate_key(item) for item in candidates}
        ordered_keys = result.get("ordered_keys") or []
        if (
            not ordered_keys
            or len(ordered_keys) != len(set(ordered_keys))
            or any(key not in valid_keys for key in ordered_keys)
        ):
            raise NarrativePlanningError("narrative provider returned invalid candidate ordering")

        roles = result.get("roles") or {}
        allowed_roles = {"hook", "body", "payoff"}
        for key in ordered_keys:
            if roles.get(key) not in allowed_roles:
                raise NarrativePlanningError("narrative provider returned invalid role assignment")

        result["provider"] = "openai-compatible"
        result["model"] = settings.NARRATIVE_MODEL
        return result


async def structure_narrative(
    *,
    objective: str,
    project: dict,
    candidates: list[dict],
    target_audience: str | None,
    project_intelligence: dict | None = None,
) -> dict:
    provider = settings.NARRATIVE_PROVIDER.lower()
    if provider == "deterministic":
        return deterministic_structure(
            objective=objective,
            project=project,
            candidates=candidates,
            target_audience=target_audience,
            project_intelligence=project_intelligence,
        )
    if provider == "openai":
        return await OpenAINarrativeProvider().structure(
            objective=objective,
            project=project,
            candidates=candidates,
            target_audience=target_audience,
        )
    raise NarrativePlanningError(f"unsupported narrative provider: {provider}")
