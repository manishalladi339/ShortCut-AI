# User-selected music beds

ShortCut AI can place a user-selected audio asset under a Create For Me edit as
a canonical audio-track clip.

## Source of the music

The planner does not search a music catalog and does not claim that an uploaded
track is licensed.

The caller explicitly supplies `music_asset_id`. The asset must belong to the
current user, be fully processed, and have kind `audio`.

Rights and licensing for user-provided audio are outside this milestone. A
future catalog integration must carry its own licensing/provenance contract.

## Planning contract

Create For Me accepts these optional controls:

- `music_asset_id`
- `music_source_start_sec`
- `music_volume` (default 0.12)
- `music_fade_sec` (default 0.75 seconds)

When music is requested, an unlocked canonical audio track must exist.

The selected asset must have enough source duration after
`music_source_start_sec` to cover the complete planned output. ShortCut AI
currently rejects music that is too short rather than silently looping,
time-stretching, or ending the bed early.

## Timeline representation

Music is proposed as an `add_music_bed` AI operation and, after review, is
stored as a normal ProjectState `Clip` on an `audio` track.

The clip:

- starts at output timeline zero;
- spans the complete planned primary edit;
- uses the user-selected source offset;
- uses deterministic volume;
- uses canonical fade-in/fade-out transitions;
- carries `music_bed` and `user_selected_music` provenance metadata.

There is no renderer-only music side channel.

## Fades

Music fades use the same first-class transition model as visual fades.

Each fade is capped at 25% of the music clip duration, so short edits cannot
produce overlapping entrance/exit fades.

## Rendering

The existing deterministic renderer mixes the audio-track clip with source
speech/audio using FFmpeg. Music volume and transition fades are executed from
the RenderPlan.

A generated-media integration test renders a real video plus synthesized music
and verifies that the exported MP4 contains both video and audio streams.

## Human review

Music-bed operations have stable AI operation IDs and are optional during
granular review. A user can reject the proposed music bed while retaining the
complete primary story, B-roll, and captions.

## Replacement behavior

When a new AI plan explicitly replaces the existing AI edit, prior AI-owned
music-bed clips are removed. Manual audio clips are preserved.

## Current boundaries

This milestone provides a user-selected static music bed. It does not yet
provide:

- licensed catalog search;
- AI music recommendation;
- automatic looping;
- dynamic speech ducking or side-chain compression;
- stem separation;
- beat-matched source selection;
- generative music.
