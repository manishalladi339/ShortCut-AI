# ShortCut AI — API Contracts (REST)

> Base path: `/api/v1`
> Auth: `Authorization: Bearer <jwt>` on every endpoint **except** `/auth/*` and `/health`.
> All requests/responses JSON. Errors: `{ "error": { "code": "...", "message": "..." } }`.

---

## Group 1 — Authentication `/auth`
| Method | Path | Body / Query | Response | Notes |
|---|---|---|---|---|
| POST | `/auth/signup` | `{email, password, name}` | `{user, access_token, refresh_token}` | Validates password ≥ 8 chars |
| POST | `/auth/login` | `{email, password}` | `{user, access_token, refresh_token}` | Rate-limited 5/min/IP |
| POST | `/auth/google` | `{auth_code}` | `{user, access_token, refresh_token}` | Emergent-managed |
| POST | `/auth/refresh` | `{refresh_token}` | `{access_token, refresh_token}` | Rotates refresh |
| POST | `/auth/logout` | `{refresh_token}` | `{ok: true}` | Revokes session |
| POST | `/auth/forgot-password` | `{email}` | `{ok: true}` | Always 200 (no enumeration) |
| POST | `/auth/reset-password` | `{token, new_password}` | `{ok: true}` | |
| GET | `/auth/me` | — | `{user}` | Validates JWT |

## Group 2 — Users `/users`
| Method | Path | Notes |
|---|---|---|
| GET | `/users/me` | Current profile |
| PATCH | `/users/me` | `{name?, avatar_b64?, niche?, user_type?, onboarding_complete?}` |
| POST | `/users/me/change-password` | `{old_password, new_password}` |
| DELETE | `/users/me` | Soft-delete + audit log |

## Group 3 — Projects `/projects`
| Method | Path | Notes |
|---|---|---|
| GET | `/projects?archived=false&limit=20&cursor=...` | Paginated list |
| POST | `/projects` | `{title, description?, content_type, creation_mode, desired_style?, target_platforms?, prompt?}` |
| GET | `/projects/{id}` | Full project with linked clip/thumb ids |
| PATCH | `/projects/{id}` | rename / update fields |
| POST | `/projects/{id}/duplicate` | Returns new project |
| POST | `/projects/{id}/archive` | sets archived=true |
| DELETE | `/projects/{id}` | hard delete (cascades clips/jobs) |
| GET | `/projects/recent` | Top 10 by updated_at |
| GET | `/projects/continue-editing` | status in (draft, processing) limit 5 |

## Group 4 — Assets `/assets`
| Method | Path | Notes |
|---|---|---|
| POST | `/assets/upload` | multipart/form-data: `file`, optional `project_id`, `tags[]`. Returns asset. |
| GET | `/assets?kind=video&project_id=&tag=&q=&limit=20&cursor=` | Search + filter |
| GET | `/assets/{id}` | Metadata only |
| GET | `/assets/{id}/data` | Streams binary (Range header supported) |
| PATCH | `/assets/{id}` | `{tags?, filename?}` |
| DELETE | `/assets/{id}` | |

## Group 5 — AI Processing `/ai`
| Method | Path | Notes |
|---|---|---|
| POST | `/ai/projects/{id}/run-pipeline` | `{prompt?, target_platforms[], style?}` → 202 `{job_id}` |
| GET | `/ai/jobs/{job_id}` | full job doc incl. step_results |
| GET | `/ai/jobs/{job_id}/status` | lightweight `{status, current_step, progress}` |
| POST | `/ai/jobs/{job_id}/cancel` | |
| POST | `/ai/jobs/{job_id}/retry` | restarts from failed step |
| POST | `/ai/commands` *(Create With Me)* | `{project_id, command: "remove pauses", params?}` → 202 `{job_id}` |
| POST | `/ai/suggestions/{project_id}` | Returns ranked AI suggestion list |
| POST | `/ai/sliders/{project_id}` | `{energy:50, cinematic:80, ...}` → updates editing intent |

## Group 6 — Clips `/clips`
| Method | Path | Notes |
|---|---|---|
| GET | `/clips?project_id=&min_score=&limit=20` | |
| GET | `/clips/{id}` | |
| POST | `/clips/{id}/render` | Triggers FFmpeg cut with chosen aspect_ratio |
| PATCH | `/clips/{id}` | trim adjustments (start_sec, end_sec) |
| DELETE | `/clips/{id}` | |

