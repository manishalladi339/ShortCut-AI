# Production Deployment

ShortCut AI's public beta runs one API service plus three worker roles against
external MongoDB and private S3-compatible object storage. Caddy terminates HTTPS
in front of the API.

## Runtime topology

- **Caddy** — public ports 80/443, automatic HTTPS and reverse proxy.
- **API** — FastAPI auth/projects/editor/render endpoints; not directly internet-exposed.
- **Media worker** — probes uploads and creates derivatives.
- **Intelligence worker** — transcription, scene/vision analysis and embeddings.
- **Render worker** — FFmpeg rendering, audio mastering and Export QA.
- **MongoDB** — durable application state, rate-limit counters and job queue.
- **S3-compatible storage** — private uploads, derivatives and rendered exports.
- **Sentry** — error/performance monitoring.
- **Resend** — account-security/password-reset email.

Do not use local filesystem storage across independent production containers.

## Prerequisites

1. API domain/subdomain pointed to the deployment server.
2. Server with Docker/Compose and public ports 80/443.
3. External MongoDB with backups enabled.
4. Private S3 bucket in the deployment region.
5. OpenAI API key for configured AI providers, with budget alerts.
6. Resend API key and verified sender.
7. Sentry project/DSN.
8. Exact frontend origins for CORS.
9. Strong random JWT secret.
10. Final legal operator/support details for the frontend.

## DNS and HTTPS

Set `SHORTCUT_API_DOMAIN` in `.env.production`, then point that hostname to
the server's public IP.

Caddy obtains and renews TLS certificates automatically after DNS resolves and
ports 80/443 are reachable.

The FastAPI container is mapped only to loopback for diagnostics:

```text
Internet -> Caddy :443 -> api:8001
Host diagnostics -> 127.0.0.1:8001
```

## S3

Keep the bucket private. Apply a browser CORS rule equivalent to
`deploy/s3-cors.json`, replacing the example frontend origin with the real one.

Prefer an instance/workload role instead of long-lived AWS access keys. Grant only
the bucket/object permissions ShortCut needs.

Recommended production controls:

- block public access;
- encryption at rest;
- lifecycle rules for old/abandoned objects;
- versioning if required by the recovery plan;
- billing/storage alerts.

## Configure

```bash
cp .env.production.example .env.production
```

Replace every placeholder.

Production startup refuses unsafe settings including:

- weak JWT secrets;
- wildcard CORS;
- non-HTTPS public API URL;
- local storage;
- missing S3 bucket;
- missing or placeholder OpenAI key when OpenAI providers are enabled;
- missing or placeholder Resend key;
- missing or placeholder Sentry DSN;
- invalid storage/render limits;
- Google auth enabled without ShortCut-owned client IDs;
- missing Terms version.

Never commit `.env.production`.

## Password-reset delivery

Production requires:

- `PASSWORD_RESET_EMAIL_PROVIDER=resend`
- `RESEND_API_KEY`
- `PASSWORD_RESET_FROM_EMAIL`
- `PASSWORD_RESET_URL_TEMPLATE` containing the literal `{token}`

Reset tokens are stored as hashes and expire automatically through MongoDB TTL.

## Legal consent

Set `TERMS_VERSION` to the currently published Terms version.

Email signup requires explicit Terms/Privacy acceptance. First-time Google account
creation also records acceptance of the current version. The user record stores
`terms_version` and `terms_accepted_at`.

## Validate

```bash
docker compose -f docker-compose.prod.yml config

docker run --rm \
  -e SHORTCUT_API_DOMAIN=api.example.com \
  -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
```

## Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Health endpoints

```bash
curl -fsS https://api.example.com/api/v1/live
curl -fsS https://api.example.com/api/v1/ready
```

Readiness checks MongoDB and object storage and returns HTTP 503 when a dependency
is unavailable.

## Public-beta resource controls

Tune these in `.env.production` based on measured cost/capacity:

- maximum upload size;
- per-user storage allowance;
- maximum video/audio duration;
- maximum concurrent renders;
- auth/signup/reset rate limits;
- upload/analysis/AI-plan/render request limits.

The API also exposes incident kill-switches:

- `SIGNUPS_ENABLED`
- `AI_FEATURES_ENABLED`
- `RENDERS_ENABLED`

Use these to stop cost-generating or public-entry paths without rebuilding.

## Worker scaling

Workers claim jobs through MongoDB leases.

```bash
docker compose -f docker-compose.prod.yml up -d --scale render-worker=2
docker compose -f docker-compose.prod.yml up -d --scale intelligence-worker=2
```

Render workers are the most CPU/RAM intensive. Scale from measured queue depth,
render latency and host resources.

## Observability

Every API response includes `X-Request-ID`. API logs include request ID, method,
path, status and elapsed time.

Configure Sentry alerts for new errors and elevated error rates. Also monitor:

- worker failures/retries;
- queue depth;
- AI-provider errors/latency/spend;
- render latency;
- server CPU/RAM/disk;
- Mongo/S3 readiness;
- authentication/rate-limit spikes.

## Backups and retention

Enable MongoDB backups/snapshots and test restore procedures.

Configure S3 lifecycle and backup policies to match `docs/DATA_RETENTION.md`.
Provider-side log/event retention should also match the published privacy policy.

## Real production smoke test

After deployment, run:

```bash
python scripts/production_smoke.py \
  --base-url https://api.example.com \
  --email smoke@example.com \
  --password 'use-a-strong-test-password' \
  --media ./sample.mp4
```

Use `--delete-account` for a disposable test account.

This exercises the real upload, workers, AI analysis, AI Director, Create With Me,
1080p render, Export QA and download flow.

## Mobile builds

The Expo project includes `frontend/eas.json` with development, preview and
production build profiles.

The configured native application ID is `com.shortcutai.app`. Confirm that the
identifier is available in the final Apple/Google developer accounts before the
first store registration; change it before registration if necessary.

Store signing, submission and legal agreements require the owner's Apple/Google
developer credentials.

## Release gate

Follow `docs/PUBLIC_RELEASE_CHECKLIST.md`. Do not open the public beta until all
Required external infrastructure and real-media checks are complete.
