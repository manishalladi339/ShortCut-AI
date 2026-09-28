# Data Retention and Deletion

## Active data

ShortCut keeps account, project, timeline, job, AI-plan and media records while needed to provide an active account.

## Automatic expiry

- sessions expire through a MongoDB TTL index;
- password-reset records expire through a MongoDB TTL index;
- rate-limit buckets expire through a MongoDB TTL index;
- presigned object URLs expire automatically.

## User deletion

Users can permanently delete their account from Profile.

Deletion is refused while jobs are queued or running to avoid workers recreating data after deletion. Once no active jobs remain, ShortCut:

1. enumerates original uploads, media derivatives and completed exports;
2. removes those objects from configured storage;
3. removes sessions, reset records, projects, timeline history, assets, jobs, exports, intelligence, AI proposals/plans, creator memory and audit logs;
4. deletes the user record.

If object-storage cleanup fails, database deletion does not proceed and the user is told to retry.

## Production infrastructure retention

Before public launch, configure:

- S3 lifecycle rules for abandoned/temporary objects;
- MongoDB backup retention;
- log retention;
- Sentry event retention;
- provider-side AI data controls;
- disaster-recovery snapshots.

These durations depend on the production providers and legal requirements and therefore cannot be finalized inside the repository alone.
