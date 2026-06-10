# ShortCut AI — Product Requirements Document (PRD)

> **Status:** Architecture-only phase. No implementation code generated yet. Pending user approval.

---

## 1. Product Vision
ShortCut AI is a **mobile-first AI content creation platform** that turns raw uploads (video, audio, images) into platform-ready content (Reels, Shorts, posts, thumbnails, captions, hashtags, schedules) with zero editing skill required.

Two creation modes:
- **Create For Me** — fully automated AI pipeline (prompt + media in → finished assets out).
- **Create With Me** — AI-guided editing using sliders, AI commands, suggestions, and templates (no technical editing jargon ever surfaced to the user).

## 2. Target Users
Content Creators, Influencers, YouTubers, Instagram Creators, Coaches, Educators, Agencies, Small Businesses, Podcasters, Marketers.

## 3. Supported Content Categories
Podcast, Educational, Business, Travel, Fitness, Comedy, Dance, Vlog, Gaming, Food, Fashion, Real Estate, Events, Product Advertisement, Personal Brand.

## 4. Stack (adapted to Emergent platform)
| Layer | Original spec | Adapted stack |
|---|---|---|
| Frontend | Next.js + TS + Tailwind | **Expo (React Native) + TypeScript** |
| Backend | Spring Boot (Java) | **FastAPI (Python)** |
| DB | PostgreSQL | **MongoDB** (collections mirror tables) |
| Storage | AWS S3 | **AWS S3 from day one** (signed-URL uploads + downloads, 1h TTL) |
| Queue | Redis | **MongoDB job queue collection** (`ai_jobs`) with FastAPI background tasks |
| Media | FFmpeg | **FFmpeg** (server-side) — free-tier watermark burn-in |
| AI | Gemini API | **Gemini 3 Pro (text/analysis) + Gemini Nano Banana (thumbnails) + OpenAI Whisper-1 (transcription)** — all via Emergent LLM key |
| Auth | JWT + Google OAuth | **JWT (email/password) + Emergent-managed Google Auth** |
| Payments | Stripe | **Stripe architecture wired now**, paid plans **disabled** until post-MVP |
| Real-time | — | **SSE stream** for AI pipeline progress (`/ai/jobs/{id}/stream`) |
| Language | — | **English-only MVP**, schema designed for multilingual expansion |
| Native UI | — | **iOS 26 Liquid Glass tabs** when available, graceful fallback on iOS < 26 and Android |

## 5. MVP Scope (approved)
- Module 1: **Authentication** (Email signup/login, Google login, forgot password, JWT, sessions, profiles)
- Module 2: **Dashboard** (Recent projects, continue editing, AI suggestions, performance, calendar preview, quick actions)
- Module 3: **Project Management** (CRUD, rename, duplicate, archive)
- Module 4: **Asset Library** (upload mp4/mov/wav/mp3/png/jpg, search, tag, preview, delete)
- Module 5: **Create For Me** (10-agent AI pipeline)
- Module 6: **Create With Me** (sliders + AI commands + suggestions)
- Module 7: **Content Hub** (clips, titles, descriptions, hashtags, thumbnails — search/filter/sort)
- Module 8: **Subscriptions (Stripe) — architecture only.** Endpoints, models, webhooks, and tier-enforcement middleware are implemented from day one, but paid checkout is **disabled** (returns 503 `feature_disabled`) until post-MVP launch. Free tier active.

**Deferred (post-MVP):** Content Calendar, Analytics, Brand Kit, *enabling* paid Stripe plans.

## 6. Non-Functional Requirements
- Mobile-first (iOS 26 native tabs / Android Material tabs)
- Scalable modular services (one FastAPI router per domain)
- Background AI jobs with retry mechanism (max 3 attempts, exponential backoff)
- Error handling at every API boundary
- Audit logging (`audit_logs` collection)
- API versioning under `/api/v1/*`
- OpenAPI auto-docs at `/api/docs`
- Unit + integration tests

## 7. Approval Checkpoints
1. [x] PRD approved
2. [x] Database schema approved
3. [x] API contracts approved
4. [x] AI pipeline approved
5. [x] Folder structure approved
6. [x] Open questions resolved (see §10)
7. [ ] **Final go-ahead** → implementation begins

## 10. Resolved Decisions (from approval round)
| # | Decision |
|---|---|
| Storage | **AWS S3 from day one.** All uploaded assets, generated clips, thumbnails, and exports stored in S3. Backend issues pre-signed URLs (PUT for upload, GET for download, 1h TTL). `assets.storage_type = "s3"`, `assets.s3_key` and `assets.s3_url` populated. |
| Real-time | **SSE** (`text/event-stream`) for pipeline progress at `GET /api/v1/ai/jobs/{id}/stream`. Polling endpoint `/status` retained as fallback for clients that drop the SSE connection. |
| Watermark | **FFmpeg burn-in on Free tier only.** Centralized in `services/media_service.py:apply_watermark()`; toggled by `user.subscription_tier == "free"` at render time. Asset stored as `*_watermarked.mp4`. |
| Language | **English-only at MVP.** All schema fields carry `language: str` (ISO 639) for forward compatibility; agents accept a `target_language` param defaulted to `"en"`. |
| Stripe | **Architecture wired now.** Subscriptions router, webhooks, customer/sub records, tier-enforcement middleware all implemented. Checkout endpoint returns `503 feature_disabled` until launch flag `STRIPE_PAID_PLANS_ENABLED=true`. |
| Liquid Glass | **iOS 26+ Liquid Glass tabs** via `expo-router` Native Tabs; fallback to standard Material/Cupertino tabs on iOS < 26 and Android. Conditional via `Platform.Version`. |

## 8. Success Metrics
- Time-to-first-clip < 90 seconds for a 10-min podcast
- AI pipeline success rate > 95%
- D1 retention > 40%
- Free → Creator conversion > 8%

## 9. Smart Business Enhancement
**Viral Score Engine** — every generated clip gets a 0–100 "viral score" (based on hook strength, emotional density, pacing, retention prediction) shown next to titles to nudge users into sharing the best clip first. Drives shareability → organic acquisition loop.
