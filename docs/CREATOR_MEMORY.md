# Creator Memory

Creator Memory lets ShortCut adapt to a creator from observed editing behavior
without turning the editor into an opaque recommender.

## Evidence sources

The memory profile is derived only from product actions:

- optional AI Director operations the creator applied or skipped;
- explicit AI-plan outcomes: accepted, modified, rejected;
- constrained Create With Me operations that were actually applied.

It does not infer preferences from age, demographics, location, or unrelated
account/profile data.

## Learned preferences

The first version can learn:

- caption preset, relative size and vertical position;
- preference for fewer or more B-roll inserts;
- tendency to lower/remove music;
- optional operation keep ratios;
- aggregate plan acceptance behavior.

Each preference carries an evidence-derived confidence score. ShortCut avoids
strong adaptation while evidence is sparse.

## Planner behavior

Future Director plans snapshot the Creator Memory used for the plan.

Current automatic adaptations are intentionally narrow:

- learned caption styles are merged into new transcript captions;
- learned B-roll density can reduce how many automatic B-roll overlays are added.

The user still reviews every optional operation before apply. Creator Memory never
bypasses ProjectState version checks or operation-level approval.

## API

- `GET /api/v1/users/me/creator-memory`
- `POST /api/v1/users/me/creator-memory/refresh`

Memory refreshes automatically after:

- applying an AI Director plan;
- submitting plan feedback;
- applying a constrained Create With Me edit.

## Trust invariant

The AI Director displays the exact memory summary, evidence count and learned
preferences attached to each plan. A plan therefore remains reproducible and
auditable even if the creator profile changes later.
