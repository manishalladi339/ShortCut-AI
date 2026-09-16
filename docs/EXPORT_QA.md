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

## Product surface

The latest export in AI Director displays:

- QA status: passed / warnings / failed;
- issue and warning counts;
- the first actionable issues with timestamps;
- suggested next actions;
- the link to the finished video.

Future work can connect issues marked auto-fixable to constrained Create With Me
operations and provide a version-safe "Fix approved issues" workflow.
