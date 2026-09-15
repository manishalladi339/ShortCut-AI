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

## Version safety

An export stores the exact ProjectState version used to compile its RenderPlan.
Later timeline edits therefore do not silently alter an already queued export.

ProjectState itself is snapshotted after edits. Historical versions can be
listed, inspected and restored as a new version.

## Still to build

- transition primitives such as cross-dissolve and audio crossfade
- keyframed transforms and easing
- masks, tracking and stabilization
- color correction / grading
- richer caption styling and animation
- nested/compound sequences
- hardware-accelerated render profiles
- render quality-control checks beyond file existence/duration
- distributed worker scheduling and cancellation

This separation keeps rendering reproducible, testable and safe to invoke from
AI-authored edit operations.
