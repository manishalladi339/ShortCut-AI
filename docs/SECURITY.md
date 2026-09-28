# Security

ShortCut AI's public-beta baseline is designed around least privilege, isolated media storage, short-lived signed access, durable worker jobs and explicit production validation.

## Current controls

- HTTPS edge through Caddy with automatic certificate management
- API bound to loopback/internal Docker networking rather than directly exposed
- strong production JWT validation
- refresh-token rotation and revocation
- hashed passwords and password-reset tokens
- rate limiting for authentication, uploads, AI and renders
- daily AI/render caps for free-beta accounts
- concurrent-render caps
- file-size, media-duration and per-user storage limits
- exact CORS origin allowlist
- private S3-compatible storage with presigned URLs
- request IDs, structured logs and Sentry monitoring
- readiness checks for MongoDB and object storage
- worker leases/recovery for background jobs
- automated Python/JavaScript dependency audits
- automated secret scanning
- production web smoke tests
- account deletion for application data and stored media

## Production secrets

Never commit:

- `.env.production`
- JWT secrets
- OpenAI API keys
- Resend keys
- AWS static keys
- Sentry private credentials

Prefer AWS workload/instance roles to long-lived static credentials.

## Vulnerability reporting

Before public launch, replace this address with the real monitored inbox:

**[SECURITY CONTACT EMAIL]**

Include:

- affected endpoint/component;
- reproduction steps;
- impact;
- logs/request IDs when available;
- proof-of-concept that avoids accessing other users' data.

Do not publish exploitable details before the operator has had a reasonable opportunity to investigate and remediate.

## Branch protection

The repository should require pull requests and successful CI checks before merging to `main`. The connected GitHub integration used for this hardening work does not expose administrative branch-protection writes, so this remains an owner-side GitHub setting.
