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

Supported operations now include:

- diarized speaker removal with sequence-wide ripple;
- transcript captions: remove or restyle;
- AI B-roll overlays: remove;
- music beds: remove, mute, lower or raise volume.

Unsupported instructions return an error and leave the timeline untouched.

## Ripple-safe speaker removal

A command such as `Remove Speaker B` is grounded in the `primary_speaker`
metadata attached to AI-generated primary story clips.

ShortCut first identifies every matching primary clip fully contained by the
approved scope. It then creates one atomic `remove_speaker_ripple` operation
instead of a collection of unrelated clip edits.

When the operation is applied:

- selected primary clips are removed;
- retained primary clips keep their source ranges and ordering;
- later timeline content shifts earlier by the removed duration;
- transcript/AI captions fully inside the removed range are removed;
- later captions shift with the story;
- AI B-roll and music beds may be shortened or removed when they overlap the
  deleted range;
- synchronized items after the deleted range shift by the same amount.

ShortCut refuses the edit when it cannot preserve synchronization safely. Examples
include:

- a locked track that would lose sync;
- another primary clip ambiguously overlapping the deleted interval;
- user-authored/non-music media that would need destructive truncation;
- a caption that crosses a deletion boundary and would require rewriting its text.

This is intentionally more conservative than blindly ripple-deleting one track.

## Scope invariant

For localized operations, a target cue or clip is mutated only when the entire
item is contained inside the approved time range.

For speaker removal, only matching primary clips fully inside the requested scope
become deletion intervals. The resulting time removal must then be applied
consistently across the whole synchronized sequence.

## API

- `POST /api/v1/projects/{project_id}/constrained-edits`
- `GET /api/v1/projects/{project_id}/constrained-edits`
- `POST /api/v1/projects/{project_id}/constrained-edits/{proposal_id}/apply`

Each proposal records the source ProjectState version, interpreted intents,
preservation rules, exact operations, selected/skipped operation IDs and the
resulting version after apply.

## Next extensions

The same constrained-operation model will expand to:

- scoped pacing/speed changes such as “make the first 10 seconds faster”;
- semantic B-roll replacement using Project Intelligence retrieval;
- QA-driven approved fixes;
- more complex story restructuring with explicit preservation constraints.
