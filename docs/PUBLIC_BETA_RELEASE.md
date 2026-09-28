# ShortCut AI Public Beta Release Gate

This file separates repository-complete work from tasks that require production accounts, credentials, legal identity or real users.

## Implemented in the repository

- [x] Production Docker image
- [x] API/media/intelligence/render worker topology
- [x] Caddy HTTPS edge
- [x] MongoDB and storage readiness checks
- [x] Private S3-compatible storage architecture
- [x] Upload-size enforcement
- [x] MIME-kind validation
- [x] Per-user storage cap
- [x] Media-duration cap
- [x] Authentication rate limiting
- [x] AI/render rate limiting
- [x] Daily free-beta AI/render limits
- [x] Concurrent render cap
- [x] Request IDs and security headers
- [x] Sentry integration and production requirement
- [x] Resend password-reset delivery
- [x] Legacy Emergent Google login blocked and removed from UI
- [x] Permanent account/data/media deletion
- [x] Explicit versioned Terms/Privacy acceptance
- [x] In-app Privacy and Terms pages
- [x] Backend integration tests
- [x] Frontend typecheck/lint
- [x] Production web build
- [x] Playwright browser smoke tests
- [x] Python dependency audit
- [x] JavaScript dependency audit
- [x] Secret scanning
- [x] Production compose validation
- [x] Caddy config validation
- [x] Deployment, retention, security and incident documentation

## External launch inputs still required

- [ ] Production domain
- [ ] DNS pointing API domain to deployment host
- [ ] AWS account/server
- [ ] private S3 bucket and browser CORS
- [ ] least-privilege AWS role/credentials
- [ ] MongoDB Atlas production connection
- [ ] production OpenAI API key with spend limits/alerts
- [ ] Resend verified sender/domain
- [ ] Sentry project/DSN
- [ ] final operator legal name
- [ ] privacy/support/security email addresses
- [ ] legal review/final governing-law and liability terms
- [ ] GitHub `main` branch protection/ruleset
- [ ] production backup/lifecycle policies
- [ ] real-video end-to-end validation
- [ ] controlled tester rollout

## Mandatory deployed smoke test

Before inviting public users:

1. `GET /api/v1/ready` returns 200.
2. Create a new account and confirm Terms/Privacy consent.
3. Create a project.
4. Upload a real video through the S3 presigned flow.
5. Wait for media processing.
6. Run Media Intelligence.
7. Generate an AI Director plan.
8. Review and apply the plan.
9. Make one Create With Me change.
10. Render a vertical 1080p export.
11. Verify audio mastering.
12. Verify Export QA.
13. Download/play the final MP4.
14. Delete the test account and confirm its media objects are gone.
15. Restart one worker during a test job and verify recovery.

## Public rollout

Start with a capped public beta. Keep paid plans disabled until usage, cost, support burden and render capacity are understood.
