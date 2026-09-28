# Data Retention and Deletion

## Active account data

ShortCut keeps account, project, timeline, AI-plan, job and media records while
needed to provide an active account.

## Automatic expiry

MongoDB TTL indexes automatically expire:

- sessions;
- password-reset records;
- rate-limit buckets.

Presigned object URLs expire automatically.

## User deletion

Users can permanently delete their account from Profile.

The account-deletion service removes queued/running job records first, revokes
sessions and removes the user identity so no new authenticated work can be queued.
Workers use lease fencing: once the job record/lease is gone, stale workers cannot
commit durable results. Worker cleanup also removes objects produced after lease loss.

The deletion service then removes user-scoped application collections and deletes
the entire private object-storage prefix:

`users/<user_id>/`

This covers original uploads, derived media and exports stored beneath that prefix.

## Provider and infrastructure retention

Before public launch configure and document:

- MongoDB backup retention and restore procedure;
- S3 lifecycle rules for abandoned/old objects;
- log retention;
- Sentry event retention;
- AI-provider data controls;
- disaster-recovery snapshots.

Short-lived infrastructure backups or provider security logs may persist after an
in-product deletion until their configured retention periods expire. The published
Privacy Policy must accurately describe those periods once production providers are
finalized.
