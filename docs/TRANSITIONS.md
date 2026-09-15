# Deterministic transitions

ShortCut AI represents transitions as canonical clip properties rather than renderer-only effects.

## Current primitive

The first supported transition is `fade`.

A clip may define:

- `transition_in`
- `transition_out`

Each transition stores its kind and duration in sequence timebase ticks. Validation rejects a transition whose duration exceeds the clip duration.

## Edit lifecycle

`ProjectState Clip -> RenderPlan RenderClip -> FFmpeg filter graph`

Manual `add_clip` and `set_clip_properties` operations can create, update or remove fade transitions. Splitting a clip preserves only the original outer transitions: the left split keeps the original entrance, the right split keeps the original exit, and the new internal cut receives no accidental fade.

AI plan application also accepts transition payloads and writes them into the same canonical Clip model. This means AI-authored transitions do not bypass editor validation or rendering contracts.

## Rendering

For visual clips, the renderer applies alpha fades before deterministic track compositing. This is particularly useful for B-roll overlays because the primary visual remains visible underneath during the fade.

For clips with source audio, the same transition duration is applied as an audio fade. B-roll remains muted when its clip volume is zero.

## Product boundary

This milestone is a fade primitive, not a full transition library. Cross-dissolve between adjacent primary clips, wipes, motion transitions, easing curves and keyframed effects remain future work.

AI selection of fade duration is intentionally separate from the renderer. The renderer only executes explicit, validated transition values stored in ProjectState.
