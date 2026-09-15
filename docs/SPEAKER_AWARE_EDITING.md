# Speaker-aware editing

ShortCut AI now carries diarized speaker labels from transcription into AI planning and timeline metadata.

## Grounding

Speaker labels come from the transcription provider. ShortCut does not infer a real person's identity from a face or voice. Labels such as `A`, `B`, or provider-specific speaker IDs are treated as anonymous diarization labels.

Semantic units already split at speaker changes when labels are available. The planner now preserves those labels on highlight candidates.

## Planner controls

Create For Me accepts optional:

- `include_speakers`: only candidate units containing one of these diarized labels are eligible.
- `exclude_speakers`: candidate units containing one of these labels are removed.

If an include filter is present, unlabeled transcript units are not eligible.

## Timeline provenance

For selected single-speaker highlights, the primary speaker label is copied into:

- the highlight candidate;
- primary clip metadata;
- grounded caption style metadata.

Multi-speaker units keep their complete speaker list and do not claim a single primary speaker.

## Evaluation

Plan evaluation now records:

- number of distinct primary speakers selected;
- number of primary-speaker switches in narrative order.

These are observability metrics, not automatic quality judgments.

## Why this matters

Speaker provenance gives later editing stages a safe basis for:

- host-only or guest-only clip generation;
- speaker-specific caption styling;
- speaker-turn-aware cuts;
- camera-selection logic once visual active-speaker association is implemented.

## Not claimed yet

This milestone does not identify real people, match faces to voices, track faces, or automatically reframe around an active speaker.
