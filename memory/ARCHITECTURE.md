# ShortCut AI — System Architecture

> **Status:** Pending approval. No code yet.

---

## 1. High-Level System Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    EXPO MOBILE APP (React Native)                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐   │
│  │ Auth Stack │ │ Dashboard  │ │  Studio    │ │ Content Hub  │   │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘   │
│         │              │              │              │            │
│         └──────────────┴──────┬───────┴──────────────┘            │
│                          axios + JWT                              │
└──────────────────────────────┼───────────────────────────────────┘
                               │ HTTPS /api/v1/*
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND (Python 3.11)                    │
│  ┌──────────┬──────────┬──────────┬──────────┬───────────────┐  │
│  │ /auth    │ /users   │ /projects│ /assets  │ /ai           │  │
│  ├──────────┼──────────┼──────────┼──────────┼───────────────┤  │
│  │ /clips   │ /captions│ /thumbs  │ /content │ /analytics    │  │
│  ├──────────┼──────────┼──────────┼──────────┼───────────────┤  │
│  │ /calendar│ /subs    │ /brand   │ /admin   │ /webhooks     │  │
│  └──────────┴──────────┴──────────┴──────────┴───────────────┘  │
│         │                              │                          │
│         │                              ▼                          │
│         │                ┌──────────────────────────┐             │
│         │                │  AI ORCHESTRATOR SERVICE │             │
│         │                │   (10-agent pipeline)    │             │
│         │                └────────────┬─────────────┘             │
│         │                             │                            │
│         │                             ▼                            │
│         │            ┌─────────────────────────────────────┐      │
│         │            │  emergentintegrations (LLM bridge)  │      │
│         │            │  - Gemini 3 Pro (text)              │      │
│         │            │  - Gemini Nano Banana (thumbnails)  │      │
│         │            │  - Whisper-1 (transcription)        │      │
│         │            └─────────────────────────────────────┘      │
│         │                                                          │
│         ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              MEDIA PROCESSING (FFmpeg)                    │    │
│  │  - clip cutting   - aspect ratio   - subtitle burn-in     │    │
│  │  - audio extract  - silence remove - thumbnail extract    │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┼───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MONGODB (single source of truth)               │
│  users  projects  assets  transcripts  clips  captions            │
│  thumbnails  titles  descriptions  hashtags  ai_jobs              │
│  content_calendar  analytics  subscriptions  brand_kits           │
│  sessions  audit_logs                                             │
└───────────────────────────────────────────────────────────────────┘

Static / Media files: Base64 in MongoDB for MVP (with chunking via
GridFS for files > 16MB). Production migration path → AWS S3.
```

## 2. Component Responsibilities

### 2.1 Mobile App (Expo)
- **Navigation:** expo-router file-based. Auth stack → main tabs (Dashboard / Studio / Hub / Profile).
- **State:** TanStack Query (server cache) + Zustand (UI state). AsyncStorage for JWT.
- **Media:** `expo-image`, `expo-video`, `expo-audio`, `expo-image-picker`, `expo-document-picker`.
- **Auth:** JWT stored in `expo-secure-store`. Google login via Emergent-managed Auth.
- **Background uploads:** chunked POST with `expo-file-system`.

### 2.2 FastAPI Backend
- **Routers:** one per domain. All mounted under `/api/v1/*`.
- **Auth middleware:** JWT bearer extracts `user_id` and attaches to request.
- **Service layer:** business logic isolated from routers (`services/*.py`).
- **Repositories:** thin Motor (async pymongo) wrappers (`repositories/*.py`).
- **Background tasks:** FastAPI `BackgroundTasks` + a Mongo-backed job queue (`ai_jobs` collection) polled by an in-process worker. Production path → Celery/RQ.

### 2.3 AI Orchestrator
- Sequential agent runner; persists checkpoint after each step into `ai_jobs.progress`.
- Retry policy: 3 attempts with exponential backoff (1s, 4s, 16s).
- Each agent is a pure function: `(input_payload) → output_payload`.
- See `AI_PIPELINE.md` for full spec.

### 2.4 Media Processing (FFmpeg)
- Runs inside backend container.
- Wrapped by `services/media_service.py`.
- Operations: clip cut by timestamps, aspect ratio reframe (9:16 / 1:1 / 16:9), silence removal, subtitle burn-in, audio normalize, thumbnail extract at timestamp.

### 2.5 Storage (AWS S3 — day one)
- All uploads, clips, thumbnails, and exports stored in **S3**.
- Bucket layout: `s3://<bucket>/users/<user_id>/<resource>/<asset_id>.<ext>`
- Upload flow: client requests `POST /assets/presign-upload` → backend returns signed PUT URL + asset shell row → client PUTs binary directly to S3 → client confirms via `POST /assets/{id}/confirm`.
- Download flow: client calls `GET /assets/{id}` → backend returns signed GET URL (1h TTL).
- Server-side ops (FFmpeg) stream S3 → temp disk → S3.
- `asset.storage_type = "s3"`, `asset.s3_key`, `asset.s3_bucket`, `asset.s3_url` (signed, ephemeral).

## 3. Authentication Flow

### Email/Password (JWT)
```
POST /api/v1/auth/signup { email, password, name }
  → bcrypt hash → users insert → JWT (access 60min + refresh 30d)
POST /api/v1/auth/login { email, password }
POST /api/v1/auth/refresh { refresh_token }
POST /api/v1/auth/forgot-password { email }   → reset token email
POST /api/v1/auth/reset-password { token, new_password }
```

### Google (Emergent-managed)
```
Mobile app → Emergent Auth SDK → returns auth_code
POST /api/v1/auth/google { auth_code }
  → backend verifies via Emergent → upsert user → JWT
```

## 4. AI Job Lifecycle

```
[mobile] POST /projects/{id}/run-pipeline
        ├─ creates ai_jobs doc { status: queued, progress: 0 }
        ├─ returns job_id immediately (202 Accepted)
        └─ BackgroundTasks.add_task(orchestrator.run, job_id)

[worker] orchestrator.run(job_id)
        loop step in [transcription, analysis, clip_detection,
                      editing_planner, caption, title, description,
                      hashtag, thumbnail, strategy]:
            ai_jobs.update(status=running, current_step=step, progress=X%)
            try:  result = agent.execute(payload)
            except: retry 3x with backoff; on fail → status=failed
            ai_jobs.update(step_result=result)
        ai_jobs.update(status=completed, progress=100)

[mobile] SSE stream GET /api/v1/ai/jobs/{job_id}/stream
         events: { event: "progress", data: {step, progress} }
                 { event: "step_complete", data: {step, result_summary} }
                 { event: "done", data: {job_id} }
                 { event: "error", data: {step, message} }
         Polling fallback: GET /ai/jobs/{job_id}/status every 2s
```

## 5. Security
- bcrypt password hashing (cost 12)
- JWT signed with HS256; secret in `.env`
- Rate limits: auth endpoints 5 req/min/IP; AI endpoints 10 req/hour/user
- CORS allowlist driven by env var
- Input validation via Pydantic v2 strict models
- Audit log writes for: login, password change, project delete, subscription change

## 6. Deployment Topology (post-approval)
| Service | Port | Process manager |
|---|---|---|
| FastAPI (uvicorn) | 8001 | supervisor |
| Expo Metro | 3000 | supervisor |
| MongoDB | 27017 | host service |
| FFmpeg | (in-process) | bundled with backend |

## 7. Open Questions for Review
*(All resolved — see PRD.md §10 for final decisions.)*
1. ~~GridFS vs S3 for MVP storage~~ → **S3 from day one.**
2. ~~SSE vs polling for job status~~ → **SSE primary, polling fallback.**
3. ~~Watermark renderer location~~ → **FFmpeg burn-in on Free tier only.**
4. ~~Viral Score model~~ → **Hybrid: heuristic formula seeded by LLM scores** (see AI_PIPELINE.md §3).
5. ~~Stripe timing~~ → **Architecture now, paid plans flag-gated off.**
6. ~~Liquid Glass~~ → **iOS 26+ Native Tabs, fallback elsewhere.**
7. ~~Default language~~ → **English-only MVP, schema multilingual-ready.**
