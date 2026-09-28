# Public Beta Incident Response

## Severity

- **SEV-1:** credential exposure, cross-account data access, destructive security incident, widespread outage.
- **SEV-2:** repeated render/AI failures, material data-processing errors, significant degradation.
- **SEV-3:** isolated bugs with workarounds.

## Immediate response

1. Confirm impact and capture request/job IDs.
2. Stop the affected surface if continued operation risks data or cost.
3. Rotate exposed credentials immediately.
4. Preserve relevant logs before retention windows expire.
5. Identify affected users/data/time window.
6. Patch and validate in CI.
7. Deploy the smallest safe remediation.
8. Notify affected users/providers when legally or operationally required.
9. Document root cause and prevention actions.

## Operational signals

Watch:

- API 5xx rate;
- Sentry error volume;
- MongoDB readiness;
- S3 readiness;
- worker queue depth;
- job failure/retry rate;
- FFmpeg render time;
- AI-provider errors/latency;
- OpenAI spend;
- disk/RAM/CPU usage;
- unusual authentication/rate-limit activity.

## Credential response

If a production key is exposed:

- revoke/rotate it at the provider;
- update deployment secrets;
- restart affected services;
- inspect audit/provider logs;
- invalidate user sessions when JWT/session confidentiality may be affected.

Never attempt to "fix" an exposed credential only by deleting it from the latest Git commit; assume repository history or logs may retain it.
