# Rhythm-aware editing

ShortCut AI now extracts deterministic **energy-onset markers** from normalized
audio and can use nearby markers to time B-roll entrances.

## Important terminology

The detector first measures short-time waveform energy and identifies strong
increases relative to a rolling local baseline. These are persisted as
`rhythm_events` or onset markers.

A second deterministic stage may estimate BPM and a regular beat grid, but only
when at least several measured onset intervals fall inside the supported tempo
range and pass a regularity-confidence threshold. Irregular material returns no
beat grid rather than fabricating one.

## Detection

The media-intelligence worker analyzes the normalized 16-bit PCM speech/audio
WAV using fixed-size windows.

Configurable inputs include:

- `RHYTHM_WINDOW_MS`
- `RHYTHM_BASELINE_SEC`
- `RHYTHM_ENERGY_RATIO`
- `RHYTHM_MIN_RMS`
- `RHYTHM_MIN_INTERVAL_SEC`

Each onset event stores:

- source time
- normalized strength
- RMS energy
- energy ratio against its local baseline

When onset spacing is regular enough, `beat_grid` additionally stores:

- estimated BPM
- beat period
- regularity confidence
- deterministic beat timestamps across the observed onset range

Rhythm analysis is optional evidence. If the WAV format or analysis fails, the
rest of media intelligence continues.

## Mapping through dead-air compaction

Create For Me may split one source highlight into multiple source segments after
dead-air removal. Rhythm markers are therefore mapped through those retained
segments into the compacted output timeline.

Events that fall inside removed source regions are discarded automatically.

## B-roll entrance timing

When `rhythm_snap_broll=true`, the planner looks forward from the planned
B-roll entrance for a nearby timing marker. A confidence-gated beat grid is
preferred when available; otherwise the planner falls back to measured energy
onsets.

The maximum forward movement is controlled by
`rhythm_snap_window_sec` (default 0.35 seconds).

If a qualifying onset is found:

1. the B-roll entrance moves to that output timeline tick;
2. its duration is reduced if needed so it stays inside the selected highlight;
3. the operation stores `rhythm_snapped`, timing-signal type, source time,
   strength, and BPM/confidence when a beat grid was used;
4. planner evaluation counts the rhythm-snapped overlay.

If no nearby onset exists, the original entrance time remains unchanged.

## Architecture boundary

The AI chooses *which* grounded B-roll visual is relevant. Waveform analysis and
timeline arithmetic decide *when* the entrance may snap. The language model
cannot invent an onset timestamp.

## Next

- dedicated music-track analysis rather than only normalized program audio
- stronger tempo tracking for missing/subdivided beats
- transition duration aligned to rhythmic structure
- audio crossfades and visual transition primitives
- creator-selectable pacing profiles
