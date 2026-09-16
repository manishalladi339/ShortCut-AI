# Export Quality Assurance

ShortCut validates both the edit timeline and the actual rendered MP4 before the
export is presented as finished.

## Core render validation

The render worker already treats these as hard render failures:

- missing/invalid output duration;
- duration materially different from the RenderPlan;
- wrong output dimensions;
- missing video stream.

## Post-render QA

After core validation, ShortCut creates a structured QA report. QA warnings do not
invalidate a usable export.

### Timeline checks

- uncovered primary-video gaps that may become black frames;
- repeated nearby B-roll from the same source;
- overlapping captions;
- captions with high reading rate;
- overly long caption cues;
- captions extending beyond export duration.

### Rendered-file checks

Using FFmpeg against the final MP4:

- sustained near-black segments;
- long silent sections;
- very low average audio level;
- peaks extremely close to digital full scale.

Every issue includes a category, severity, timestamp where available, evidence and
a suggested action. The system intentionally does not generate a synthetic quality
score.

## Failure behavior

If advanced FFmpeg signal analysis is unavailable, the render still completes after
core validation. The QA report records a nonblocking warning so the absence of a
check is visible rather than silently ignored.

## Reviewable safe fixes

For QA findings that can be repaired deterministically, AI Director exposes
`Review safe QA fixes`.

The first fix set is intentionally limited to caption problems:

- overlapping caption cues;
- overlong caption text that can be split without changing the words;
- captions extending beyond the primary visual timeline.

ShortCut creates a normal constrained-edit proposal instead of mutating the
timeline automatically. Every repair is reviewable and can be included or skipped.

A QA fix proposal is valid only when the current ProjectState version exactly
matches the version used to produce the export. If the timeline changed after the
render, ShortCut requires a fresh export before proposing fixes.

Caption repair invariants:

- preserve the exact original text;
- keep replacement cues inside the original cue interval;
- never create overlapping replacement cues;
- preserve primary story clips, B-roll and music decisions;
- retain the original caption style while adding QA provenance.

Audio-level warnings are recommendations for now. They are no longer marked
auto-fixable until ShortCut has a dedicated final-mix gain stage.

## Product surface

The latest export in AI Director displays:

- QA status: passed / warnings / failed;
- issue and warning counts;
- the first actionable issues with timestamps;
- suggested next actions;
- the link to the finished video.

The constrained proposal can be applied in Create With Me and then re-rendered,
allowing Export QA to verify whether the approved repairs resolved the issue.
