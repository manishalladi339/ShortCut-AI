# Production Deployment

ShortCut AI production beta runs one API service plus three worker roles against
shared MongoDB and S3-compatible object storage.

## Runtime topology

- **API** — FastAPI auth/projects/editor/render endpoints.
- **Media worker** — probes uploads and creates derivatives.
- **Intelligence worker** — transcription, scene/vision analysis and embeddings.
- **Render worker** — FFmpeg rendering, audio mastering and Export QA.
- **MongoDB** — durable application state and job queue.
- **S3-compatible storage** — shared uploads, derivatives and rendered exports.

Do not use local filesystem storage across independent production containers.

## Prerequisites

1. External MongoDB with backups enabled.
2. S3 bucket in the deployment region.
3. OpenAI API key for the configured transcription/vision/embedding providers.
4. HTTPS domain for the API.
5. Exact frontend origins for CORS.
6. A strong random JWT secret.

The S3 workload identity should permit the object operations ShortCut uses and bucket
health checks. At minimum this normally means object Get/Put/Delete plus bucket
metadata/list permission required by `HeadBucket`.

## Configure

```bash
cp .env.production.example .env.production
```

Replace every placeholder. Production startup refuses:

- weak JWT secrets;
- wildcard CORS;
- non-HTTPS public API URLs;
- local storage;
- missing S3 bucket;
- missing OpenAI key when an OpenAI provider is enabled.

Never commit `.env.production`.

## Validate the compose file

```bash
docker compose -f docker-compose.prod.yml config
```

## Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The API container runs as a non-root user and has an internal liveness healthcheck.

## Health endpoints

Process liveness:

```bash
curl -fsS https://api.example.com/api/v1/live
```

Dependency readiness:

```bash
curl -fsS https://api.example.com/api/v1/ready
```

Readiness checks MongoDB and storage. A dependency failure returns HTTP 503.

The legacy `/api/v1/health` endpoint remains a liveness alias for compatibility.

## Worker scaling

Workers claim jobs through MongoDB leases, so multiple replicas can safely compete
for queued work.

Examples:

```bash
docker compose -f docker-compose.prod.yml up -d --scale render-worker=2
docker compose -f docker-compose.prod.yml up -d --scale intelligence-worker=2
```

Render workers are the most CPU/RAM intensive. Do not colocate too many FFmpeg jobs
on a small host.

## Crash recovery

Running jobs carry lease tokens and expiration timestamps.

When a worker disappears:
- expired work is requeued while retry budget remains;
- exhausted work becomes terminally failed;
- stale workers cannot commit after ownership moved;
- completed media/intelligence can be reconciled without repeating expensive work;
- succeeded render job results can repair incomplete export rows.

## Logs and request tracing

Every API response includes `X-Request-ID`.

API logs include:
- request ID;
- method/path;
- HTTP status;
- elapsed milliseconds.

Pass your platform request ID as `X-Request-ID` to correlate edge/API logs.

Worker logs should be shipped to your platform log aggregator.

## Storage durability

Rendered outputs and uploads live in S3. Configure:
- versioning if appropriate;
- lifecycle/retention rules for old exports;
- encryption at rest;
- blocked public access;
- least-privilege workload credentials.

Presigned URLs provide upload/download access; the bucket should remain private.

## MongoDB durability

Enable managed backups or snapshots. Collections contain:
- users/sessions;
- projects and canonical ProjectState;
- media intelligence;
- AI plans and constrained proposals;
- job queue state;
- exports and QA reports;
- audit logs.

## Quotas

The free beta defaults to 3 projects per UTC calendar month.

Quota consumption:
- resets automatically when the UTC month changes;
- is atomic across concurrent requests;
- applies to new projects and duplicates;
- rolls back best-effort if project persistence fails.

Paid plans remain disabled until billing is intentionally enabled.

## Rollout checklist

Before opening the beta:

1. `backend-ci` and `frontend-ci` green on the release commit.
2. Production env validation passes.
3. `/api/v1/ready` returns 200.
4. Upload a real video and image.
5. Wait for Media Intelligence to complete.
6. Build and review an AI Director plan.
7. Apply to canonical ProjectState.
8. Render a vertical 1080p export.
9. Verify audio mastering and Export QA.
10. Run a QA repair and re-render.
11. Test worker restart during a queued/running job.
12. Verify S3 export URL and Mongo backup policy.
