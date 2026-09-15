# AI edit planner

The planner bridges media intelligence and the deterministic editing engine.

## Current flow

```text
Project objective
   + analyzed semantic units
   + embeddings
   + transparent highlight features
        |
        v
candidate ranking
        |
        v
non-overlapping clip selection
        |
        v
ProposedEditOperation[]
        |
        v
human review / later approval layer
        |
        v
validated EditOperation protocol
```

## Why proposals do not mutate the timeline directly

ShortCut AI keeps model/intelligence decisions separate from application state.
A planner can be wrong. A deterministic editing engine must still validate every
asset, time range, track and ProjectState version.

The first planner therefore stores **proposals**, not hidden mutations.

A separate apply endpoint accepts an explicit `expected_version` and applies the
selected clip operations in one atomic ProjectState replacement. Stale plans are
rejected. Existing timeline clips are never replaced unless the caller explicitly
sets `replace_existing_video_clips=true`.

## Ranking baseline

Each semantic unit gets:
- an auditable heuristic score based on duration, density, hook/question language,
  specificity and position
- semantic relevance to the user's/project's objective through embeddings
- a combined score

A greedy selector rejects overlapping source ranges and respects the requested
target duration and maximum clip count.

This baseline is intentionally measurable. Later narrative/LLM ranking can be
compared against it instead of replacing it with an opaque score.

## Apply contract

`POST /api/v1/projects/{project_id}/ai-plans/{plan_id}/apply`

Applying a plan:
- requires the exact ProjectState version the plan was created from
- rechecks asset readiness and ownership
- rechecks target track existence/lock state
- applies all current planner operations as a single ProjectState version
- writes edit history and an immutable snapshot
- marks the plan applied only after state persistence succeeds

This keeps **Create For Me** auditable and prevents silent overwrites.

## Current limitation

Selected clips are ordered by source chronology. Narrative re-ordering, hook/body/
payoff roles, audience analysis and generated captions are the next planner layer.

The API does **not** claim that the current baseline predicts virality. Scores are
selection heuristics, not engagement guarantees.