## Group 7 — Captions `/captions`
| Method | Path | Notes |
|---|---|---|
| GET | `/captions/{clip_id}` | |
| POST | `/captions/{clip_id}/regenerate` | `{platform?, style?}` |
| PATCH | `/captions/{id}` | manual edits |
| GET | `/captions/{id}/srt` | download SRT |

## Group 8 — Titles / Descriptions / Hashtags
| Method | Path | Notes |
|---|---|---|
| GET | `/titles?project_id=&clip_id=` | |
| POST | `/titles/regenerate` | `{project_id, clip_id?, platform, count=20}` |
| GET | `/descriptions?...` | |
| POST | `/descriptions/regenerate` | |
| GET | `/hashtags?...` | |
| POST | `/hashtags/regenerate` | |

## Group 9 — Thumbnails `/thumbnails`
| Method | Path | Notes |
|---|---|---|
| GET | `/thumbnails?project_id=&clip_id=` | |
| POST | `/thumbnails/generate` | `{project_id, clip_id?, concept?, text_overlay?, count=4}` → uses Nano Banana |
| DELETE | `/thumbnails/{id}` | |

## Group 10 — Content Hub `/content`
| Method | Path | Notes |
|---|---|---|
| GET | `/content/search?q=&type=clip|title|hashtag|thumb&platform=&sort=newest|score` | Unified search across hub |
| GET | `/content/recent` | mixed feed |

## Group 11 — Analytics `/analytics` *(post-MVP)*
| Method | Path | Notes |
|---|---|---|
| GET | `/analytics/overview?range=7d` | KPIs |
| GET | `/analytics/clips/{id}` | |
| POST | `/analytics/import` | Webhook from platform integrations |

## Group 12 — Calendar `/calendar` *(post-MVP)*
| Method | Path | Notes |
|---|---|---|
| GET | `/calendar?month=2026-05` | |
| POST | `/calendar` | schedule |
| PATCH | `/calendar/{id}` | reschedule |
| DELETE | `/calendar/{id}` | |
| GET | `/calendar/suggestions` | AI-generated content plan |

## Group 13 — Subscriptions `/subscriptions` *(post-MVP)*
| Method | Path | Notes |
|---|---|---|
| GET | `/subscriptions/me` | |
| POST | `/subscriptions/checkout` | `{tier}` → Stripe Checkout URL |
| POST | `/subscriptions/portal` | Stripe customer portal URL |
| POST | `/webhooks/stripe` | Stripe webhook receiver |

## Group 14 — Brand Kit `/brand` *(post-MVP)*
| Method | Path | Notes |
|---|---|---|
| GET | `/brand` | |
| PUT | `/brand` | upsert |

## Group 15 — System
| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `{ok:true}` |
| GET | `/api/docs` | OpenAPI Swagger UI |

---

## Standard Pydantic Response Shapes

```python
class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_b64: str | None = None
    role: Literal["user", "admin"]
    subscription_tier: Literal["free","creator","pro","agency"]
    onboarding_complete: bool
    created_at: datetime

class ProjectOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None = None
    content_type: ContentType
    creation_mode: Literal["create_for_me","create_with_me"]
    status: ProjectStatus
    desired_style: Style | None = None
    target_platforms: list[Platform] = []
    primary_asset_id: str | None = None
    output_clip_ids: list[str] = []
    output_thumbnail_ids: list[str] = []
    current_ai_job_id: str | None = None
    archived: bool
    created_at: datetime
    updated_at: datetime

class AIJobStatus(BaseModel):
    id: str
    project_id: str
    status: Literal["queued","running","completed","failed","cancelled"]
    current_step: str | None = None
    progress: int
    error: dict | None = None
```

## Pagination Convention
- All list endpoints support `limit` (default 20, max 100) and `cursor` (base64-encoded `{updated_at, id}`).
- Response: `{ items: [...], next_cursor: "...", has_more: bool }`.

## Error Codes
| Code | HTTP | Meaning |
|---|---|---|
| `auth.invalid_credentials` | 401 | |
| `auth.token_expired` | 401 | |
| `auth.forbidden` | 403 | |
| `validation.failed` | 422 | |
| `quota.exceeded` | 402 | Project limit reached on free tier |
| `ai.job_failed` | 500 | |
| `resource.not_found` | 404 | |
| `rate_limit.exceeded` | 429 | |
