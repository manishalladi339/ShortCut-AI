# ShortCut AI — MongoDB Database Schema

> All collections use `id: UUID v4` as the primary key (string field, NOT Mongo's `_id`).
> Every doc has: `id`, `created_at` (ISO-8601 UTC), `updated_at` (ISO-8601 UTC).
> All `_id` fields are excluded from API responses (projections strip them).

---

## 1. `users`
| Field | Type | Notes |
|---|---|---|
| `id` | str (uuid) | PK |
| `email` | str | unique index |
| `password_hash` | str | bcrypt; null if Google-only |
| `auth_provider` | enum | `email` \| `google` \| `both` |
| `google_id` | str? | unique sparse index |
| `name` | str | display name |
| `avatar_b64` | str? | base64 image |
| `role` | enum | `user` \| `admin` |
| `subscription_tier` | enum | `free` \| `creator` \| `pro` \| `agency` |
| `subscription_status` | enum | `active` \| `cancelled` \| `past_due` |
| `monthly_project_count` | int | reset on 1st of month |
| `monthly_project_limit` | int | 3 / 50 / -1 / -1 |
| `onboarding_complete` | bool | |
| `user_type` | str? | "Creator" / "Podcaster" / etc. |
| `niche` | str[]? | content categories of interest |
| `created_at`, `updated_at` | iso | |

Indexes: `email` (unique), `google_id` (unique sparse), `subscription_tier`.

## 2. `sessions`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid → users.id | |
| `refresh_token_hash` | str | sha256 |
| `device_info` | str? | |
| `expires_at` | iso | |
| `revoked` | bool | |
| `created_at` | iso | |

Indexes: `user_id`, `refresh_token_hash`, TTL on `expires_at`.

## 3. `projects`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid → users.id | |
| `title` | str | |
| `description` | str? | |
| `content_type` | enum | podcast/educational/business/travel/fitness/comedy/dance/vlog/gaming/food/fashion/real_estate/events/product_ad/personal_brand |
| `creation_mode` | enum | `create_for_me` \| `create_with_me` |
| `status` | enum | `draft` \| `processing` \| `completed` \| `archived` \| `failed` |
| `desired_style` | enum? | cinematic/professional/emotional/funny/energetic/inspirational/luxury |
| `target_platforms` | str[] | ig_reels / yt_shorts / fb_reels / linkedin / x |
| `prompt` | str? | user's natural-language brief |
| `primary_asset_id` | uuid? → assets.id | main video/audio |
| `output_clip_ids` | uuid[] | |
| `output_thumbnail_ids` | uuid[] | |
| `current_ai_job_id` | uuid? → ai_jobs.id | |
| `archived` | bool | default false |
| `created_at`, `updated_at` | iso | |

Indexes: `user_id`, `(user_id, archived, updated_at desc)`, `status`.

## 4. `assets`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `project_id` | uuid? | optional link |
| `filename` | str | |
| `mime_type` | str | video/mp4, audio/mp3, image/png… |
| `kind` | enum | `video` \| `audio` \| `image` |
| `size_bytes` | int | |
| `duration_sec` | float? | video/audio |
| `width`, `height` | int? | video/image |
| `storage_type` | enum | `inline_b64` \| `gridfs` \| `s3` |
| `data_b64` | str? | when inline |
| `gridfs_id` | str? | when chunked |
| `s3_url` | str? | when S3 |
| `tags` | str[] | |
| `created_at`, `updated_at` | iso | |

Indexes: `user_id`, `project_id`, `(user_id, kind)`, `tags`.

## 5. `transcripts`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `asset_id` | uuid → assets.id | |
| `project_id` | uuid | |
| `language` | str | ISO 639 |
| `segments` | object[] | `{start, end, text, speaker?, confidence}` |
| `full_text` | str | concatenated |
| `speaker_count` | int | |
| `created_at` | iso | |

## 6. `clips`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `project_id` | uuid | |
| `source_asset_id` | uuid → assets.id | |
| `output_asset_id` | uuid? → assets.id | rendered file |
| `start_sec`, `end_sec` | float | |
| `duration_sec` | float | 15/30/60 |
| `clip_score` | int | 0–100 |
| `viral_score` | int | 0–100 |
| `hook` | str? | extracted hook line |
| `category` | enum | hook/story/emotional/educational/controversial/viral |
| `aspect_ratio` | enum | 9:16 / 1:1 / 16:9 |
| `caption_id` | uuid? → captions.id | |
| `title_id` | uuid? → titles.id | |
| `thumbnail_id` | uuid? → thumbnails.id | |
| `status` | enum | `pending` \| `rendering` \| `ready` \| `failed` |
| `created_at`, `updated_at` | iso | |

Indexes: `project_id`, `(project_id, clip_score desc)`.

## 7. `captions`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid | |
| `srt` | str | SRT body |
| `vtt` | str | WebVTT body |
| `highlighted_keywords` | str[] | |
| `style` | object | `{font, color, position, animation}` |
| `platform` | str | reels/shorts/tiktok |
| `created_at` | iso | |

## 8. `titles`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid? | optional (project-level titles allowed) |
| `project_id` | uuid | |
| `variations` | object[] | `[{text, style, platform, score}]` (min 20) |
| `selected_index` | int? | user's choice |
| `created_at` | iso | |

## 9. `descriptions`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid? | |
| `project_id` | uuid | |
| `platform_copies` | object | `{ig: str, yt: str, x: str, linkedin: str, fb: str}` |
| `created_at` | iso | |

## 10. `hashtags`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid? | |
| `project_id` | uuid | |
| `trending` | str[] | |
| `niche` | str[] | |
| `platform` | object | `{ig: str[], yt: str[], x: str[]}` |
| `created_at` | iso | |

## 11. `thumbnails`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid? | |
| `project_id` | uuid | |
| `concept` | str | textual concept |
| `text_overlay` | str | |
| `image_b64` | str | base64 PNG |
| `model` | str | `gemini-nano-banana` |
| `created_at` | iso | |

## 12. `ai_jobs`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `project_id` | uuid | |
| `mode` | enum | `create_for_me` \| `create_with_me` |
| `status` | enum | `queued` \| `running` \| `completed` \| `failed` \| `cancelled` |
| `current_step` | str | one of the 10 agent names |
| `progress` | int | 0–100 |
| `step_results` | object | `{transcription:..., analysis:..., ...}` |
| `error` | object? | `{step, message, attempt}` |
| `retry_count` | int | |
| `started_at` | iso? | |
| `completed_at` | iso? | |
| `created_at`, `updated_at` | iso | |

Indexes: `user_id`, `status`, `(status, created_at)`.

## 13. `content_calendar` *(post-MVP)*
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `clip_id` | uuid? | |
| `title` | str | |
| `platform` | str | |
| `scheduled_at` | iso | |
| `status` | enum | `draft` \| `scheduled` \| `posted` \| `failed` |
| `ai_suggested` | bool | |
| `created_at`, `updated_at` | iso | |

## 14. `analytics` *(post-MVP)*
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `clip_id` | uuid | |
| `user_id` | uuid | |
| `platform` | str | |
| `views`, `reach`, `engagement`, `watch_time_sec`, `shares`, `saves` | int | |
| `recorded_at` | iso | |

## 15. `subscriptions` *(post-MVP)*
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `tier` | enum | free/creator/pro/agency |
| `stripe_customer_id` | str | |
| `stripe_subscription_id` | str | |
| `status` | str | |
| `current_period_end` | iso | |
| `created_at`, `updated_at` | iso | |

## 16. `brand_kits` *(post-MVP)*
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `logo_b64` | str? | |
| `colors` | str[] | hex |
| `fonts` | str[] | |
| `brand_voice` | str | tone description |
| `created_at`, `updated_at` | iso | |

## 17. `audit_logs`
| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid? | |
| `action` | str | `auth.login`, `project.delete`, … |
| `target_id` | uuid? | |
| `metadata` | object | |
| `ip` | str? | |
| `created_at` | iso | |

Indexes: `user_id`, `action`, `created_at desc`.

---

## Reference: Pydantic response strategy
Every read endpoint returns a Pydantic model. Mongo queries always use `{"_id": 0}` projection so ObjectId never reaches JSON. Datetimes serialized as ISO-8601 with `Z`.
