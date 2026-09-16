# Durable Jobs and Worker Recovery

ShortCut uses MongoDB as a durable job queue for media processing, media
intelligence, and rendering. Production workers use expiring ownership leases so a
crashed process cannot leave a job permanently stuck in `running`.

## Lease ownership

When a worker claims a queued job it receives a random `lease_token` and an
expiration timestamp.

Only the worker holding the current, unexpired token may:

- extend progress / heartbeat;
- mark the job succeeded;
- return it to the queue after a handled failure;
- mark it terminally failed.

The token is never exposed by the public Job API. The API exposes only
`heartbeat_at` and `lease_expires_at` for operational visibility.

Worker lease duration is never shorter than the configured maximum blocking work
window plus safety margin.

## Stale-job recovery

Before claiming new work, each worker recovers expired jobs of its own type.

If retry budget remains:

`running -> queued`

If retry budget is exhausted:

`running -> failed`

Recovery uses compare-and-set conditions on the expired lease, so two workers
cannot recover the same attempt simultaneously.

Legacy jobs created before leases existed are recoverable when their last
`updated_at` is older than one lease interval.

## Completion reconciliation

A process can crash after producing valid output but before all related Mongo
records are updated. ShortCut handles those windows explicitly.

### Media processing

If an asset was already marked `ready` for the same processing job, a retry
marks the durable job succeeded from the stored media metadata instead of probing
and generating derivatives again.

### Media intelligence

If the intelligence document already reached `completed` for the same job, a
retry restores the asset's intelligence pointers and completes the job without
rerunning transcription, vision, or embeddings.

### Rendering

The render job result is committed before the export row is finalized. If the
worker dies in that window, export GET/list requests reconcile the export from the
durable succeeded job result.

Rendered files use a deterministic storage key per export, so a retry safely
overwrites an orphaned partial upload.

## Duplicate render protection

Exports carry an internal `active` flag while queued/rendering.

A partial unique Mongo index prevents two active exports for the same:

- user;
- project;
- sequence;
- ProjectState version;
- export preset.

The API also performs a fast read-before-enqueue check. If two requests race
between the read and insert, the unique index chooses one winner and the losing
request returns the winner instead of creating a second expensive render.

## Operational configuration

`JOB_LEASE_SECONDS` is the baseline lease duration. Workers automatically raise
their effective lease when their configured render/analysis timeout requires a
longer window.

The default is:

`JOB_LEASE_SECONDS=1200`

A production deployment should monitor jobs whose heartbeat approaches lease
expiry; repeated lease recovery usually indicates worker resource pressure,
provider timeouts, or unexpectedly large inputs.
