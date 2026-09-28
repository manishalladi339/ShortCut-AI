# Public Release Gate

ShortCut AI is eligible for a public beta only when every **Required** item below is complete on the release commit.

## Automated gates — Required

- [ ] backend-ci is green.
- [ ] frontend-ci is green.
- [ ] release-ci is green.
- [ ] e2e-ci is green.
- [ ] security-ci is green with no unresolved high/critical finding.
- [ ] Production image builds from the exact release commit.

## Production infrastructure — Required

- [ ] HTTPS API domain is live.
- [ ] HTTPS frontend domain is live.
- [ ] External MongoDB backups/snapshots are enabled and a restore has been tested.
- [ ] Private S3-compatible bucket is configured with encryption, blocked public access and lifecycle rules.
- [ ] Strong JWT secret is configured outside source control.
- [ ] OpenAI production key has a spend limit/alert.
- [ ] Resend sender is verified and password reset delivery is tested.
- [ ] Sentry DSN is configured and a test exception is visible in the project.
- [ ] CORS contains only real frontend origins.
- [ ] Google auth is either disabled or configured with ShortCut-owned Google client IDs.

## Abuse and cost controls — Required

- [ ] Upload size, per-user storage and media-duration limits are appropriate for the beta.
- [ ] Auth, upload, AI analysis, AI planning and render limits are configured.
- [ ] Maximum active renders per user is configured.
- [ ] Cloud billing alerts are enabled.
- [ ] An operator can disable signups or AI-heavy features during an incident.

## Real media validation — Required

Run at least:
- [ ] 20 representative real videos end-to-end.
- [ ] portrait + landscape source.
- [ ] single-speaker + multi-speaker.
- [ ] poor/noisy audio.
- [ ] multiple source assets and still images.
- [ ] near-maximum supported duration.
- [ ] interrupted worker/restart recovery.
- [ ] failed upstream AI request/retry.
- [ ] 1080p vertical render download.
- [ ] Export QA + repair + re-render.

Record render time, failure reason, OpenAI cost and peak CPU/RAM for every run.

## Privacy and user controls — Required

- [x] In-app authenticated account deletion path exists.
- [x] Account deletion removes user-scoped database records and object-storage media.
- [ ] Published Privacy Policy URL uses the final operator/legal identity and contact details.
- [ ] Published Terms URL uses the final operator/legal identity and governing-law decision.
- [ ] Support/contact path is visible in the product.
- [ ] Data retention and deletion policy matches actual infrastructure lifecycle rules.

## Launch sequence

1. Deploy the release commit to staging.
2. Complete the real-media validation set.
3. Run a small load test.
4. Deploy the same immutable image to production.
5. Invite 5–10 private testers.
6. Resolve launch-blocking defects.
7. Expand to a capped public beta.
8. Add paid plans only after metering, billing webhooks, refunds/support and cost margins are verified.
