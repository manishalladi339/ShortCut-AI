# ShortCut AI — Architecture Index

> All architecture documents live in `/app/memory/`. Read in this order.

| # | File | Purpose |
|---|---|---|
| 1 | [PRD.md](./PRD.md) | Product scope, MVP boundary, success metrics |
| 2 | [ARCHITECTURE.md](./ARCHITECTURE.md) | System diagram, components, auth flow, job lifecycle |
| 3 | [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | All 17 MongoDB collections w/ fields + indexes |
| 4 | [API_CONTRACTS.md](./API_CONTRACTS.md) | 15 route groups, payloads, errors, pagination |
| 5 | [AI_PIPELINE.md](./AI_PIPELINE.md) | 10-agent Create-For-Me + Create-With-Me sliders/commands |
| 6 | [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Backend + Expo frontend folder layout |

---

## Architecture Approval Checklist

- [ ] PRD scope and MVP boundary are correct
- [ ] Adapted stack (Expo + FastAPI + MongoDB + Emergent LLM key) is acceptable
- [ ] 17 collections cover all required entities; no missing fields
- [ ] API contracts match the 13 spec'd API groups + additions
- [ ] 10-agent AI pipeline + Create-With-Me mapping is acceptable
- [ ] Viral Score smart enhancement is acceptable
- [ ] Folder structure is acceptable
- [ ] Auth flow (JWT + Emergent Google) is acceptable
- [ ] Job queue via Mongo `ai_jobs` (vs Redis) is acceptable for MVP

## Open Questions (please confirm)
1. **Storage for MVP**: inline base64 + GridFS, or jump to S3 immediately?
2. **Real-time pipeline updates**: polling (default) or SSE stream?
3. **Watermark on Free tier**: FFmpeg burn-in OK?
4. **Default content language**: English only at MVP, multi-language later?
5. **Stripe**: defer entirely (post-MVP) — confirm OK?
6. **Native iOS Liquid Glass tabs**: enable when iOS ≥ 26, else fallback — OK?

Once approved (or changes requested), I'll begin Phase 2: implementation, starting with backend skeleton + auth + projects, then the AI orchestrator, then the Expo UI.
