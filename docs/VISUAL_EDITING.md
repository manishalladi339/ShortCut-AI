# Visual editing and B-roll retrieval

This milestone turns multimodal observations into editor-facing signals without pretending that recommendation and rendering are the same thing.

## Current capability

```text
scene detection
  -> representative frames
  -> visual observations
  -> source-time grounding
  -> visual editability signals
  -> visual semantic search
  -> ranked B-roll/source moments
```

### Visual editability signals

`services/visual_edit_signals.py` scores only observations that fall inside a candidate's source range. The score is deliberately small and bounded so visual metadata cannot overwhelm transcript relevance or highlight quality.

Signals currently include described-frame coverage, visible-person presence, shot variety, and on-screen text. Every contribution produces a human-readable reason.

### Visual semantic search

`POST /api/v1/projects/{project_id}/intelligence/visual-search`

The endpoint searches only completed media-intelligence records owned by the authenticated user and belonging to the requested project. It embeds the query and grounded visual descriptions, ranks them with cosine similarity, and returns exact source asset IDs and timestamps.

This can answer editor/planner requests such as:

- "show the product while the speaker explains the feature"
- "find a wide establishing shot"
- "find footage of the dashboard"

Results are recommendations, not timeline mutations.

## Why B-roll is not auto-applied yet

The current renderer is transcript/clip oriented. Automatically inserting B-roll before the ProjectState and renderer support overlay/secondary-video semantics end to end would create architecture theater: the API would claim an edit that the renderer cannot faithfully reproduce.

The next rendering milestone will add a deterministic secondary-video/overlay operation and render-plan support. Only then will the AI planner be allowed to emit executable B-roll operations.

## Next

- integrate bounded visual signals into highlight ranking
- precompute visual-description embeddings during media intelligence
- add secondary-video/overlay semantics to ProjectState
- implement deterministic B-roll render operations
- active-speaker-aware camera selection
- silence and beat intelligence
- creator preference memory
