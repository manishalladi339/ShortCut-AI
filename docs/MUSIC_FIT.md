# Music fit policy

Create For Me now has an explicit music fit policy for user-selected audio beds.

## Modes

`music_fit_mode="require_full"` preserves the original strict behavior: the selected music source, starting at `music_source_start_sec`, must contain enough remaining duration to cover the planned output. If it does not, planning fails instead of silently fabricating audio.

`music_fit_mode="loop"` allows a shorter selected music asset to repeat until the planned output duration is filled.

Looping is opt-in. It is never inferred by the renderer.

## Canonical representation

A music clip stores `loop_source` in ProjectState. RenderPlan carries the same value. This means source repetition is part of the edit decision and can be reviewed, persisted, versioned and reproduced.

When looping is required, the proposed music-bed operation includes:

- `loop_source=true`
- the complete output duration
- the original selected asset ID
- fit-mode metadata
- the available original source duration
- the planned output duration

The normal music volume, fades and speech-responsive ducking still apply after repetition.

## Exact loop boundary

The first looping implementation repeats the complete source file through FFmpeg `-stream_loop -1`. Because that is the exact behavior being executed, a source offset other than zero is rejected when repetition is actually required. This prevents a misleading plan where the first cycle starts at one point but later cycles restart somewhere else.

If the selected source is already long enough, a non-zero source offset remains valid because no repeat occurs.

## Apply-time safety

Loop intent is permitted only for user-selected music-bed operations. The planner/apply path continues to validate asset ownership, readiness, media type and source bounds. A looping source must still begin inside the real audio asset.

## Rendering

The renderer adds `-stream_loop -1` only for clips whose canonical `loop_source` flag is true. Non-looping audio and all visual clips retain their existing input behavior. The output remains bounded by the canonical timeline duration.

## Verification

A generated-media integration test creates a 1.25-second 440 Hz music file and a 4-second visual timeline. The real FFmpeg renderer is asked to fill the 4-second music clip with explicit looping enabled. The test verifies:

- the final render remains approximately four seconds long;
- one audio source is reported as looped;
- decoded PCM near the end of the output still contains audible music, proving that the short source was repeated rather than falling silent.

## Current boundary

This version repeats the source at its file boundary and does not claim seamless musical loop-point discovery or crossfaded seam repair. Those are separate audio-intelligence features and should only be added when they are measured and tested rather than hidden behind a generic loop flag.
