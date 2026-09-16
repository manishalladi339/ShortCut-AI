# Project Intelligence and Story Director

ShortCut now synthesizes asset-level media analysis into a project-level view before
building an edit proposal.

## Project Intelligence

The project-intelligence layer reads completed media-intelligence records and builds:

- cross-asset semantic topic clusters from persisted embeddings;
- source-local speaker-presence summaries without claiming cross-video identity;
- visual-library summaries such as common objects, shot types, people presence, and on-screen text;
- auditable topic evidence with asset IDs, intelligence IDs, unit indices, timestamps, text, and speaker labels;
- stable full topic membership for downstream story planning.

The API exposes:

- `POST /api/v1/projects/{project_id}/project-intelligence` to rebuild the synthesis;
- `GET /api/v1/projects/{project_id}/project-intelligence` to inspect the latest synthesis.

Create For Me rebuilds this synthesis automatically from the analyzed media used by
the plan.

## Story Director

The Story Director creates a blueprint before the user applies edit operations. It
groups selected grounded source moments into explicit beats such as:

`hook -> context -> development -> proof -> payoff`

Every beat contains its intended duration, purpose, topic references, and exact
candidate evidence keys. Planner evaluation verifies that the story blueprint covers
the selected evidence exactly once and never references an unavailable candidate.

The mobile AI Director displays:

1. what ShortCut understood across the project;
2. the cross-asset topics it found;
3. the planned story beats;
4. the exact grounded source moments;
5. the granular edit operations that may be approved or skipped.

This keeps the product direction centered on project understanding and narrative
construction rather than isolated clip scoring.
