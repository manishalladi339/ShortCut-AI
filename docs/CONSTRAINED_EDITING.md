# Constrained Create With Me

Create With Me treats natural-language editing as a proposal against an exact
ProjectState version, not as permission to regenerate the timeline.

## Safety model

1. The user describes a change.
2. ShortCut resolves an explicit or inferred time scope.
3. The planner creates deterministic operations only for supported components.
4. The UI shows every operation and a preservation contract before apply.
5. The user may skip individual operations.
6. Apply uses optimistic concurrency against the proposal's exact ProjectState
   version and commits the approved operations in one state replacement.
7. A stale proposal is rejected instead of being silently rebased.

The first release deliberately protects primary story clips. Supported localized
components are:

- transcript captions: remove or restyle;
- AI B-roll overlays: remove;
- music beds: remove, mute, lower or raise volume.

Primary video cuts, cross-track ripple edits and replacement B-roll are not yet
executed by this planner. Unsupported instructions return an error and leave the
timeline untouched.

## Scope invariant

An operation is proposed only when the entire target cue or clip is contained in
the approved time range. This prevents a clip that crosses a scope boundary from
being mutated outside the user's requested region.

## API

- `POST /api/v1/projects/{project_id}/constrained-edits`
- `GET /api/v1/projects/{project_id}/constrained-edits`
- `POST /api/v1/projects/{project_id}/constrained-edits/{proposal_id}/apply`

Each proposal records the source ProjectState version, interpreted intents,
preservation rules, exact operations, selected/skipped operation IDs and the
resulting version after apply.

## Next extensions

The constrained-operation model is intended to expand to:

- sequence-wide ripple-safe primary clip changes;
- replacement B-roll selected through project semantic retrieval;
- scoped pacing changes;
- speaker removal with synchronized captions/overlays/audio;
- natural-language multi-step changes backed by the same preservation validator.
