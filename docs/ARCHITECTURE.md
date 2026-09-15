# ShortCut AI — Product Architecture

ShortCut AI is an AI-native mobile editing system. The core contract is simple:

> AI decides **what** should change. A deterministic editing engine decides **how** that change is represented and rendered.

## Product flows

### Create For Me
1. User creates a project and uploads source media.
2. Media ingestion validates and normalizes assets.
3. Analysis workers produce transcript, shot/scene boundaries, audio features and semantic metadata.
4. The AI planner consumes user intent, creator preferences and media intelligence.
5. The planner emits validated `EditOperation` objects.
6. Operations mutate the canonical `ProjectState`.
7. A render planner converts a specific ProjectState version into a deterministic render plan.
8. Media workers render, validate and publish the final artifact.

### Create With Me
1. User opens an existing ProjectState.
2. Natural-language requests are converted into proposed EditOperations.
3. The backend validates permissions, state version and operation schema.
4. Accepted operations are appended to history and applied to ProjectState.
5. The mobile client receives the new state and can undo, refine or render.

## System boundaries

```text
Expo / React Native
       |
       v
FastAPI application
  |    |      |       |
Auth Projects Assets ProjectState
       |      |       |
       +------+-------+
              |
        MongoDB (current)
              |
      background job boundary
              |
     analysis / AI / render workers
              |
          object storage
```

The current repository uses MongoDB and local/S3-compatible storage contracts. The long-term production target can migrate persistence behind repository interfaces without changing the public API.

## Canonical editing model

```text
Project
  -> ProjectState
      -> Sequence(s)
          -> Track(s)
              -> Clip(s)
                  -> source asset + source range
                  -> timeline range
                  -> transform/audio/caption metadata
      -> version
      -> operation history

ProjectState(version N)
  -> RenderPlan
  -> Render Artifact
```

Time is represented with integer ticks plus an explicit timebase. Floating-point seconds are not authoritative timeline coordinates.

## Concurrency

Every ProjectState has an integer `version`. Mutations require `expected_version`. If the client edits stale state, the API returns HTTP 409 rather than silently overwriting newer edits.

## AI boundary

LLMs and agents never directly mutate database documents or shell out to FFmpeg. They return structured proposals. The application validates proposals and applies deterministic operations.

Planned intelligence modules:
- transcription and diarization
- shot/scene detection
- visual/audio understanding
- semantic indexing and retrieval
- hook/highlight ranking
- narrative and audience analysis
- edit planning
- caption and packaging generation
- evaluation and quality gates

## Rendering boundary

A render request pins a ProjectState version. The renderer must be reproducible: the same state version and render settings should produce functionally equivalent output.

Rendering stages:
1. resolve assets
2. validate media
3. build timeline graph
4. compose video/audio/captions/effects
5. encode
6. quality checks
7. store artifact and metadata

## Current implementation status

Implemented in the existing codebase:
- email/JWT authentication
- project CRUD and quotas
- media asset records and upload contract
- local S3-compatible storage stub
- backend tests for core APIs

Added in this architecture foundation:
- canonical ProjectState schemas
- sequence/track/clip timeline model
- optimistic state versioning
- deterministic edit-operation endpoint
- project-state persistence and indexes

Not yet implemented:
- production S3 adapter
- background analysis workers
- transcription/media intelligence
- LLM orchestration
- renderer
- editable mobile timeline connected to ProjectState
- AI evaluation system
