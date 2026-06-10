# ShortCut AI — Architecture Index

> All architecture documents live in `/app/memory/`. Read in this order.

| # | File | Purpose |
|---|---|---|
| 1 | [PRD.md](./PRD.md) | Product scope, MVP boundary, success metrics, **resolved decisions §10** |
| 2 | [ARCHITECTURE.md](./ARCHITECTURE.md) | System diagram, components, S3 flow, SSE flow, auth flow |
| 3 | [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | All 17 MongoDB collections w/ fields + indexes + S3/i18n conventions |
| 4 | [API_CONTRACTS.md](./API_CONTRACTS.md) | 15 route groups, SSE endpoint, S3 presign, Stripe (flag-gated) |
| 5 | [AI_PIPELINE.md](./AI_PIPELINE.md) | 10-agent Create-For-Me + Create-With-Me + free-tier watermark |
| 6 | [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Backend + Expo frontend folder layout |

---

## Architecture Approval Checklist

- [x] PRD scope and MVP boundary are correct
- [x] Adapted stack (Expo + FastAPI + MongoDB + S3 + Emergent LLM key) is acceptable
- [x] 17 collections cover all required entities; no missing fields
- [x] API contracts match the 13 spec'd API groups + additions (SSE, S3 presign)
- [x] 10-agent AI pipeline + Create-With-Me mapping is acceptable
- [x] Viral Score smart enhancement is acceptable
- [x] Folder structure is acceptable
- [x] Auth flow (JWT + Emergent Google) is acceptable
- [x] Job queue via Mongo `ai_jobs` (vs Redis) is acceptable for MVP
- [ ] **Final go-ahead to begin Phase 2 (implementation)**

## Resolved Decisions (from approval round)

| Topic | Decision |
|---|---|
| **Storage** | **AWS S3 from day one.** Pre-signed PUT for uploads, pre-signed GET (1h TTL) for downloads. |
| **Real-time pipeline updates** | **SSE** (`GET /api/v1/ai/jobs/{id}/stream`) — primary. Polling `/status` retained as fallback. |
| **Watermark** | **FFmpeg burn-in on Free tier only**, applied at clip render via `services/media_service.py:apply_watermark()`. |
| **Language** | **English-only at MVP.** All textual collections carry `language` field; agents take `target_language` param. UI strings in `src/i18n/en.json` for future locales. |
| **Stripe** | **Architecture wired now.** Endpoints + webhooks + tier-enforcement middleware live. Paid checkout returns `503 feature_disabled` until env flag `STRIPE_PAID_PLANS_ENABLED=true`. |
| **Liquid Glass tabs** | **iOS 26+ Native Tabs (Liquid Glass)** via expo-router; graceful Material/Cupertino fallback on iOS <26 and Android. |

## Required Credentials (to gather before Phase 2 implementation)

| Credential | Source | Used by |
|---|---|---|
| `EMERGENT_LLM_KEY` | I'll fetch via `emergent_integrations_manager` | Gemini 3 Pro, Gemini Nano Banana, Whisper-1 |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION` + `AWS_S3_BUCKET` | **You provide** | S3 uploads/downloads |
| `STRIPE_SECRET_KEY` (test) | I'll use the pre-loaded platform test key | Stripe (subscriptions skeleton) |
| `JWT_SECRET` | Backend generates strong random | JWT signing |
| Emergent Google Auth | I'll route via `integration_playbook_expert_v2` | Google login |

## Phase 2 Implementation Plan (after your final go-ahead)

1. **Backend skeleton** — FastAPI app, Mongo connection, JWT auth, `/auth/*`, `/users/me`, audit log, error handlers.
2. **S3 + Asset service** — boto3 wrapper, presign endpoints, FFmpeg probe on confirm.
3. **Projects + Asset Library** — CRUD + tagging + search.
4. **AI integration via `integration_playbook_expert_v2`** — Gemini 3 Pro / Nano Banana / Whisper-1 wiring through `emergentintegrations`.
5. **AI orchestrator + 10 agents** — sequential runner, retry, SSE event broker.
6. **Create For Me end-to-end** — upload → pipeline → clips/titles/thumbnails/etc.
7. **Create With Me** — slider translator, command parser, suggestions.
8. **Content Hub** — unified search + filters.
9. **Stripe skeleton** — endpoints flag-gated; webhook handler ready.
10. **Expo UI** — design guidelines → routes → tabs (Liquid Glass) → all screens.
11. **`testing_agent_v3_expo` end-to-end test** — backend + UI flows.
12. **`finish` w/ working demo.**

---

**Ready when you are.** Reply with **"approved — begin Phase 2"** (or any tweaks you want first) and I'll start building.
