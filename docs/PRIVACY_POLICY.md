# ShortCut AI Privacy Policy — Public Beta Draft

**Effective date:** 28 September 2026  
**Status:** Release-ready product policy template. Before public launch, replace the operator and contact placeholders below with the final legal/operator details and obtain legal review appropriate to the launch jurisdictions.

## 1. Who operates ShortCut AI

ShortCut AI ("ShortCut", "we", "us") is operated by **[OPERATOR LEGAL NAME]**.  
Privacy contact: **[PRIVACY CONTACT EMAIL]**.

## 2. What we collect

We collect information needed to provide and secure ShortCut AI:

- account information such as name, email address, authentication data and account preferences;
- project metadata, timelines, AI plans, edit history and creator preferences;
- video, audio and image files you upload;
- derivatives and exports generated from your media;
- usage, job, reliability and security/audit events;
- device/browser and request information that may be present in ordinary service logs.

Passwords are stored as cryptographic hashes. Password-reset tokens are stored as hashes in production.

## 3. How we use information

We use data to:

- authenticate accounts;
- store and organize projects;
- analyze media;
- generate AI-assisted editing suggestions;
- render and deliver exports;
- provide account-security emails;
- enforce service quotas and prevent abuse;
- diagnose errors and maintain reliability;
- respond to support, security and legal obligations.

We do not need ownership of your uploaded content to provide the service.

## 4. AI processing

Depending on configured features, portions of your content may be sent to configured AI providers.

This can include:

- audio for transcription;
- representative image/video frames for visual analysis;
- transcript or project text for semantic processing;
- text used to generate embeddings.

ShortCut should be configured to send only the material needed for the requested feature. Provider processing is also subject to the provider agreements configured by the ShortCut operator.

## 5. Service providers

The public-beta deployment may use providers for:

- cloud compute and object storage;
- MongoDB hosting;
- OpenAI-compatible AI services;
- Resend transactional account-security email;
- Sentry error and performance monitoring;
- frontend hosting and DNS/CDN services.

These providers process data for the services we configure them to provide.

## 6. Storage and security

Production media is stored in private object storage and accessed through time-limited signed URLs. Production traffic is served over HTTPS.

ShortCut implements controls including:

- authenticated APIs;
- access/refresh token sessions;
- strong production secrets;
- rate limiting;
- upload and cost quotas;
- private object storage;
- security headers;
- request IDs and error monitoring;
- automated dependency and secret scanning.

No internet service can guarantee absolute security.

## 7. Retention

Active account data is retained while needed to provide the service.

Expired sessions and password-reset records are automatically aged out by database expiry indexes.

Users can delete individual assets or permanently delete their account. Account deletion removes owned application records and stored media/exports after active background jobs have finished.

Infrastructure backups, provider security logs, billing records or records required by law may remain for a limited period according to the applicable provider/operator retention policy.

## 8. Your content and rights

You should only upload content you have the right to process.

You may:

- access your account information in the product;
- remove individual media assets;
- remove projects;
- permanently delete your account from Profile;
- contact us using the privacy address above for additional privacy requests.

## 9. Children

ShortCut AI public beta is not intended for children below the minimum age permitted for the service in the applicable jurisdiction. The final launch policy should specify the supported age threshold.

## 10. International processing

Cloud and AI providers may process information in countries different from the user's country. Before public launch, the operator should confirm the regions and contractual safeguards used by production providers.

## 11. Changes

We may update this policy as the product changes. Material updates should be accompanied by a new policy/terms version and, where appropriate, renewed notice or consent.

## Launch fields that must be finalized externally

- [ ] Operator legal name
- [ ] Privacy/support email
- [ ] Minimum user age
- [ ] Production provider regions
- [ ] Jurisdiction-specific disclosures
- [ ] Legal review
