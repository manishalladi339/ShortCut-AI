# Deterministic rendering boundary

ShortCut AI renders a **specific ProjectState version**, never an informal collection of UI edits.

## Compile step

`ProjectState(version N) -> RenderPlan`

The compiler:
- selects an explicit sequence
- resolves every enabled clip to an owned, processed media asset
- rejects missing or still-processing media
- normalizes clip ordering
- calculates sequence duration
- pins the ProjectState version and timebase

The resulting plan is deliberately model-independent. An LLM cannot bypass it.

## Execution step (next milestone)

`RenderPlan -> FFmpeg graph -> encoded artifact -> quality checks`

The executor will:
1. materialize source/proxy assets
2. trim and time-shift clips
3. compose tracks
4. mix audio
5. burn or sidecar captions
6. apply transitions/effects represented in ProjectState
7. encode to a selected export preset
8. validate output duration/container/streams
9. persist the final artifact and render metadata

This separation makes rendering reproducible, testable and safe to invoke from AI-authored edit operations.
