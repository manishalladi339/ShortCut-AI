# Deterministic rendering boundary

ShortCut AI renders a **specific ProjectState version**, never an informal collection of UI edits.

## Compile step

`ProjectState(version N) -> RenderPlan`

The compiler:
- selects an explicit sequence
- resolves every enabled clip to an owned, processed media asset
- preserves track order for deterministic z-stacking
- skips muted tracks and disabled clips
- carries source timing, playback rate, volume, transform and media metadata
- compiles first-class caption cues
- calculates sequence duration
- pins the ProjectState version and timebase

The resulting plan is model-independent. An LLM cannot bypass it.

## Execution step

`RenderPlan -> FFmpeg filter graph -> encoded artifact -> storage`

The current executor supports:
1. multiple visual tracks and overlapping visual clips
2. deterministic track stacking
3. video and image visual assets
4. clip trim and timeline placement
5. playback-rate changes
6. scale, position, rotation and opacity transforms
7. source audio from video clips
8. standalone audio-track mixing
9. per-clip volume and playback-rate audio processing
10. silence for empty portions of the mix
11. first-class captions burned from SRT
12. H.264/AAC MP4 output
13. persisted export artifacts with signed download URLs

## AI B-roll overlays

Create For Me may emit an `add_broll_overlay` proposal only when the active sequence contains an unlocked `overlay` track and the planner has a grounded cross-asset visual match.

The proposal records the source asset, media-intelligence record, visual-observation index, observation timestamp and semantic relevance score. The selected source moment is currently bounded to at most three seconds.

When a user applies the AI plan, the backend validates that the B-roll asset is still owned, processed and visual, then writes the clip to the overlay track in the same optimistic-concurrency transaction as the primary edit and captions. B-roll clip volume is zero so the primary spoken audio continues underneath.

The render compiler requires no AI-specific bypass: an overlay is an ordinary canonical clip on an `overlay` track. The FFmpeg executor composites overlay tracks after lower-index visual tracks, so the B-roll temporarily replaces/covers the primary visual while preserving the primary audio mix.

When replacing an earlier AI-generated plan, only overlays tagged with the previous `ai_plan_id` are removed. Manually-created overlay clips are preserved.

## Version safety

An export stores the exact ProjectState version used to compile its RenderPlan. Later timeline edits therefore do not silently alter an already queued export.

ProjectState itself is snapshotted after edits. Historical versions can be listed, inspected and restored as a new version.

## Still to build

- transition primitives such as cross-dissolve and audio crossfade
- keyframed transforms and easing
- masks, tracking and stabilization
- color correction / grading
- richer caption styling and animation
- nested/compound sequences
- hardware-accelerated render profiles
- generated-media visual regression tests for B-roll compositing
- distributed worker scheduling and cancellation

This separation keeps rendering reproducible, testable and safe to invoke from AI-authored edit operations.
