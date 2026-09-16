# Deployment and operations

## Configuration

Use `.env.example` for Compose or `backend/.env.example` for independent services. Store real secrets in your hosting provider's secret manager; never commit `.env`.

For production:

- Set `APP_ENV=production`, a unique random `JWT_SECRET` of at least 32 characters, HTTPS `APP_PUBLIC_URL` and `FRONTEND_PUBLIC_URL`, and explicit `CORS_ORIGINS`.
- Terminate TLS in a reverse proxy/load balancer in front of the web container. Route `/api/` to the API. Keep MongoDB private.
- Use a durable shared volume for local storage, mounted into every worker and the API, or set `STORAGE_BACKEND=s3`. All replicas must see the same source/export objects.
- For S3, set bucket, region, and optional S3-compatible endpoint. Prefer cloud workload roles; the local Compose example does not inject AWS access keys. Bucket CORS must permit your frontend origin, PUT/GET/HEAD, `Content-Type`, and `If-None-Match`. Conditional PUT prevents replacing a confirmed object through a reused upload link.
- Configure `OPENAI_API_KEY`; defaults use OpenAI-compatible speech, vision, and embedding APIs. Provider costs are incurred by analysis and planning. Use provider budget limits and an authenticated reverse proxy with per-user/IP rate limits before public signup.
- Configure SMTP host, port, sender, and optional authentication. STARTTLS is on by default. Password reset is unavailable when no SMTP host is configured. SMTP delivery errors are logged generically to avoid exposing account existence; alert on those errors.

The development Compose file is a starting point, not a managed hosting deployment. Size workers for CPU-intensive FFmpeg processing, and benchmark representative uploads before choosing instance capacity. Billing is not active.

## Worker operation

Run these independently:

```sh
python -m workers.media_worker
python -m workers.intelligence_worker
python -m workers.render_worker
python -m workers.pipeline_worker
```

Jobs are claimed atomically. Progress updates renew a one-hour processing lease. Workers recover expired leases when claiming new work; retryable jobs are requeued, exhausted attempts fail visibly. Old workers cannot acknowledge jobs after losing their claim. A permanently interrupted automatic pipeline fails rather than blindly applying edits twice; already created plans/exports remain available for review.

Media/AI operations must finish each stage within the configured timeouts. No daemon in this repository provides a separately managed autoscaler, dead-letter dashboard, or alerting service. Monitor job age, failure rate, MongoDB health, storage capacity, and provider errors.

`/api/v1/health` is process liveness. `/api/v1/ready` checks MongoDB availability; it does not guarantee AI-provider credentials, SMTP delivery, or worker health.

## Operational acceptance before public launch

1. Use a real provider key to analyze a short spoken video, create a proposal, apply it, and verify captions/source ranges against the source.
2. Run Create For Me, close the client, return, and download the completed export. Test worker interruption and recovery with representative files.
3. Test sign-up/login, token rotation, password reset using a real inbox, uploads, seekable playback, editing, restore, and export on web and physical Android/iOS devices.
4. Configure HTTPS, ingress rate limits, provider spending limits, storage lifecycle rules, database backups, and a restore drill. Complete dependency/security review and load testing.
5. Establish account/content deletion and data-retention procedures. Project deletion removes project records and retains source uploads in the owner's library. Previously issued download links expire, while object-storage lifecycle policy handles orphaned derived/export binaries.

## Rollback

Deploy tagged images/commits. Keep MongoDB and object-storage backups independently of the containers. Roll back app images without deleting volumes. Review schema/index compatibility before reverting across releases. The release branch adds a partial unique index enforcing one active automatic pipeline per project.
