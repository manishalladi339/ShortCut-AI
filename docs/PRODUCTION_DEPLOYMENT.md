# Production Deployment

ShortCut AI public beta runs one API service plus three worker roles against external MongoDB and private S3-compatible object storage. Caddy terminates HTTPS in front of the API.

## Topology

- **Caddy** — public ports 80/443, automatic HTTPS, reverse proxy.
- **API** — FastAPI auth/projects/editor/render endpoints; loopback/internal only.
- **Media worker** — probes uploads and creates derivatives.
- **Intelligence worker** — transcription, scene/vision analysis and embeddings.
- **Render worker** — FFmpeg rendering, audio mastering and Export QA.
- **MongoDB** — durable application state, rate limits and job queue.
- **S3-compatible storage** — uploads, derivatives and exports.
- **Sentry** — error/performance monitoring.
- **Resend** — password-reset email.

## Prerequisites

1. Domain/subdomain for the API.
2. Server with Docker/Compose and public 80/443.
3. External MongoDB with backups.
4. Private S3 bucket.
5. OpenAI API key with budget alerts.
6. Resend verified sender.
7. Sentry project/DSN.
8. Exact frontend origin.
9. Strong random JWT secret.

## DNS

Point the API hostname to the server before starting Caddy.

Example:

`api.example.com -> server public IP`

Caddy obtains and renews TLS certificates automatically after DNS resolves and ports 80/443 are reachable.

## S3

Keep the bucket private. Apply a browser CORS rule equivalent to `deploy/s3-cors.json`, replacing the example origin with the real frontend origin.

Prefer an instance/workload role. If static credentials are unavoidable, grant only the bucket/object operations ShortCut requires.

Configure lifecycle rules for temporary/abandoned objects and enable encryption/backups/versioning as appropriate.

## Configure

```bash
cp .env.production.example .env.production
```

Replace every placeholder.

Production startup refuses unsafe settings including:

- weak JWT secret;
- wildcard CORS;
- non-HTTPS public API URL;
- disabled rate limiting;
- local storage;
- missing S3 bucket;
- placeholder/missing OpenAI key when OpenAI providers are enabled;
- placeholder/missing Sentry DSN;
- missing Resend configuration.

Never commit `.env.production`.

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

The API remains available locally at `127.0.0.1:8001` for diagnostics, while internet traffic uses Caddy over HTTPS.

## Health

```bash
curl -fsS https://api.example.com/api/v1/live
curl -fsS https://api.example.com/api/v1/ready
```

Readiness verifies MongoDB and object storage and returns HTTP 503 when a dependency is unavailable.

## Public-beta limits

Defaults are configurable in `.env.production`:

- 1 GiB maximum single upload;
- 10 GiB user storage cap;
- 60-minute maximum input media duration;
- auth/upload/AI/render per-minute rate limits;
- 20 media-intelligence jobs/day for free users;
- 10 renders/day for free users;
- 30 AI-edit requests/day for free users;
- 2 concurrent renders per free user.

Tune these only after observing real cost and queue data.

## Worker scaling

Workers claim jobs through MongoDB leases.

Examples:

```bash
docker compose -f docker-compose.prod.yml up -d --scale render-worker=2
docker compose -f docker-compose.prod.yml up -d --scale intelligence-worker=2
```

Render workers are CPU/RAM intensive. Scale based on measured queue depth and host capacity.

## Monitoring

Configure Sentry alerts for new errors and elevated error rates. Ship container logs to the hosting provider/log aggregator.

Monitor:

- worker failures and retries;
- queue depth;
- OpenAI latency/errors/spend;
- render latency;
- server CPU/RAM/disk;
- Mongo/S3 readiness;
- rate-limit spikes.

## Backups and retention

Enable MongoDB backups/snapshots and test restore procedures.

Configure S3 lifecycle/retention and backup policies. See `docs/DATA_RETENTION.md`.

## Release checklist

See `docs/PUBLIC_BETA_RELEASE.md`. Do not open the beta until the mandatory deployed real-video smoke test has passed.
