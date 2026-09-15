# Rhythm-aware editing

ShortCut AI now extracts deterministic **energy-onset markers** from normalized
audio and can use nearby markers to time B-roll entrances.

## Important terminology

This milestone does **not** claim full musical beat tracking or BPM estimation.

The detector measures short-time waveform energy and identifies strong increases
relative to a rolling local baseline. The resulting records are called
`rhythm_events` or onset markers.

This makes the signal useful for cuts and entrances while keeping the claim
aligned with what the implementation actually measures.

## Detection

The media-intelligence worker analyzes the normalized 16-bit PCM speech/audio
WAV using fixed-size windows.

Configurable inputs include:

- `RHYTHM_WINDOW_MS`
- `RHYTHM_BASELINE_SEC`
- `RHYTHM_ENERGY_RATIO`
- `RHYTHM_MIN_RMS`
- `RHYTHM_MIN_INTERVAL_SEC`

Each event stores:

- source time
- normalized strength
- RMS energy
- energy ratio against its local baseline

Rhythm analysis is optional evidence. If the WAV format or analysis fails, the
rest of media intelligence continues.

## Mapping through dead-air compaction

Create For Me may split one source highlight into multiple source segments after
dead-air removal. Rhythm markers are therefore mapped through those retained
segments into the compacted output timeline.

Events that fall inside removed source regions are discarded automatically.

## B-roll entrance timing

When `rhythm_snap_broll=true`, the planner looks forward from the planned
B-roll entrance for a nearby mapped onset.

The maximum forward movement is controlled by
`rhythm_snap_window_sec` (default 0.35 seconds).

If a qualifying onset is found:

1. the B-roll entrance moves to that output timeline tick;
2. its duration is reduced if needed so it stays inside the selected highlight;
3. the operation stores `rhythm_snapped`, the source onset time and strength;
4. planner evaluation counts the rhythm-snapped overlay.

If no nearby onset exists, the original entrance time remains unchanged.

## Architecture boundary

The AI chooses *which* grounded B-roll visual is relevant. Waveform analysis and
timeline arithmetic decide *when* the entrance may snap. The language model
cannot invent an onset timestamp.

## Next

- dedicated music-track analysis rather than only normalized program audio
- tempo/BPM estimation with confidence
- transition duration aligned to rhythmic structure
- audio crossfades and visual transition primitives
- creator-selectable pacing profiles
