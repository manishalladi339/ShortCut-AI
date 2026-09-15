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

AI plan application also accepts transition payloads and writes them into the same canonical Clip model. Create For Me can now generate bounded fade transitions for grounded B-roll overlays. This means AI-authored transitions do not bypass editor validation or rendering contracts.

## Create For Me fade planning

When `broll_fade=true`, the planner generates matching fade-in and fade-out transitions for an executable B-roll overlay.

The planner never lets either fade consume more than 25% of the overlay duration, preventing the entrance and exit fades from overlapping on short clips. `broll_fade_sec` controls the requested maximum fade duration.

If the overlay entrance was aligned to a high-confidence beat grid, transition planning may shorten the fade to at most one quarter beat. This is deterministic arithmetic over measured rhythm evidence; an LLM does not invent transition timing.

The operation metadata records the transition strategy, planned duration in ticks, and planned duration in seconds so the decision remains inspectable.

## Rendering

For visual clips, the renderer applies alpha fades before deterministic track compositing. This is particularly useful for B-roll overlays because the primary visual remains visible underneath during the fade.

For clips with source audio, the same transition duration is applied as an audio fade. B-roll remains muted when its clip volume is zero.

## Product boundary

This milestone is a fade primitive, not a full transition library. Cross-dissolve between adjacent primary clips, wipes, motion transitions, easing curves and keyframed effects remain future work.

Transition selection remains separate from the renderer. The planner proposes explicit bounded values, ProjectState validates and owns them, and the renderer only executes those validated values.
