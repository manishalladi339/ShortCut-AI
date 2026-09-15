"""Media-intelligence worker: audio, speech, scenes, vision and embeddings."""
from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from core.security import utc_now
from db.mongo import close as close_mongo
from db.mongo import get_db
from models.job import JobType
from services import job_service
from services.audio_extract import extract_mono_16k
from services.broll_planning import visual_text
from services.embeddings import get_embedding_provider
from services.frame_sampler import extract_frames
from services.scene_detection import detect_scenes
from services.semantic_units import build_semantic_units
from services.storage import materialize
from services.transcription import get_transcription_provider
from services.vision import get_vision_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.intelligence-worker")


def _normalize_words(words: list[dict]) -> list[dict]:
    normalized = []
    for item in words:
        text = str(item.get("word") or item.get("text") or "").strip()
        if text:
            normalized.append({"start": float(item.get("start", 0.0)), "end": float(item.get("end", item.get("start", 0.0))), "text": text, "speaker": item.get("speaker")})
    return normalized


def _normalize_segments(segments: list[dict]) -> list[dict]:
    normalized = []
    for item in segments:
        text = str(item.get("text") or "").strip()
        if text:
            normalized.append({"start": float(item.get("start", 0.0)), "end": float(item.get("end", item.get("start", 0.0))), "text": text, "speaker": item.get("speaker")})
    return normalized


async def process_one() -> bool:
    from core.config import settings
    job = await job_service.claim_next(JobType.media_intelligence)
    if not job:
        return False
    db = get_db()
    intelligence_id = job.get("payload", {}).get("intelligence_id")
    try:
        record = await db.media_intelligence.find_one({"id": intelligence_id, "user_id": job["user_id"]}, {"_id": 0})
        asset = await db.assets.find_one({"id": job["asset_id"], "user_id": job["user_id"]}, {"_id": 0})
        if not record or not asset:
            raise RuntimeError("analysis record or asset no longer exists")
        await db.media_intelligence.update_one({"id": intelligence_id}, {"$set": {"status": "running", "updated_at": utc_now()}})

        with TemporaryDirectory(prefix="shortcut-intelligence-") as tmp:
            root = Path(tmp)
            suffix = Path(asset["filename"]).suffix
            with materialize(asset["storage_key"], suffix=suffix) as source:
                audio = root / "speech.wav"
                await job_service.set_progress(job["id"], 15)
                extract_mono_16k(source, audio)
                await job_service.set_progress(job["id"], 35)
                transcript = await get_transcription_provider().transcribe(audio)
                scenes, visual_observations = [], []
                if asset["kind"] == "video":
                    await job_service.set_progress(job["id"], 55)
                    scenes = detect_scenes(source, asset.get("duration_sec"))
                    await job_service.set_progress(job["id"], 65)
                    frames = extract_frames(source, root / "frames", scenes=scenes, duration_sec=asset.get("duration_sec"), max_frames=settings.MAX_VISION_FRAMES)
                    if frames:
                        visual_observations = await get_vision_provider().analyze_frames(frames)

        words = _normalize_words(transcript.get("words") or [])
        segments = _normalize_segments(transcript.get("segments") or [])
        semantic_units = build_semantic_units(segments=segments, scenes=scenes, split_on_speaker=True)
        await job_service.set_progress(job["id"], 80)
        embedder = get_embedding_provider()
        semantic_vectors = await embedder.embed([unit["text"] for unit in semantic_units]) if semantic_units else []
        visual_texts = [visual_text(item) for item in visual_observations]
        visual_vectors = await embedder.embed(visual_texts) if visual_texts else []

        result = {
            "language": transcript.get("language"), "transcript_text": str(transcript.get("text") or "").strip(),
            "words": words, "segments": segments, "speakers": transcript.get("speakers") or [], "diarized": bool(transcript.get("diarized")),
            "scenes": scenes, "visual_observations": visual_observations, "visual_vectors": visual_vectors,
            "semantic_units": semantic_units, "semantic_vectors": semantic_vectors, "embedding_model": settings.EMBEDDING_MODEL,
            "provider": transcript.get("provider"), "model": transcript.get("model"),
        }
        now = utc_now()
        await db.media_intelligence.update_one({"id": intelligence_id}, {"$set": {**result, "status": "completed", "updated_at": now}})
        await db.assets.update_one({"id": asset["id"]}, {"$set": {"language": result["language"], "intelligence_status": "completed", "intelligence_id": intelligence_id, "updated_at": now}})
        await job_service.succeed(job["id"], {"intelligence_id": intelligence_id, "word_count": len(words), "segment_count": len(segments), "scene_count": len(scenes), "speaker_count": len(transcript.get("speakers") or []), "visual_observation_count": len(visual_observations), "visual_embedded_count": len(visual_vectors), "semantic_unit_count": len(semantic_units), "embedded_unit_count": len(semantic_vectors)})
        return True
    except Exception as exc:
        final = job["attempt"] >= job["max_attempts"]
        await job_service.fail(job, code="intelligence.failed", message=str(exc))
        if intelligence_id:
            await db.media_intelligence.update_one({"id": intelligence_id}, {"$set": {"status": "failed" if final else "queued", "updated_at": utc_now()}})
        logger.exception("media intelligence failed for job %s", job["id"])
        return True


async def run_forever() -> None:
    from core.config import settings
    while True:
        if not await process_one():
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SEC)


async def _main(once: bool) -> None:
    try:
        if once:
            await process_one()
        else:
            await run_forever()
    finally:
        await close_mongo()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    asyncio.run(_main(args.once))
