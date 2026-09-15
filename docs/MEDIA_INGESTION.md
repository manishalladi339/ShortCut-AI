# Media ingestion

The ingestion pipeline separates **upload completion** from **media validation**.

## Flow

1. Client requests `POST /api/v1/assets/presign-upload`.
2. The API creates a pending asset record and returns an upload URL.
3. The client uploads directly to the configured storage backend.
4. The client calls `POST /api/v1/assets/{asset_id}/confirm`.
5. The API verifies object existence and size, marks the asset uploaded, and enqueues one `media_probe` job.
6. A worker atomically claims the job.
7. The worker materializes the object locally when necessary and invokes FFprobe.
8. Extracted metadata is persisted on the asset.
9. Job state is visible through `/api/v1/jobs`.

## Storage backends

`STORAGE_BACKEND=local` is intended for local development and CI.

`STORAGE_BACKEND=s3` uses boto3-compatible object storage and presigned upload/download URLs. It supports AWS S3 and S3-compatible endpoints through `S3_ENDPOINT_URL`.

Application code depends on the storage interface rather than a local-disk implementation.

## Job semantics

Jobs use these states:

`queued -> running -> succeeded`

A failed processing attempt returns to `queued` until `max_attempts` is reached. The terminal state is then `failed`.

Jobs are claimed with an atomic database operation to prevent two workers from processing the same queue entry concurrently.

## Security / trust boundary

Client-supplied duration, dimensions and codec information are not authoritative. Media metadata is derived server-side using FFprobe.

Local storage endpoints are enabled only when the local backend is selected. Production S3 deployments upload directly to object storage.

## Next ingestion work

- multipart uploads for very large assets
- checksum verification
- MIME/container allowlists
- proxy generation
- thumbnails
- audio waveforms
- cleanup for abandoned uploads
- dead-letter / operator retry controls
