# Visual Transitions

ShortCut stores clip entrance/exit transitions in canonical ProjectState. They are
versioned, reviewable, restorable and rendered deterministically.

## Supported visual transitions

- `fade`
- `slide_left`
- `slide_right`
- `slide_up`
- `slide_down`

These are clip-local entrance/exit treatments. They do not silently overlap
adjacent story clips or invent source media.

## Why there is no fake cross-dissolve yet

A true cross-dissolve between two butt-cut story clips requires validated source
handles on both sides of the edit.

Without those handles, an apparent dissolve would have to do at least one unsafe
thing:

- shorten the story;
- repeat/freeze frames;
- pull media outside an approved source range; or
- silently overlap content that was never approved.

ShortCut therefore ships deterministic fades/slides first. A real cross-dissolve
should be added only after source-handle availability is represented explicitly
in ProjectState.

## Rendering

Fade transitions use alpha fades on the visual clip.

Directional slide transitions are evaluated per frame by the compositor:

- slide-left entrance: off-canvas left -> configured clip position
- slide-right entrance: off-canvas right -> configured clip position
- slide-up entrance: below canvas -> configured clip position
- slide-down entrance: above canvas -> configured clip position

Exit transitions move toward the corresponding canvas edge.

Transform motion keyframes continue underneath the transition. A slide wraps the
current transform position instead of replacing the zoom/pan curve.

## Audio behavior

Visual slide transitions do **not** fade dialogue or other audio carried by a
video/overlay clip.

For audio processing:

- `fade` can create an audio fade;
- a visual slide on video/overlay contributes zero audio fade duration;
- a standalone audio clip with a slide transition is rejected explicitly.

This prevents visual transition semantics from leaking into the audio mix.

## Create With Me

Examples:

- `Slide this shot in from the left`
- `Slide this shot out to the right`
- `Fade this shot out`
- `Fade the B-roll out`
- `Remove the transition from this shot`

Default duration: **0.25 seconds**.

Modifiers:

- quick / fast / snappy -> 0.18 seconds
- slow / smooth / gentle -> 0.40 seconds

The chosen duration is capped to half of the target clip duration.

A slide request must include a direction. If the direction is ambiguous,
ShortCut refuses the edit rather than guessing.

## Scope and safety

A transition can be proposed only when the complete target clip is inside the
approved scope.

Primary story transitions target video clips.

B-roll transitions target overlay clips only when the overlay is AI/plan-authored.
User-authored overlays are preserved.

Transition edits preserve:

- timeline start;
- clip duration;
- source start and source duration;
- clip order;
- transform motion keyframes;
- captions;
- unrelated audio/B-roll.

All changes remain ProjectState-version fenced and reviewable before apply.

## Caption disambiguation

Commands such as:

- `Fade the captions in`
- `Slide the captions up`

remain caption-animation requests. The visual transition planner exits early when
the instruction explicitly targets captions/subtitles.

## Timeline review

The timeline inspector surfaces:

- entrance transition kind;
- exit transition kind;
- existing motion keyframe count.

Quick actions include:

- Slide in;
- Fade out;
- Fade B-roll out.

Each action opens Create With Me with the selected clip's exact time range.

## Tests

The transition milestone covers:

- story slide planning/apply;
- story fade-out;
- AI-only B-roll targeting;
- caption-fade disambiguation;
- removal while preserving geometry;
- duration capping;
- direction refusal;
- scope containment;
- user-authored overlay protection;
- slide position expressions;
- video-audio isolation;
- standalone audio slide rejection;
- generated-media FFmpeg slide/fade rendering.
