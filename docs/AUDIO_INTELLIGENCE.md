# Audio intelligence: silence-aware editing

ShortCut AI now treats pauses as first-class editing evidence rather than relying only on transcript timestamps.

## Detection

The media-intelligence worker analyzes the normalized 16 kHz speech WAV with FFmpeg's `silencedetect` filter.

Configuration:

- `SILENCE_NOISE_DB=-35`
- `SILENCE_MIN_DURATION_SEC=0.35`
- `SILENCE_SNAP_WINDOW_SEC=0.75`

Detected intervals are persisted as time-aligned `start`, `end`, and `duration` values on the media-intelligence record.

Silence detection is an enhancement, not a hard dependency. If FFmpeg silence analysis fails for an otherwise valid asset, transcription and the remaining intelligence pipeline continue with an empty silence list.

## Edit-boundary refinement

Create For Me uses nearby silence boundaries to make cuts feel less abrupt.

For a selected transcript unit:

1. the cut-in may expand backward to the end of a nearby preceding silence;
2. the cut-out may expand forward to the start of a nearby following silence;
3. snapping is bounded by `SILENCE_SNAP_WINDOW_SEC`;
4. the system never moves a boundary inward across the transcript range, so it does not intentionally cut away spoken content.

The refined range is then passed through the existing duration constraints and non-overlap selection.

## Why this is deterministic

No LLM decides where silence exists. FFmpeg measures the audio signal and the planner applies a small deterministic boundary rule.

## Tests

The suite covers parser normalization, boundary snapping, and a generated tone -> silence -> tone WAV that is analyzed by the real FFmpeg filter in CI.

## Next

- silence-based dead-air removal proposals
- configurable breathing-room profiles by content type
- music beat/onset analysis
- transition timing against musical structure
- speaker-turn-aware cut refinement
