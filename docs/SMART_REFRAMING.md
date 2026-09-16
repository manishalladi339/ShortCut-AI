# Subject-Aware Smart Reframing

ShortCut can propose portrait-friendly crops for primary story clips when visual
evidence is strong enough.

## Trust model

Smart reframing is deliberately evidence-gated.

ShortCut does **not**:

- perform face recognition;
- infer a person's identity;
- claim that a visible face matches a diarized speaker;
- link a person across frames.

Vision analysis stores only frame-local visible subjects with:

- a normalized bounding box;
- prominence;
- optional visible speaking-likelihood;
- a frame-local label.

## When ShortCut reframes

### Single-person shots

A shot may be reframed when exactly one visible subject is present and that subject
has sufficient visual prominence.

### Multi-person shots

A multi-person shot is reframed only when one visible subject has a strong speaking
cue and a meaningful confidence margin over the others.

Ambiguous multi-person shots remain unchanged.

## Crop calculation

The renderer already supports clip transforms:

- scale;
- position X/Y;
- rotation;
- opacity.

The smart-reframe planner uses the source dimensions, output dimensions and
subject box to calculate a bounded cover crop.

It:

- fills the target frame;
- keeps the selected visible subject near the horizontal center;
- places the subject slightly above vertical center when geometry allows;
- applies only a limited extra zoom for wide shots;
- refuses invalid/out-of-frame geometry;
- returns no transform when the source is already appropriately framed.

## Provenance

Every proposed reframe records:

- source visual observation index and timestamp;
- subject box;
- frame-local subject label;
- evidence strategy;
- confidence;
- people count;
- visible speaking-likelihood when available;
- `identity_claimed: false`.

The transform and provenance are stored in the AI plan. When approved, the
transform is written into canonical ProjectState and therefore becomes part of the
auditable timeline.

## Product behavior

AI Director exposes a **Subject-aware reframing** toggle, enabled by default.

Grounded source moments display the evidence used for each proposed reframe,
including the strategy, confidence and explicit note that no identity matching was
performed.

The timeline inspector surfaces smart-reframe provenance on clips after apply.

## Evaluation

Planner evaluation records:

- number of smart-reframed primary clips;
- transform validity;
- whether reframe provenance is grounded.

A reframe is considered ungrounded when required observation provenance is
missing or when metadata claims identity matching.
