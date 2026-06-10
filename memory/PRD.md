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
| Storage | AWS S3 | **Base64 + MongoDB GridFS** (preview) → S3 on production |
| Queue | Redis | **MongoDB job queue collection** (`ai_jobs`) with FastAPI background tasks |
| Media | FFmpeg | **FFmpeg** (server-side) |
| AI | Gemini API | **Gemini 3 Pro (text/analysis) + Gemini Nano Banana (thumbnails) + OpenAI Whisper-1 (transcription)** — all via Emergent LLM key |
| Auth | JWT + Google OAuth | **JWT (email/password) + Emergent-managed Google Auth** |
| Payments | Stripe | **Stripe** (test keys from env) |

## 5. MVP Scope (approved)
- Module 1: **Authentication** (Email signup/login, Google login, forgot password, JWT, sessions, profiles)
- Module 2: **Dashboard** (Recent projects, continue editing, AI suggestions, performance, calendar preview, quick actions)
- Module 3: **Project Management** (CRUD, rename, duplicate, archive)
- Module 4: **Asset Library** (upload mp4/mov/wav/mp3/png/jpg, search, tag, preview, delete)
- Module 5: **Create For Me** (10-agent AI pipeline)
- Module 6: **Create With Me** (sliders + AI commands + suggestions)
- Module 7: **Content Hub** (clips, titles, descriptions, hashtags, thumbnails — search/filter/sort)

**Deferred (post-MVP):** Content Calendar, Analytics, Brand Kit, Subscriptions (Stripe).

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
1. [ ] PRD approved
2. [ ] Database schema approved
3. [ ] API contracts approved
4. [ ] AI pipeline approved
5. [ ] Folder structure approved
6. [ ] **THEN** implementation begins

## 8. Success Metrics
- Time-to-first-clip < 90 seconds for a 10-min podcast
- AI pipeline success rate > 95%
- D1 retention > 40%
- Free → Creator conversion > 8%

## 9. Smart Business Enhancement
**Viral Score Engine** — every generated clip gets a 0–100 "viral score" (based on hook strength, emotional density, pacing, retention prediction) shown next to titles to nudge users into sharing the best clip first. Drives shareability → organic acquisition loop.
