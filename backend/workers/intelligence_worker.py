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
from models.job import JobStatus, JobType
from services import job_service
from services.audio_extract import extract_mono_16k
from services.broll_planning import visual_text
from services.beat_detection import estimate_beat_grid
from services.embeddings import get_embedding_provider
from services.frame_sampler import extract_frames
from services.scene_detection import detect_scenes
from services.rhythm_detection import RhythmDetectionError, detect_rhythm_events
from services.silence_detection import SilenceDetectionError, detect_silences
from services.semantic_units import build_semantic_units
from services.storage import materialize
from services.transcription import get_transcription_provider
from services.vision import get_vision_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("shortcut.intelligence-worker")


def _worker_lease_seconds() -> int:
    return max(
        settings.JOB_LEASE_SECONDS,
        settings.MEDIA_INTELLIGENCE_TIMEOUT_SEC + 300,
    )


async def _complete_already_analyzed(job: dict, record: dict, asset: dict) -> bool:
    if record.get("status") != "completed" or record.get("job_id") != job["id"]:
        return False

    now = utc_now()
    await get_db().assets.update_one(
        {"id": asset["id"]},
        {
            "$set": {
                "language": record.get("language"),
                "intelligence_status": "completed",
                "intelligence_id": record["id"],
                "updated_at": now,
            }
        },
    )
    owned = await job_service.succeed(
        job["id"],
        {
            "intelligence_id": record["id"],
            "word_count": len(record.get("words") or []),
            "segment_count": len(record.get("segments") or []),
            "scene_count": len(record.get("scenes") or []),
            "silence_count": len(record.get("silences") or []),
            "rhythm_event_count": len(record.get("rhythm_events") or []),
            "beat_grid_confidence": (record.get("beat_grid") or {}).get("confidence"),
            "speaker_count": len(record.get("speakers") or []),
            "visual_observation_count": len(record.get("visual_observations") or []),
            "visual_embedded_count": len(record.get("visual_vectors") or []),
            "semantic_unit_count": len(record.get("semantic_units") or []),
            "embedded_unit_count": len(record.get("semantic_vectors") or []),
            "reconciled_existing_intelligence": True,
        },
        lease_token=job["lease_token"],
    )
    if not owned:
        logger.warning(
            "lost lease while reconciling intelligence %s",
            record["id"],
        )
    return True


async def _recover_stale_intelligence() -> None:
    recovered = await job_service.recover_stale_jobs(JobType.media_intelligence)
    if not recovered:
        return
    db = get_db()
    for job in recovered:
        intelligence_id = (job.get("payload") or {}).get("intelligence_id")
        if not intelligence_id:
            continue
        status = (
            "queued"
            if job["recovered_status"] == JobStatus.queued.value
            else "failed"
        )
        await db.media_intelligence.update_one(
            {
                "id": intelligence_id,
                "status": {"$ne": "completed"},
            },
            {
                "$set": {
                    "status": status,
                    "updated_at": utc_now(),
                }
            },
        )
        if job.get("asset_id"):
            await db.assets.update_one(
                {
                    "id": job["asset_id"],
                    "intelligence_status": {"$ne": "completed"},
                },
                {
                    "$set": {
                        "intelligence_status": status,
                        "updated_at": utc_now(),
                    }
                },
            )


