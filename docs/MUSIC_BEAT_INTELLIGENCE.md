# Music and beat intelligence

ShortCut AI is adding a deterministic timing signal for music-aware edits.

## Current milestone

The beat detector operates on decoded 16-bit PCM WAV audio. It computes short-time RMS energy, detects transient energy rises as onset candidates, and estimates a beat period only when the onset sequence is sufficiently regular.

The output is intentionally conservative:

- onset timestamps;
- estimated BPM;
- estimated beat period;
- regularity confidence;
- beat timestamps.

If the signal is too irregular, the estimator returns no beat grid rather than inventing one.

## Editing primitive

`nearest_beat()` can snap a proposed edit time to the closest measured beat only when that beat lies inside a caller-specified maximum shift window. This prevents music timing from moving an otherwise grounded cut by an arbitrary amount.

## Architecture rule

Music timing is signal-derived. An LLM may later choose whether a creator/style should use beat-synced edits, but it does not fabricate beat timestamps.

## Next integration

1. persist beat intelligence for suitable music/audio assets;
2. select an explicit music reference for a sequence;
3. map its beat grid to timeline time;
4. optionally snap B-roll entrances and transition boundaries within a small tolerance;
5. expose beat-alignment metrics in planner evaluation;
6. add generated click-track integration tests.

This milestone does not yet claim automatic music selection, source separation, emotional music matching, or production-grade tempo tracking for complex live music.
