"""Real database/render pipeline with deterministic, test-only intelligence.

This verifies orchestration, not live model accuracy or provider credentials.
"""

import asyncio
from pathlib import Path
import subprocess
import uuid
import pytest


def test_server_pipeline_completes_without_a_connected_client(monkeypatch, tmp_path):
    from core.config import settings
    from core.security import utc_now
    from db import mongo
    from models.ai_plan import CreateAIEditPlanRequest
    from routers.pipeline import start_pipeline
    from routers.project_state import _get_or_create_state
    from services import ai_edit_planner, storage
    from workers import pipeline_worker, render_worker

    # Separate connection per event loop; the server's real MongoDB is used.
    mongo._client = None
    mongo._db = None
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setattr(settings, "STUB_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "_storage", None)

    class TestEmbedder:
        async def embed(self, texts):
            return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(
        ai_edit_planner, "get_embedding_provider", lambda: TestEmbedder()
    )
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=green:s=160x90:d=6:r=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=300:duration=6",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        timeout=30,
    )

    async def scenario():
        db = mongo.get_db()
        uid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        now = utc_now()
        user = {"id": uid, "subscription_tier": "free"}
        await db.users.insert_one({**user, "email": f"{uid}@test.example"})
        await db.projects.insert_one(
            {
                "id": pid,
                "user_id": uid,
                "archived": False,
                "title": "Test pipeline",
                "content_type": "podcast",
                "prompt": "Explain a useful lesson",
                "target_platforms": ["ig_reels"],
            }
        )
        state = await _get_or_create_state(pid, uid)
        state["sequences"][0].update(width=160, height=90)
        await db.project_states.replace_one({"project_id": pid}, state)
        await db.assets.insert_one(
            {
                "id": aid,
                "user_id": uid,
                "project_id": pid,
                "kind": "video",
                "filename": "source.mp4",
                "storage_key": "source.mp4",
                "duration_sec": 6.0,
                "processing_status": "ready",
                "upload_status": "uploaded",
                "media_metadata": {"audio_codec": "aac"},
            }
        )
        await db.media_intelligence.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": uid,
                "project_id": pid,
                "asset_id": aid,
                "status": "completed",
                "embedding_model": settings.EMBEDDING_MODEL,
                "semantic_units": [
                    {
                        "start": 0.0,
                        "end": 6.0,
                        "text": "Here is a useful lesson: start small, test your idea, and improve every day.",
                    }
                ],
                "semantic_vectors": [[1.0, 0.0, 0.0]],
                "segments": [],
                "words": [],
                "created_at": now,
            }
        )
        body = CreateAIEditPlanRequest(target_duration_sec=5, include_captions=True)
        job = await start_pipeline(pid, body, user)
        duplicate = await start_pipeline(pid, body, user)
        assert duplicate.id == job.id

        # The client makes no further calls after enqueueing.
        async def render_loop():
            while True:
                await render_worker.process_one()
                await asyncio.sleep(0.05)

        renderer = asyncio.create_task(render_loop())
        try:
            assert await asyncio.wait_for(pipeline_worker.process_one(), timeout=60)
        finally:
            renderer.cancel()
            try:
                await renderer
            except asyncio.CancelledError:
                pass
        finished = await db.jobs.find_one({"id": job.id})
        assert finished["status"] == "succeeded", finished
        export = await db.exports.find_one({"id": finished["result"]["export_id"]})
        assert export["status"] == "completed"
        assert export["project_state_version"] == 2
        assert storage.get_storage().exists(export["storage_key"])
        await mongo.close()

    asyncio.run(scenario())
