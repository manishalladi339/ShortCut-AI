# Visual Transitions

ShortCut supports deterministic clip entrance/exit transitions in canonical ProjectState.

## Supported kinds

- `fade`
- `slide_left`
- `slide_right`
- `slide_up`
- `slide_down`

These are clip-local entrance/exit treatments. They do not invent source handles or
silently overlap adjacent clips.

## Why no fake cross-dissolve

A true cross-dissolve between two butt-cut story clips needs overlapping source
media from both sides of the edit. If ShortCut does not have validated source handles,
pretending to dissolve would either shorten the story, repeat frames or pull media
outside the approved source range.

The production-beta renderer therefore uses deterministic fades/slides until an
explicit source-handle model is added.

## Rendering

Fade transitions use alpha fade on the visual clip.

Directional slides are evaluated per frame in the compositor:

- slide-left entrance: off-canvas left -> configured clip position
- slide-right entrance: off-canvas right -> configured clip position
- slide-up entrance: below canvas -> configured position
- slide-down entrance: above canvas -> configured position

Exit transitions reverse the direction toward the appropriate canvas edge.

Motion keyframes remain active underneath transitions; the transition expression wraps
the current transform position rather than replacing it.

## Audio behavior

Visual slide transitions do not alter dialogue/audio carried by a video clip.

Standalone audio tracks support fade transitions only. This prevents a visual
transition enum from being silently interpreted as an audio effect.

## Create With Me

Examples:

- `Slide this shot in from the left`
- `Slide this shot out to the right`
- `Fade this shot out`
- `Fade the B-roll out`
- `Remove the transition from this shot`

Default duration is 0.25 seconds.

Language modifiers:
- quick / fast / snappy -> 0.18 seconds
- slow / smooth / gentle -> 0.40 seconds

Transition duration is capped to half of the target clip duration.

## Scope and safety

A transition can be applied only when the whole target clip is inside the approved
scope.

Story transition operations may mutate primary video clips.

B-roll transition operations are limited to AI/plan-authored overlays. User-authored
overlays are not silently modified.

Transition edits preserve:
- timeline start
- duration
- source start/duration
- clip order
- captions
- unrelated B-roll/audio

All changes remain reviewable and ProjectState-version fenced.

## Timeline review

The timeline inspector shows entrance and exit transition kinds and exposes quick
actions for story slide-in/fade-out and B-roll fade-out.
