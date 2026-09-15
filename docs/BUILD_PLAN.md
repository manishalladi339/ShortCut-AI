# ShortCut AI — Build Plan

## Milestone 1 — Product foundation
- canonical ProjectState and operation protocol
- optimistic concurrency
- project-state persistence
- architecture documentation
- remove generated cache/build artifacts from tracked source
- CI and repeatable local development

## Milestone 2 — Media ingestion
- production object-storage adapter
- multipart uploads
- FFprobe metadata validation
- proxies, thumbnails and waveforms
- background job state machine
- retry/idempotency semantics

## Milestone 3 — Editing engine
- complete edit-operation vocabulary
- operation validation
- undo/redo and version history
- multiple sequences
- captions, transforms and audio properties
- deterministic RenderPlan

## Milestone 4 — Rendering
- FFmpeg graph builder
- captions and overlays
- transitions and audio mixing
- render workers
- artifact QC
- export presets

## Milestone 5 — Media intelligence
- transcription with word timestamps
- diarization
- shot/scene segmentation
- audio/music features
- semantic media representation
- embeddings and retrieval

## Milestone 6 — AI editing
- typed planner outputs
- Create For Me pipeline
- Create With Me command interpretation
- creator preferences and memory
- guardrails, retries and fallbacks
- evaluation datasets and quality metrics

## Milestone 7 — Mobile product completion
- robust upload manager
- job progress
- project-state sync
- preview/timeline editing
- AI assistant
- export/publish UX
- offline/reconnect behavior

## Definition of done
A release is product-level only when a user can create an account, upload media, obtain AI-assisted edits, modify the same canonical project state, render/export it, and repeat the workflow reliably with automated tests and observable failure states.
