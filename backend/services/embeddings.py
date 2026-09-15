"""Embedding-provider abstraction for semantic retrieval."""
from __future__ import annotations

from typing import Protocol

import httpx

from core.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise EmbeddingError("embedding input cannot be empty")
        if not settings.OPENAI_API_KEY:
            raise EmbeddingError("OPENAI_API_KEY is required for embeddings")

        try:
            async with httpx.AsyncClient(timeout=settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC) as client:
                response = await client.post(
                    f"{settings.OPENAI_API_BASE.rstrip('/')}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.EMBEDDING_MODEL,
                        "input": cleaned,
                    },
                )
        except httpx.HTTPError as exc:
            raise EmbeddingError(str(exc)) from exc

        if response.status_code >= 400:
            raise EmbeddingError(
                f"embedding provider returned {response.status_code}: "
                f"{response.text[:1000]}"
            )

        payload = response.json()
        rows = sorted(payload.get("data") or [], key=lambda item: item["index"])
        vectors = [row.get("embedding") or [] for row in rows]
        if len(vectors) != len(cleaned) or any(not vector for vector in vectors):
            raise EmbeddingError("embedding provider returned incomplete vectors")
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    raise EmbeddingError(f"unsupported embedding provider: {provider}")
