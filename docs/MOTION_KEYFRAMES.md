# Motion Keyframes

ShortCut stores visual motion in the canonical clip transform instead of as an
opaque renderer effect. Motion remains versioned, reviewable and restorable with
the rest of ProjectState.

## First release scope

Motion keyframes animate:

- scale;
- horizontal position;
- vertical position.

Rotation and opacity remain static in this release.

This deliberately covers the most common creator motions:

- slow push-in / zoom in;
- pull-out / zoom out;
- pan left;
- pan right;
- pan up;
- pan down;
- subtle motion on B-roll.

## Normalized timing

Each transform keyframe stores an `at` value from `0.0` through `1.0`.

A motion curve must:

- contain at least two keyframes;
- begin at progress `0.0`;
- end at progress `1.0`;
- use strictly increasing progress values.

Normalized progress keeps a motion curve valid when a clip is moved or retimed.
It does not depend on absolute timeline ticks.

## Easing

Supported segment easing:

- `linear`
- `ease_in`
- `ease_out`
- `ease_in_out`

The renderer compiles each segment into a deterministic FFmpeg expression.
Values are clamped to the segment's local 0–1 progress before easing.

## Smart-reframe compatibility

Motion starts from the clip's existing static transform.

If smart reframing previously placed a subject using:

- scale = 3.2
- X = -120
- Y = 10

then a slow push-in begins from exactly that framing and increases scale from
there. Motion therefore layers on top of the reviewed smart reframe rather than
resetting it.

Removing motion clears only `transform.keyframes`. The static smart-reframe
transform remains intact.

## Create With Me

Examples:

- `Slowly zoom in on this shot`
- `Push in`
- `Zoom out`
- `Pan right`
- `Pan left`
- `Add subtle motion to the B-roll`
- `Remove the motion`

Motion targets complete visual clips inside the approved scope.

By default, a motion instruction targets primary video. Mentioning B-roll or an
overlay targets the overlay track instead.

The operation never changes:

- timeline start;
- clip duration;
- source start;
- source duration;
- audio;
- captions.

Camera-direction semantics are used for pans. For example, “pan right” moves the
underlying media left so the virtual camera travels toward the right side of the
source frame.

## Rendering

The FFmpeg renderer evaluates scale at clip-local time and X/Y positioning at
global overlay time.

Without keyframes, the existing static-transform rendering path remains
equivalent.

The first release uses a generated-media integration test to ensure dynamic
scale and overlay-position expressions execute through the production renderer.

## Timeline review

The timeline inspector shows the number of motion keyframes on a selected clip
and provides scoped actions such as:

- Slow push-in
- Add subtle motion

Those actions open Create With Me with the exact selected timeline range already
filled.

## Current limits

This release does not yet provide:

- arbitrary Bézier control handles;
- animated rotation/opacity;
- motion-path drawing;
- automatic multi-keyframe face tracking;
- per-frame manual keyframe editing in the mobile UI.

Those can build on the same canonical transform keyframe representation later.
