# Motion Keyframes

ShortCut stores visual motion in canonical ProjectState instead of hiding it in
the renderer. Motion is therefore versioned, reviewable, restorable and visible
to later editing operations.

## Supported motion

The first release animates:

- scale
- horizontal position
- vertical position

This covers common creator motions:

- slow push-in / zoom in
- pull-out / zoom out
- pan left / right
- pan up / down
- subtle B-roll motion
- clearing motion back to a static shot

Rotation and opacity remain static in this release.

## Normalized keyframe timing

Every transform keyframe stores an `at` value from `0.0` to `1.0`.

A valid motion curve:

- has at least two keyframes
- begins at `0.0`
- ends at `1.0`
- has strictly increasing progress values

Normalized progress means a motion survives moving or retiming a clip without
being tied to old absolute timeline ticks.

## Easing

Supported easing modes:

- `linear`
- `ease_in`
- `ease_out`
- `ease_in_out`

The renderer compiles each segment into deterministic FFmpeg interpolation
expressions and clamps local segment progress to 0–1.

## Smart-reframe compatibility

Motion starts from the clip's existing static transform.

If subject-aware reframing already produced:

- scale = 3.2
- X = -120
- Y = 10

then a slow push-in begins from exactly that framing rather than resetting the
shot.

Removing motion clears only `transform.keyframes`; it preserves the static
smart-reframe scale and position.

## Pan safety

Directional pans can expose a canvas edge if the source is not already cropped.

ShortCut therefore proposes a pan only when crop slack is known from either:

- subject-aware reframe provenance, or
- an existing static scale of at least 1.1.

Pans also add a small compensating zoom while moving. If edge coverage is not
provable, ShortCut returns no matching safe edit instead of guessing.

Camera-direction semantics are used: for example, “pan right” moves the media
left so the virtual camera travels toward the right side of the source image.

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

By default, motion commands target primary video. Mentioning B-roll or overlay
targets the overlay track.

A motion operation does **not** change:

- timeline start
- clip duration
- source start
- source duration
- audio
- captions

## Renderer

Scale is evaluated in clip-local time.

Overlay X/Y positioning is evaluated after the clip has been shifted into global
timeline time. This distinction keeps motion correct for clips that begin later
in the sequence.

Without keyframes, the static-transform path remains equivalent to existing
rendering.

A generated-media integration test renders a real H.264 clip through the same
FFmpeg executor used by exports, so dynamic expressions are validated beyond
string-generation unit tests.

## Timeline review

The timeline inspector shows the keyframe count for a selected clip and exposes
scoped actions such as:

- Slow push-in
- Add subtle motion to B-roll

Those actions open Create With Me with the selected clip's exact start/end range.

## Current limits

This release intentionally does not include:

- arbitrary Bézier handles
- animated rotation or opacity
- drawn motion paths
- automatic per-frame face tracking
- direct manual keyframe handles in the mobile timeline

Those can build on the same canonical transform representation later.
