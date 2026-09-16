# Multi-Asset Director Mode

Multi-Asset Director Mode extends the existing grounded AI Director for projects
containing many spoken and visual sources.

## Goal

The mode is designed for prompts such as:

> Here are several interviews, testimonials, B-roll clips, screen recordings, old
> photos and music. Build a coherent founder story, preserve the strongest source
> moments and use visual evidence to support the story.

It does not assign invented identities or claim that a source is an interview,
testimonial or customer unless that information is explicitly present elsewhere.

## Story-source selection

Primary story moments still come from grounded transcript semantic units.

Multi-Asset Mode adds deterministic constraints on top of relevance/highlight scoring:

1. seed the story from distinct spoken-source assets;
2. reward previously uncovered project topics;
3. reward a new source asset;
4. penalize repeated use as a source approaches its duration share cap;
5. preserve per-asset non-overlap;
6. preserve global target-duration and clip-count budgets.

Default source constraints:

- requested minimum spoken sources: 3
- maximum requested duration share from one source: 55%

If fewer spoken sources exist, the cap relaxes only as much as mathematically
necessary so a valid cut can still be produced.

## Long-form limits

Standard Director Mode remains capped at:

- 300 seconds
- 30 primary clips

Multi-Asset Director Mode supports:

- up to 900 seconds
- up to 80 primary clips

The mobile UI automatically increases the clip budget for longer targets.

## Director brief

Every multi-asset plan records a Director brief containing:

- objective
- target duration
- requested diversity constraints
- analyzed asset count
- selected spoken-source count
- selected source IDs
- covered project topic IDs
- selected source mix
- visual-support asset IDs
- a human-readable summary

The AI Director UI shows this before apply.

## Source mix

For each selected spoken source, the plan reports:

- source asset ID / filename
- selected clip count
- selected source duration
- semantic-unit count
- visual-observation count
- source-local speaker count

The role is deliberately descriptive: `primary_spoken_source`.

## Still images

Still images are now valid visual-intelligence sources.

Image analysis:

- skips audio extraction/transcription;
- runs a single frame-local vision observation;
- embeds the grounded visual description;
- makes the image eligible for semantic B-roll retrieval.

When an image is selected as B-roll, ShortCut creates a bounded still-image hold
(up to the normal B-roll duration target) and marks the overlay provenance with:

- `source_asset_kind: image`
- `still_image_hold: true`

## Trust and review

Multi-Asset Mode still follows the same trust contract:

- AI plans do not silently mutate ProjectState;
- primary story operations stay required as one coherent cut;
- optional B-roll/captions/music remain reviewable;
- every source moment retains asset/intelligence/unit provenance;
- ProjectState version fencing applies at plan apply time;
- final render QA runs after export.

## Current scope

Primary story narration currently comes from analyzed video transcript units.
Audio-only sources can be used by other audio workflows but are not yet promoted
to visual primary-story clips.

Still images and visual-only video are supporting visual evidence rather than
invented spoken story sources.
