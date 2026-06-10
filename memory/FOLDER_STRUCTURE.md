# ShortCut AI — Folder Structure (proposed)

> Reflects the **Expo + FastAPI + MongoDB** stack. Generated only after architecture approval.

---

## Backend `/app/backend/`

```
backend/
├── server.py                       # FastAPI app entry; mounts routers
├── requirements.txt
├── .env                            # MONGO_URL, JWT_SECRET, EMERGENT_LLM_KEY, STRIPE_KEY
├── core/
│   ├── __init__.py
│   ├── config.py                   # pydantic Settings, reads env
│   ├── security.py                 # bcrypt, JWT encode/decode, password reset tokens
│   ├── deps.py                     # FastAPI dependencies (get_current_user, get_db)
│   ├── errors.py                   # custom exception classes + handlers
│   ├── pagination.py               # cursor helpers
│   └── logging.py                  # structured logger
│
├── db/
│   ├── __init__.py
│   ├── mongo.py                    # Motor client, db handle
│   └── indexes.py                  # ensure_indexes() called on startup
│
├── models/                         # Pydantic models (request + response)
│   ├── user.py
│   ├── project.py
│   ├── asset.py
│   ├── transcript.py
│   ├── clip.py
│   ├── caption.py
│   ├── title.py
│   ├── description.py
│   ├── hashtag.py
│   ├── thumbnail.py
│   ├── ai_job.py
│   ├── calendar.py
│   ├── analytics.py
│   ├── subscription.py
│   ├── brand_kit.py
│   └── common.py                   # enums (ContentType, Platform, Style, Status)
│
├── repositories/                   # Mongo CRUD (one per collection)
│   ├── user_repo.py
│   ├── project_repo.py
│   ├── asset_repo.py
│   ├── ai_job_repo.py
│   ├── clip_repo.py
│   ├── caption_repo.py
│   ├── title_repo.py
│   ├── description_repo.py
│   ├── hashtag_repo.py
│   ├── thumbnail_repo.py
│   ├── transcript_repo.py
│   ├── audit_repo.py
│   ├── session_repo.py
│   ├── calendar_repo.py
│   ├── analytics_repo.py
│   ├── subscription_repo.py
│   └── brand_repo.py
│
├── services/                       # business logic
│   ├── auth_service.py
│   ├── user_service.py
│   ├── project_service.py
│   ├── asset_service.py            # presign upload/download, confirm
│   ├── s3_service.py               # boto3 wrapper (presign, head, delete)
│   ├── media_service.py            # FFmpeg wrappers + watermark burn-in
│   ├── content_hub_service.py
│   ├── quota_service.py            # subscription tier enforcement
│   ├── stripe_service.py           # checkout/portal/webhook handling (paid flag-gated)
│   ├── sse_service.py              # SSE event broker per job_id
│   └── audit_service.py
│
├── ai/
│   ├── __init__.py
│   ├── orchestrator.py             # runs 10-agent pipeline, manages ai_jobs
│   ├── llm_client.py               # emergentintegrations wrapper (Gemini/Whisper)
│   ├── prompts/                    # prompt templates (one file per agent)
│   │   ├── content_analysis.py
│   │   ├── clip_detection.py
│   │   ├── editing_planner.py
│   │   ├── caption.py
│   │   ├── title.py
│   │   ├── description.py
│   │   ├── hashtag.py
│   │   ├── thumbnail.py
│   │   └── strategy.py
│   ├── agents/
│   │   ├── base.py                 # AgentBase with retry/backoff
│   │   ├── transcription_agent.py
│   │   ├── content_analysis_agent.py
│   │   ├── clip_detection_agent.py
│   │   ├── editing_planner_agent.py
│   │   ├── caption_agent.py
│   │   ├── title_agent.py
│   │   ├── description_agent.py
│   │   ├── hashtag_agent.py
│   │   ├── thumbnail_agent.py
│   │   └── strategy_agent.py
│   ├── slider_translator.py        # Create-With-Me slider → action mapping
│   ├── command_parser.py           # NL command → agent subset selector
│   └── viral_score.py
│
├── routers/                        # FastAPI APIRouter modules
│   ├── auth.py
│   ├── users.py
│   ├── projects.py
│   ├── assets.py
│   ├── ai.py
│   ├── clips.py
│   ├── captions.py
│   ├── titles.py
│   ├── descriptions.py
│   ├── hashtags.py
│   ├── thumbnails.py
│   ├── content.py
│   ├── analytics.py                # post-MVP
│   ├── calendar.py                 # post-MVP
│   ├── subscriptions.py            # wired now; paid endpoints flag-gated 503
│   ├── brand.py                    # post-MVP
│   └── system.py                   # /health, /api/docs
│
├── assets_static/
│   └── watermark.png               # free-tier watermark overlay
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_auth_service.py
    │   ├── test_quota_service.py
    │   ├── test_viral_score.py
    │   └── test_slider_translator.py
    └── integration/
        ├── test_auth_flow.py
        ├── test_project_crud.py
        ├── test_pipeline_e2e.py
        └── test_assets_upload.py
```

