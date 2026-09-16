# ShortCut AI

ShortCut AI is an AI Director / AI Editor that turns raw media into a grounded,
reviewable edit without silently rewriting the creator's timeline.

The product is built around one principle:

> Give ShortCut everything you shot and tell it the story you want to tell.

ShortCut analyzes the project, proposes a story and edit plan with source provenance,
lets the creator approve or modify individual decisions, applies only approved
changes to a canonical ProjectState, renders the finished video, and inspects the
actual output with Export QA.

## Core capabilities

### AI Director / Create For Me

- whole-project Media Intelligence
- Story Director: hook / context / development / proof / payoff
- grounded source moments with exact provenance
- semantic B-roll retrieval
- still-image B-roll
- subject-aware portrait reframing
- internal dead-air removal
- rhythm-aware B-roll timing
- animated captions
- music bed + speech ducking
- final audio mastering
- review-before-apply plan workflow

### Multi-Asset Director Mode

For longer stories across multiple source assets:

- source-diversity-aware primary story selection
- topic coverage balancing
- source-share caps
- up to 15-minute plans
- Source Mix transparency
- grounded visual support from analyzed video and image assets

### Create With Me

Natural-language, localized editing with version-safe proposals:

- "Remove Speaker B"
- "Make the first ten seconds faster"
- "Replace B-roll in the intro with factory footage"
- "Add a subtle push-in"
- "Pan right"
- "Slide this shot in from the left"
- "Fade this B-roll out"
- "Make the captions pop"
- "Use bold social captions"
- "Lower the music"

Structural edits use conservative ripple/refusal rules rather than silently breaking
synchronization.

### Creator Memory

ShortCut learns only from editing evidence such as accepted/skipped operations and
applied constrained edits. It can adapt caption style, B-roll density, music level
and caption animation as evidence accumulates.

### Timeline review

- inline rendered preview
- canonical versioned timeline
- source-range inspection
- AI provenance chips
- exact-range Create With Me actions
- stale-render warning when the timeline changed after export

### Rendering and QA

- FFmpeg H.264/AAC rendering
- multiple tracks and overlays
- transforms and normalized motion keyframes
- fade + directional slide transitions
- ASS animated captions
- speech-responsive music ducking
- two-pass loudness / true-peak mastering
- deterministic render validation
- post-render Export QA
- reviewable QA caption repairs

## Trust model

ShortCut never silently applies an AI edit.

Plans and constrained edits are tied to an exact ProjectState version. Apply uses
optimistic concurrency, so a stale proposal cannot overwrite newer work.

Source-grounded metadata is retained for story moments, B-roll, reframing, QA repairs
and other AI-generated decisions.

## Architecture

```text
Raw Media
   ↓
Media Intelligence
   ↓
Project Intelligence
   ↓
Creative Brief / Multi-Asset Director
   ↓
Story Director
   ↓
Evidence Retrieval
   ↓
Edit Planner
   ↓
Reviewable AI Plan
   ↓
Canonical ProjectState
   ↓
Create With Me / Timeline Review
   ↓
Render Engine
   ↓
Audio Mastering
   ↓
Export QA
   ↓
Finished Video
   ↓
Creator Feedback
   ↓
Creator Memory
```

Backend:
- FastAPI / Python
- MongoDB / Motor
- FFmpeg / FFprobe
- S3-compatible object storage
- Mongo-backed durable job queue with worker leases

Frontend:
- Expo Router
- React Native / TypeScript
- web + mobile-capable client

## Local development

### Requirements

- Docker + Docker Compose
- OpenAI API key for full transcription/vision/embedding analysis

### Start the stack

```bash
export OPENAI_API_KEY=your-key
docker compose up --build
```

API:

```text
http://localhost:8001
```

Health:

```bash
curl http://localhost:8001/api/v1/health
```

Readiness:

```bash
curl http://localhost:8001/api/v1/ready
```

Frontend:

```bash
cd frontend
cp .env.example .env
yarn install
yarn start
```

## Validation

Backend and frontend are validated independently in GitHub Actions.

Frontend:

```bash
cd frontend
yarn typecheck
yarn lint
```

Backend tests run through the repository CI workflow and integration environment.

## Production deployment

Production uses:

- external MongoDB
- shared S3-compatible object storage
- one API service
- media worker
- intelligence worker
- render worker
- explicit HTTPS/CORS configuration
- strong JWT secret
- dependency readiness checks

Start from:

```bash
cp .env.production.example .env.production
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d --build
```

See [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) for the complete
runbook, worker scaling, crash recovery, storage requirements and release checklist.

## Production reliability

Background work uses expiring worker leases:

- stale jobs are recovered automatically
- retries are fenced by worker ownership
- stale attempts cannot commit after ownership moved
- completed work can be reconciled after process crashes
- duplicate active renders are deduplicated

Every API request includes an `X-Request-ID` response header and logs latency/status
for correlation.

## Free beta quota

Free users default to 3 projects per UTC calendar month.

The quota window resets automatically, is consumed atomically, and applies to both
new projects and duplicated projects.

Paid billing remains disabled until it is intentionally enabled.

## Key documentation

- [Create With Me](docs/CONSTRAINED_EDITING.md)
- [Creator Memory](docs/CREATOR_MEMORY.md)
- [Export QA](docs/EXPORT_QA.md)
- [Timeline Review](docs/TIMELINE_REVIEW.md)
- [Smart Reframing](docs/SMART_REFRAMING.md)
- [Animated Captions](docs/ANIMATED_CAPTIONS.md)
- [Motion Keyframes](docs/MOTION_KEYFRAMES.md)
- [Visual Transitions](docs/VISUAL_TRANSITIONS.md)
- [Multi-Asset Director](docs/MULTI_ASSET_DIRECTOR.md)
- [Job Reliability](docs/JOB_RELIABILITY.md)
- [Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)
