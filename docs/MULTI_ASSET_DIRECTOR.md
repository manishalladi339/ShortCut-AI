# Multi-Asset Director Mode

Multi-Asset Director Mode builds a grounded longer-form story across multiple
spoken-source assets while using any analyzed visual asset — including still images —
as B-roll support.

## Intended use

Examples:
- two interviews + customer testimonials + B-roll + old photos
- founder interview + team footage + screen recordings + product images
- multiple conversations that need to become one coherent documentary-style edit

The mode is designed for prompts such as:

"Create a four-minute founder story. Open with the hardest moment, establish the
problem, reveal the product halfway, use customers as proof, and end personally."

## Standard vs Multi-Asset

Standard mode keeps the short-form limits:
- up to 300 seconds
- up to 30 primary story clips

Multi-Asset mode supports:
- up to 900 seconds
- up to 80 primary story clips
- configurable minimum source diversity
- configurable maximum share from one spoken source

The frontend currently defaults Multi-Asset plans to:
- minimum 3 spoken sources when available
- maximum 55% of story duration from one source
- up to 60 primary moments

## Grounded selection

Multi-Asset selection starts from the existing semantic/highlight candidate set.

It then adds explicit Director constraints:

1. Seed the strongest viable moments from distinct source assets.
2. Cap how much story duration one source can occupy.
3. Reward uncovered project topics.
4. Reward new source assets.
5. Penalize repeated use of an already-dominant source.
6. Preserve per-asset temporal non-overlap.
7. Trim only to duration/diversity budgets; never invent source ranges.

If too few spoken sources exist, the source-share cap relaxes only as much as is
mathematically necessary to produce a usable story.

## Story Director

The existing Story Director still structures the selected grounded moments into:
- hook
- context
- development
- proof
- payoff

Multi-Asset Mode does not replace Story Director; it gives Story Director a stronger,
source-diverse set of grounded evidence.

## Director brief and Source Mix

Every Multi-Asset plan stores a Director brief containing:
- selected spoken asset IDs
- source count
- per-source selected duration
- per-source selected moment count
- covered topic IDs
- visual-support asset IDs
- project analyzed-asset count
- requested diversity constraints

AI Director displays the Source Mix before apply so the creator can see whether the
story genuinely uses multiple inputs rather than trusting an opaque score.

No source is labeled as "founder", "customer", "expert", etc. unless that role exists
as explicit grounded metadata. The initial release uses the neutral role
"primary_spoken_source".

## Still images

Images are first-class visual intelligence sources.

For an image:
- Media Intelligence skips audio extraction/transcription.
- Vision analyzes the image as one visual observation.
- The visual description is embedded like video visual observations.
- Semantic B-roll retrieval can choose it when relevant.
- The planner creates a bounded hold duration on the overlay track.
- The renderer loops the image input for the complete B-roll slot.

Images do not become primary spoken story clips.

## Trust and safety

Multi-Asset Mode retains the normal ShortCut contract:
- exact ProjectState version
- reviewable AI plan
- exact source provenance
- no silent timeline mutation
- replace-existing-video requires explicit opt-in
- visual recommendations are grounded in stored visual observations
- speaker labels remain source-local
- still-image use is visible in clip metadata

## Current scope

The first production-beta release optimizes deterministic source/topic diversity.
Future iterations can add explicit user-defined roles such as "founder interview",
"customer proof", or "archive footage" once the UI supports grounded role assignment.
