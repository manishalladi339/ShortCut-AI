# Speech-responsive music ducking

ShortCut AI can now lower a user-selected music bed while spoken program audio is present. The feature is deterministic signal processing, not an LLM-generated volume curve.

## Canonical state

Music ducking is stored on the canonical `Clip` as an `AudioDucking` configuration. The same configuration is carried into `RenderPlan`, so previews, exports and future editor clients can reason about the effect from ProjectState rather than hidden renderer metadata.

The validated controls are:

- `enabled`
- `threshold`
- `ratio`
- `attack_ms`
- `release_ms`
- `makeup`

The bounds match the supported deterministic FFmpeg sidechain-compression contract.

## Create For Me controls

When a user selects a music asset, Create For Me exposes:

- `music_ducking` — defaults to enabled
- `music_duck_threshold`
- `music_duck_ratio`
- `music_duck_attack_ms`
- `music_duck_release_ms`

The planning policy attaches those values to the proposed `add_music_bed` operation before the plan is persisted. Human review can still reject the music-bed operation completely.

## Renderer behavior

The renderer prepares each audio source on the timeline first. When one or more music clips have ducking enabled and primary program speech is available, it:

1. builds a speech sidechain bus from primary video audio;
2. preserves that bus unchanged for the final program mix;
3. splits the speech bus for every ducked music source;
4. applies FFmpeg `sidechaincompress` to each music source using the canonical settings;
5. mixes the untouched speech/program audio, compressed music and other non-sidechain audio into the final AAC output.

If no speech sidechain exists, the music is rendered normally instead of being muted or failing the render.

Standalone narration can opt into the speech sidechain later by carrying explicit `speech_source` or `voiceover` metadata. Ordinary sound effects are not treated as speech by default.

## Grounding boundary

The language model does not decide where the music becomes quieter. Actual audio amplitude drives the compressor at render time. The AI/user may select the policy and settings, while deterministic signal processing decides the instantaneous gain reduction.

## Verification

The integration test generates:

- a primary video whose audio is silent, then contains a 1 kHz speech-like tone, then returns to silence;
- a continuous 440 Hz music bed;
- a real H.264/AAC render through the production FFmpeg executor.

The rendered audio is decoded to PCM and a Goertzel frequency measurement verifies that the 440 Hz music component is materially lower during the speech interval than before and after it.

## Current boundary

This milestone does not perform source separation, semantic speech-vs-music classification, loudness normalization to LUFS, or automatic mastering. It establishes the canonical and deterministic sidechain path those features can build on.