---

## Frontend `/app/frontend/`

```
frontend/
├── app.json
├── package.json
├── metro.config.js                 # PROTECTED — do not modify
├── .env                            # EXPO_PUBLIC_BACKEND_URL — PROTECTED
├── tsconfig.json
├── eslint.config.js
│
├── app/                            # expo-router file-based routes
│   ├── _layout.tsx                 # root layout, Auth gate, theme provider
│   ├── index.tsx                   # splash → routes to (auth) or (tabs)
│   ├── (auth)/
│   │   ├── _layout.tsx
│   │   ├── welcome.tsx
│   │   ├── sign-in.tsx
│   │   ├── sign-up.tsx
│   │   ├── google.tsx              # OAuth callback handler
│   │   ├── forgot-password.tsx
│   │   └── reset-password.tsx
│   ├── (tabs)/
│   │   ├── _layout.tsx             # iOS 26+ Liquid Glass NativeTabs / fallback Material on iOS<26 & Android
│   │   ├── dashboard.tsx           # Tab 1
│   │   ├── studio.tsx              # Tab 2 — list projects + new
│   │   ├── hub.tsx                 # Tab 3 — Content Hub
│   │   └── profile.tsx             # Tab 4
│   ├── projects/
│   │   ├── new.tsx                 # creation wizard (mode picker)
│   │   ├── [id]/
│   │   │   ├── _layout.tsx
│   │   │   ├── index.tsx           # project detail
│   │   │   ├── upload.tsx
│   │   │   ├── create-for-me.tsx   # AI pipeline runner + live progress
│   │   │   ├── create-with-me.tsx  # sliders + commands UI
│   │   │   ├── clips.tsx           # generated clips grid
│   │   │   ├── clip/[clipId].tsx   # single clip view (titles, caption, thumbnail tabs)
│   │   │   ├── thumbnails.tsx
│   │   │   ├── titles.tsx
│   │   │   ├── descriptions.tsx
│   │   │   └── hashtags.tsx
│   ├── assets/
│   │   ├── index.tsx               # Asset Library
│   │   └── [id].tsx                # asset preview
│   ├── onboarding/
│   │   ├── _layout.tsx
│   │   ├── user-type.tsx
│   │   ├── niche.tsx
│   │   └── done.tsx
│   ├── settings/
│   │   ├── index.tsx
│   │   ├── account.tsx
│   │   ├── subscription.tsx        # post-MVP
│   │   └── brand-kit.tsx           # post-MVP
│   └── modals/
│       ├── ai-suggestions.tsx
│       ├── pipeline-progress.tsx
│       └── share-clip.tsx
│
├── src/
│   ├── api/
│   │   ├── client.ts               # axios + interceptors + token refresh
│   │   ├── auth.ts
│   │   ├── projects.ts
│   │   ├── assets.ts
│   │   ├── ai.ts
│   │   ├── clips.ts
│   │   ├── content.ts
│   │   └── thumbnails.ts
│   ├── store/                      # Zustand
│   │   ├── auth.ts
│   │   ├── ui.ts
│   │   └── pipeline.ts             # SSE-driven progress state
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePipelineSSE.ts       # connects to /ai/jobs/{id}/stream
│   │   ├── usePipelineStatus.ts    # polling fallback
│   │   ├── useProjects.ts
│   │   ├── useAssets.ts
│   │   └── useUploader.ts          # presign → direct PUT to S3 → confirm
│   ├── i18n/
│   │   ├── index.ts                # i18next setup
│   │   └── en.json                 # English strings (only locale at MVP)
│   ├── components/
│   │   ├── ui/                     # design-system primitives
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Chip.tsx            # filter chip row primitive
│   │   │   ├── BottomSheet.tsx
│   │   │   ├── Toast.tsx
│   │   │   ├── ScoreBadge.tsx      # viral score visual
│   │   │   └── ProgressRing.tsx
│   │   ├── auth/
│   │   ├── dashboard/
│   │   │   ├── RecentProjects.tsx
│   │   │   ├── ContinueEditing.tsx
│   │   │   ├── QuickActions.tsx
│   │   │   ├── AISuggestionsCard.tsx
│   │   │   └── PerformanceCard.tsx
│   │   ├── studio/
│   │   │   ├── ProjectCard.tsx
│   │   │   ├── ModePickerSheet.tsx
│   │   │   ├── ContentTypeSheet.tsx
│   │   │   ├── StyleSheet.tsx
│   │   │   └── PlatformPickerSheet.tsx
│   │   ├── pipeline/
│   │   │   ├── StepProgress.tsx
│   │   │   ├── AgentLog.tsx
│   │   │   └── PipelineErrorState.tsx
│   │   ├── clips/
│   │   │   ├── ClipCard.tsx
│   │   │   ├── ClipPlayer.tsx
│   │   │   ├── CaptionsView.tsx
│   │   │   ├── TitleVariations.tsx
│   │   │   └── HashtagCloud.tsx
│   │   ├── createwithme/
│   │   │   ├── SliderRow.tsx
│   │   │   ├── AICommandInput.tsx
│   │   │   └── SuggestionList.tsx
│   │   ├── hub/
│   │   │   ├── HubFilters.tsx
│   │   │   └── HubGrid.tsx
│   │   ├── assets/
│   │   │   ├── AssetTile.tsx
│   │   │   └── UploadButton.tsx
│   │   └── common/
│   │       ├── ErrorBoundary.tsx
│   │       ├── EmptyState.tsx
│   │       ├── LoadingScreen.tsx
│   │       └── SafeScrollView.tsx
│   ├── theme/
│   │   ├── colors.ts
│   │   ├── spacing.ts              # tokens from design_guidelines.json
│   │   ├── typography.ts
│   │   └── radius.ts
│   ├── utils/
│   │   ├── storage/                # already exists — AsyncStorage / SecureStore
│   │   ├── format.ts
│   │   ├── platform.ts
│   │   └── time.ts
│   └── constants/
│       ├── platforms.ts
│       ├── contentTypes.ts
│       └── styles.ts
│
├── assets/                         # icons, splash, fonts
└── scripts/                        # CI helpers
```

