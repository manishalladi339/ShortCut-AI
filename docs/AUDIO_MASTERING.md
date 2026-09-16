# Final Audio Mastering

ShortCut performs a final mastering pass after timeline compositing and caption
burn-in so quality checks apply to the exact file delivered to the creator.

## Pipeline

1. Build the deterministic timeline mix.
2. Apply clip volume, playback rate, fades and music ducking.
3. Burn captions when enabled.
4. Measure the finished audio stream with FFmpeg `loudnorm`.
5. Run a second loudness-normalization pass using the measured values.
6. Copy the already-rendered video stream while re-encoding only final AAC audio.
7. Probe and QA the mastered MP4.

The default targets are configurable:

- integrated loudness: **-14 LUFS**
- true peak: **-1.5 dBTP**
- loudness range target: **11 LU**

These are production defaults, not a claim that every platform uses one universal
playback target.

## Two-pass normalization

The first FFmpeg pass records:

- input integrated loudness;
- input true peak;
- input loudness range;
- input threshold;
- target offset.

The second pass feeds those measurements back into `loudnorm`. This is more
deterministic than applying a fixed gain or relying only on a one-pass limiter.

## No-signal handling

A fully silent mix can produce non-finite loudness values such as `-inf`.
ShortCut detects that case and preserves the file without attempting a second-pass
normalization. Export QA can still report long silence independently.

## Export metadata

Each completed render stores an `audio_mastering` object inside
`render_metadata` containing:

- mastering status;
- configured targets;
- before loudness / true peak / LRA;
- after loudness / true peak / LRA;
- normalization type when available.

## QA

Export QA verifies the mastering result.

Current tolerances:

- integrated loudness within 1 LU of target;
- output true peak no more than 0.2 dB above the configured target.

A miss produces a warning with the measured values. It does not silently mutate
the timeline or hide the finished export.

## Configuration

```env
AUDIO_MASTERING_ENABLED=true
AUDIO_TARGET_LUFS=-14.0
AUDIO_TRUE_PEAK_DBTP=-1.5
AUDIO_TARGET_LRA=11.0
```

Disabling mastering preserves the pre-master render while retaining the same
render/export pipeline.