async def _progress(job: dict, progress: int) -> None:
    ok = await job_service.set_progress(
        job["id"],
        progress,
        lease_token=job["lease_token"],
        lease_seconds=_worker_lease_seconds(),
    )
    if not ok:
        raise RuntimeError("media-intelligence job lease was lost")


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
    await _recover_stale_intelligence()
    job = await job_service.claim_next(
        JobType.media_intelligence,
        lease_seconds=_worker_lease_seconds(),
    )
    if not job:
        return False
    db = get_db()
    intelligence_id = job.get("payload", {}).get("intelligence_id")
    try:
        record = await db.media_intelligence.find_one({"id": intelligence_id, "user_id": job["user_id"]}, {"_id": 0})
        asset = await db.assets.find_one({"id": job["asset_id"], "user_id": job["user_id"]}, {"_id": 0})
        if not record or not asset:
            raise RuntimeError("analysis record or asset no longer exists")
        if await _complete_already_analyzed(job, record, asset):
            return True
        await db.media_intelligence.update_one({"id": intelligence_id}, {"$set": {"status": "running", "updated_at": utc_now()}})

        with TemporaryDirectory(prefix="shortcut-intelligence-") as tmp:
            root = Path(tmp)
            suffix = Path(asset["filename"]).suffix
            with materialize(asset["storage_key"], suffix=suffix) as source:
                audio = root / "speech.wav"
                await _progress(job, 15)
                extract_mono_16k(source, audio)
                await _progress(job, 25)
                try:
                    silences = detect_silences(
                        audio,
                        duration_sec=asset.get("duration_sec"),
                    )
                except SilenceDetectionError as exc:
                    logger.warning(
                        "silence detection skipped for asset %s: %s",
                        asset["id"],
                        exc,
                    )
                    silences = []
                try:
                    rhythm_events = detect_rhythm_events(audio)
                except RhythmDetectionError as exc:
                    logger.warning(
                        "rhythm detection skipped for asset %s: %s",
                        asset["id"],
                        exc,
                    )
                    rhythm_events = []
                beat_grid = estimate_beat_grid(
                    [event["time"] for event in rhythm_events]
                )
                await _progress(job, 40)
                transcript = await get_transcription_provider().transcribe(audio)
                scenes, visual_observations = [], []
                if asset["kind"] == "video":
                    await _progress(job, 55)
                    scenes = detect_scenes(source, asset.get("duration_sec"))
                    await _progress(job, 65)
                    frames = extract_frames(source, root / "frames", scenes=scenes, duration_sec=asset.get("duration_sec"), max_frames=settings.MAX_VISION_FRAMES)
                    if frames:
                        visual_observations = await get_vision_provider().analyze_frames(frames)

        words = _normalize_words(transcript.get("words") or [])
        segments = _normalize_segments(transcript.get("segments") or [])
        semantic_units = build_semantic_units(segments=segments, scenes=scenes, split_on_speaker=True)
        await _progress(job, 80)
        embedder = get_embedding_provider()
        semantic_vectors = await embedder.embed([unit["text"] for unit in semantic_units]) if semantic_units else []
        visual_texts = [visual_text(item) for item in visual_observations]
        visual_vectors = await embedder.embed(visual_texts) if visual_texts else []

        result = {
            "language": transcript.get("language"), "transcript_text": str(transcript.get("text") or "").strip(),
            "words": words, "segments": segments, "speakers": transcript.get("speakers") or [], "diarized": bool(transcript.get("diarized")),
            "scenes": scenes, "silences": silences, "rhythm_events": rhythm_events, "beat_grid": beat_grid, "visual_observations": visual_observations, "visual_vectors": visual_vectors,
            "semantic_units": semantic_units, "semantic_vectors": semantic_vectors, "embedding_model": settings.EMBEDDING_MODEL,
            "provider": transcript.get("provider"), "model": transcript.get("model"),
        }
        await _progress(job, 95)
        now = utc_now()
        await db.media_intelligence.update_one({"id": intelligence_id}, {"$set": {**result, "status": "completed", "updated_at": now}})
        await db.assets.update_one({"id": asset["id"]}, {"$set": {"language": result["language"], "intelligence_status": "completed", "intelligence_id": intelligence_id, "updated_at": now}})
        owned = await job_service.succeed(
            job["id"],
            {
                "intelligence_id": intelligence_id,
                "word_count": len(words),
                "segment_count": len(segments),
                "scene_count": len(scenes),
                "silence_count": len(silences),
                "rhythm_event_count": len(rhythm_events),
                "beat_grid_confidence": (beat_grid or {}).get("confidence"),
                "speaker_count": len(transcript.get("speakers") or []),
                "visual_observation_count": len(visual_observations),
                "visual_embedded_count": len(visual_vectors),
                "semantic_unit_count": len(semantic_units),
                "embedded_unit_count": len(semantic_vectors),
            },
            lease_token=job["lease_token"],
        )
        if not owned:
            logger.warning(
                "media-intelligence job %s lost its lease before completion",
                job["id"],
            )
        return True
    except Exception as exc:
        final = job["attempt"] >= job["max_attempts"]
        owned = await job_service.fail(
            job,
            code="intelligence.failed",
            message=str(exc),
            lease_token=job.get("lease_token"),
        )
        if owned and intelligence_id:
            await db.media_intelligence.update_one(
                {"id": intelligence_id},
                {
                    "$set": {
                        "status": "failed" if final else "queued",
                        "updated_at": utc_now(),
                    }
                },
            )
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
