# Conversation pacing

ShortCut AI now refines an already-grounded Create For Me story with two
deterministic pacing passes: internal dead-air compaction and conservative
speaker-run rebalancing.

## Internal dead-air compaction

Silence detection remains waveform-based. Once the planner has selected a
grounded transcript range, long silence intervals fully inside that source
range may be compacted.

The compactor:
- never removes silence at the selected clip's outer edges;
- only considers pauses at or above the request's `dead_air_min_sec`;
- retains a small amount of pause on both sides of a removed interval;
- never intentionally deletes transcript text;
- represents the result as multiple grounded source segments from the same
  original semantic unit.

Those source segments become contiguous primary timeline clips. This means a
ten-second selected source span containing two seconds of dead air can become
roughly eight seconds of output without requiring a generative model to guess
where the cut belongs.

Create For Me exposes:
- `remove_dead_air` (default true)
- `dead_air_min_sec` (default 0.9 seconds)

Candidate provenance includes the exact retained source segments and measured
dead-air reduction.

## Speaker-turn pacing

Narrative planning still decides hook/body/payoff ordering first. A conservative
post-pass can then break unusually long runs from the same diarized speaker.

`max_same_speaker_run` defaults to 2.

The pacing pass may only swap a later body clip with the current body clip.
Hook and payoff candidates are not moved by the rule. Unknown or multi-speaker
units are not treated as a known primary speaker.

This is intended to improve conversational rhythm without allowing a pacing
heuristic to rewrite the story structure.

## Evaluation

Planner evaluation now records:
- compacted selected duration;
- seconds of detected dead air removed;
- number of generated primary source parts;
- speaker count;
- speaker switches;
- maximum same-speaker run;
- grounding checks for primary clips, transcript captions, and B-roll overlays.

## Current boundary

This is deterministic structural pacing, not aesthetic taste modeling. It does
not yet analyze music, emotional prosody, facial reactions, or learned creator
preferences.
