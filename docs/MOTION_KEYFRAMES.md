# Motion Keyframes

ShortCut supports deterministic clip motion as part of canonical ProjectState.

## Data model

A clip transform can include up to eight normalized keyframes.

Each keyframe stores:
- `at`: clip progress from 0.0 to 1.0
- scale
- position X/Y
- easing

Motion must begin at progress 0 and end at progress 1. Normalized progress keeps
motion stable when a clip is moved or retimed.

Supported easing:
- linear
- ease_in
- ease_out
- ease_in_out

Rotation and opacity remain static in this first motion release.

## Rendering

FFmpeg evaluates transform expressions per frame.

Scale is evaluated in clip-local time before the clip is shifted onto the global
timeline. X/Y overlay position is evaluated in global timeline time after the shift.

Static transforms still use constant expressions and remain backward compatible.

## Create With Me

Initial natural-language motion support is intentionally conservative:

- “Add a subtle push-in to this shot”
- “Add a slow zoom in”
- “Use a Ken Burns push-in”
- “Remove the motion from this shot”
- “Make this shot static”

The first preset changes only transform keyframes. It does not change:
- timeline start
- clip duration
- source start/duration
- clip ordering
- captions
- B-roll
- audio

The planner uses the clip’s existing scale and position as the starting frame, so
subject-aware reframing is preserved rather than overwritten.

## Scope safety

A story clip receives motion only when the entire clip is contained inside the
approved scope. If a selected clip crosses the scope boundary, ShortCut refuses
rather than leaking the visual change outside the requested range.

## Product review

Motion is reviewable before apply and version-fenced like other Create With Me
operations. The timeline inspector shows the number of motion keyframes and exposes
a one-tap “Slow push-in” refinement for selected story clips.

## Current limit

The first release uses bounded push-in motion. Arbitrary multi-point editor-authored
curves, animated rotation/opacity and object tracking remain future extensions.