---

## /app/memory (architecture docs)
```
memory/
├── PRD.md
├── ARCHITECTURE.md
├── DATABASE_SCHEMA.md
├── API_CONTRACTS.md
├── AI_PIPELINE.md
├── FOLDER_STRUCTURE.md       (this file)
└── test_credentials.md       (updated when seed users are created)
```

---

## Naming Conventions
- Files: snake_case for Python, kebab-case for Expo route files, PascalCase for React components.
- Routes: `/api/v1/<group>/<resource>`.
- Mongo collections: snake_case plural.
- Pydantic models: `<Entity>Create`, `<Entity>Update`, `<Entity>Out`.

## Testing Conventions
- Backend unit tests: `tests/unit/test_<module>.py`, pytest fixtures from `conftest.py`.
- Backend integration tests: hit FastAPI via `httpx.AsyncClient`.
- Frontend: tested via `testing_agent_v3_expo` (E2E) once UI is built.

## testID Conventions (Expo)
Every interactive / informational element gets a `testID` in kebab-case by role:
- `auth-signin-submit`, `auth-google-button`
- `dashboard-newproject-button`, `dashboard-recent-project-card-{id}`
- `studio-mode-picker-create-for-me`
- `pipeline-progress-step-{name}`, `pipeline-progress-percent`
- `clip-card-{clipId}`, `clip-viral-score-badge`
- `hub-filter-chip-{value}`, `hub-search-input`
