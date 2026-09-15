# AI plan review and selective apply

ShortCut AI separates AI planning from ProjectState mutation. This milestone
adds a safer review layer between those two stages.

## Operation identity

Every newly generated AI edit operation receives a unique operation ID before
the plan is persisted. The ID is returned through the AI plan API and remains
stable for the lifetime of that plan.

Older plans created before operation IDs remain fully applicable as complete
plans. They must be regenerated before granular review is available.

## Selective apply

The apply endpoint accepts an optional `operation_ids` allowlist:

`POST /api/v1/projects/{project_id}/ai-plans/{plan_id}/apply`

If `operation_ids` is omitted, the complete plan is applied exactly as before.

When IDs are supplied, ShortCut AI may omit optional operations such as
individual B-roll overlays and transcript captions.

## Primary-story safety rule

Primary `add_clip` operations are treated as one atomic timing group.

This is deliberate. Captions and B-roll are positioned against the output
timeline created by those primary clips. Allowing an arbitrary subset of
primary source parts would shift later timing and could make otherwise-grounded
caption or B-roll coordinates incorrect.

A reviewed request must therefore include every primary `add_clip` operation.
Optional B-roll and caption operations may then be accepted or rejected
individually.

Unknown IDs, duplicate IDs, and attempts to partially apply the primary story
are rejected before ProjectState is mutated.

## Audit trail

After successful application, the AI plan stores:

- `applied_operation_ids`
- `skipped_operation_ids`
- `applied_project_state_version`

The edit-history record stores the same reviewed selection together with the
applied operation count. This preserves which AI suggestions the user actually
accepted rather than only recording that a plan existed.

## Concurrency

Selective apply does not weaken optimistic concurrency. The plan must still
target the exact current ProjectState version, and all accepted operations are
committed through one candidate ProjectState replacement.

## Product role

This is the backend contract required for a Create With Me review UI: users can
keep the AI-selected story while independently rejecting an unwanted B-roll
shot or caption suggestion before committing the plan.
