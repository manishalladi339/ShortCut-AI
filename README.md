# ShortCut AI

AI-assisted video editing with an Expo app, FastAPI API, MongoDB job queue, and deterministic FFmpeg exports.

**Release candidate:** the account → upload → edit → render workflow is implemented and integration-tested. Live AI-provider validation, production deployment, and native-device acceptance are still release gates. This repository does not claim a deployed production service.

## What works

- Email/password accounts, rotating refresh tokens, SMTP password reset.
- Signed uploads and downloads; streaming local uploads and seekable video playback.
- Background metadata extraction, proxy/thumbnail generation, transcription, visual analysis, and semantic indexing.
- **Create For Me:** server-owned analysis → proposal → versioned edit → export. Processing survives closing the client.
- **Create With Me:** reviewed AI proposals, manual clip placement/trimming/splitting, volume, captions, and version restore.
- Deterministic MP4 rendering with overlays, fades, captions, audio mixing, music ducking, and free-tier watermark.
- Export history and Content Hub, with original media preserved during editing.

## Run the full stack

Requires Docker with Compose.

```sh
cp .env.example .env
# Set a random JWT_SECRET. Add your AI key and SMTP settings as needed.
docker compose up --build
```

Open `http://localhost:8080`. API docs are at `http://localhost:8001/docs` on the host.

The stack includes MongoDB, the API, web frontend, and separate ingestion, intelligence, rendering, and automatic-pipeline workers. Manual editing/export does not require an AI key. AI actions require a configured provider; password-reset delivery requires SMTP.

For an Expo native development build, run `npm ci` in `frontend`, copy its `.env.example` to `.env`, set the API URL to an address reachable from the device, then run `npm start`. Use the same reachable origin for backend `APP_PUBLIC_URL` so media links work on the device.

## Scope and limits

The current automatic workflow produces one short-form export per request. Export limits are 5 minutes, 100 clips, and up to 4K pixels with even dimensions. Default upload limit is 512 MiB. Automatic selection is primarily grounded in spoken-video transcripts; silent-media montage generation and bulk “20 reels from a podcast” remain future work. Manual editing accepts images, video, and audio.

Long PCM audio is sent for transcription in ten-minute chunks. Timestamps remain absolute; diarization speaker labels are scoped to each chunk rather than claiming cross-chunk identity matching.

Paid subscriptions and social-network publishing are not enabled. Google sign-in is a legacy optional integration and is hidden by default.

## Tests and deployment

See [deployment](docs/DEPLOYMENT.md), [release assessment](docs/RELEASE_READINESS.md), and [architecture](docs/ARCHITECTURE.md).

Backend tests use a real disposable MongoDB and a running API. Some tests invoke workers directly, so the test process and API **must use the same database and storage path**. Never run these tests against production.

```sh
python -m pip install -r backend/requirements.txt
# Set MONGO_URL, DB_NAME, JWT_SECRET, STUB_STORAGE_DIR, APP_PUBLIC_URL,
# EXPO_PUBLIC_BACKEND_URL and PYTHONPATH=backend, then start the API.
python -m pytest -q backend/tests --tb=short
cd frontend
npm ci
npx tsc --noEmit
npx eslint app src --quiet
npx expo export --platform web
```

CI runs database/API/FFmpeg integration tests and a separate frontend type/lint/export check. AI orchestration tests use controlled responses; they do not establish live provider quality or availability.
