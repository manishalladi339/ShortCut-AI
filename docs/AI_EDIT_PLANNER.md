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
audience + narrative structuring
        |
        v
hook / body / payoff roles
        |
        v
grounded clips + captions + B-roll + transitions
        |
        v
explicit apply transaction
        |
        v
ProjectState -> renderer
```

## Grounding and ranking

Each semantic unit gets:
- an auditable heuristic score based on duration, density, hook/question language,
  specificity and position
- semantic relevance to the project objective through embeddings
- a combined score

The selector rejects overlapping source ranges and respects target duration and
maximum clip count. Scores are selection heuristics, **not virality predictions**.

## Narrative layer

The planner now supports two narrative providers:

- `deterministic` — default baseline with no extra LLM call
- `openai` — optional OpenAI-compatible JSON narrative planner

Both operate only on already-selected grounded candidate keys.

The narrative layer produces:
- audience profile
- ordered candidate keys
- hook/body/payoff role assignment
- narrative summary
- caption suggestion
- CTA suggestion

The final edit plan stores the provider/model used so plans remain auditable.

## Grounded captions

When `include_captions=true`, each selected transcript unit also produces an
`add_caption` proposal aligned to its output timeline range. The caption text is
copied from the grounded transcript unit rather than invented.

## Why planning and applying are separate

A planner can be wrong. ShortCut AI therefore stores a proposal first.

`POST /api/v1/projects/{project_id}/ai-plans/{plan_id}/apply`

Application:
- requires the exact ProjectState version the plan was created from
- rejects stale plans
- rechecks asset readiness and ownership
- rechecks target track existence/lock state
- applies grounded clips and captions in one ProjectState replacement
- writes edit history
- writes an immutable snapshot
- marks the plan applied only after persistence succeeds

Existing timeline clips are never replaced unless the caller explicitly sets
`replace_existing_video_clips=true`.

## Planner evaluation

Every generated plan stores measurable baseline metrics including:
- selected duration and dead-air reduction
- average highlight score
- hook/payoff presence
- grounding integrity
- speaker count/switches and maximum same-speaker run
- rhythm-snapped B-roll count
- faded B-roll count and transition validity
- operation/candidate counts

Users can also submit human feedback:

`POST /api/v1/projects/{project_id}/ai-plans/{plan_id}/feedback`

Supported outcomes:
- accepted
- modified
- rejected

Project-level feedback metrics expose acceptance rate and outcome counts. This is
the beginning of a real evaluation dataset: later planner revisions can be
compared against actual human acceptance rather than subjective demo quality.

## Current limitations

Still to build:
- stronger narrative evaluation datasets
- automatic comparison of deterministic vs LLM planner variants
- animated caption styling
- dedicated music-track selection/mixing
- richer transition primitives and keyframes
- creator preference learning
- frontend review controls for accepting/rejecting individual AI operations
