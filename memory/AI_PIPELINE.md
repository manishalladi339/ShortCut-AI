# ShortCut AI — AI Workflow Definitions

> **Providers:** Gemini 3 Pro (text reasoning), Gemini Nano Banana (thumbnails), OpenAI Whisper-1 (transcription). All routed via `emergentintegrations` using the Emergent LLM Key.

---

## Pipeline Overview — "Create For Me"

```
upload(s) ──► [1] Transcription ──► [2] Content Analysis ──► [3] Clip Detection
                                                                    │
                                                                    ▼
[10] Strategy ◄── [9] Thumbnail ◄── [8] Hashtag ◄── [7] Description ◄── [6] Title ◄── [5] Caption ◄── [4] Editing Planner
        │
        ▼
   ai_jobs.status = completed
```

Each agent:
- Reads from `ai_jobs.step_results` (previous outputs).
- Writes its own output back into `step_results.<agent_name>`.
- Updates `progress` by +10 on success.
- On failure, the orchestrator retries up to 3× with exponential backoff (1s, 4s, 16s). If still failing, `status=failed` and `error.step` is recorded.

---

## Agent 1 — Transcription
**Model:** OpenAI Whisper-1 (via Emergent LLM key)
**Inputs:** `asset.data_b64` (audio extracted via FFmpeg if video) or audio asset.
**FFmpeg pre-step:** `ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 audio.wav`
**Prompt / params:** `response_format=verbose_json`, `timestamp_granularities=["word","segment"]`
**Output schema:**
```json
{
  "language": "en",
  "full_text": "...",
  "segments": [
    {"start": 0.0, "end": 4.2, "text": "...", "speaker": "S1", "confidence": 0.94}
  ],
  "speaker_count": 2
}
```
Persisted to `transcripts` collection. `ai_jobs.step_results.transcription = transcript_id`.

---

## Agent 2 — Content Analysis
**Model:** Gemini 3 Pro
**Input:** transcript.full_text + transcript.segments + project.content_type + project.desired_style
**System prompt (essence):**
> You are a viral content analyst. Identify hooks (first 3s grab), stories (narrative arcs), emotional moments, educational moments, controversial takes, and viral segments. Return a ranked JSON list. Score each on hook_strength, emotional_density, retention_prediction (0–100).
**Output schema:**
```json
{
  "moments": [
    {"start": 12.3, "end": 38.0, "category": "hook|story|emotional|educational|controversial|viral",
     "summary": "...", "hook_strength": 87, "emotional_density": 72, "retention_prediction": 81,
     "transcript_excerpt": "..."}
  ]
}
```

---

## Agent 3 — Clip Detection
**Model:** Gemini 3 Pro
**Input:** `analysis.moments` + transcript segments
**Task:** Generate clips of 15s, 30s, and 60s flavors. Snap boundaries to natural sentence ends (use segment timestamps).
**Output schema:**
```json
{
  "clips": [
    {"start_sec": 12.5, "end_sec": 27.5, "duration_sec": 15, "category": "hook",
     "clip_score": 88, "viral_score": 91, "hook": "Wait until you see this…",
     "transcript_excerpt": "...", "reasoning": "strong hook + emotional payoff"}
  ]
}
```
Each clip becomes a `clips` doc with `status=pending`. FFmpeg render kicked off only when user opens the clip.

**Viral Score formula (Smart Business Enhancement):**
`viral_score = 0.4*hook_strength + 0.3*retention_prediction + 0.2*emotional_density + 0.1*platform_fit`

---

## Agent 4 — Editing Planner
**Model:** Gemini 3 Pro
**Input:** clip metadata + desired_style + target_platforms
**Task:** Output editing blueprint per clip (kept jargon-free for "Create With Me" mapping later).
**Output schema (per clip):**
```json
{
  "clip_id": "...",
  "cut_strategy": "fast_punchy | slow_buildup | rhythmic",
  "caption_strategy": {"style":"karaoke","color":"#FFD700","position":"center"},
  "music_style": "lofi|cinematic|hype|emotional|none",
  "thumbnail_concept": "Bold face crop + neon text 'YOU WON'T BELIEVE'",
  "transition_recommendations": ["hard_cut", "zoom_in", "whip_pan"],
  "aspect_ratio_per_platform": {"ig_reels":"9:16","yt_shorts":"9:16","linkedin":"1:1"}
}
```

---

## Agent 5 — Caption Agent
**Model:** Gemini 3 Pro
**Input:** clip transcript segments + style from Editing Planner
**Task:** Produce SRT + VTT with karaoke-style word highlighting; bold "power keywords"; tune line length per platform (Reels ≤ 30 chars/line; LinkedIn ≤ 60).
**Output:** persists to `captions` collection per clip.

---

## Agent 6 — Title Agent
**Model:** Gemini 3 Pro
**Task:** Minimum **20 title variations per clip**, split across 3 archetypes:
- Hook titles (curiosity gap)
- YouTube SEO titles (with keywords)
- Reel titles (short, ≤ 40 chars)
**Output:**
```json
{"variations":[
  {"text":"I tried this for 30 days…","archetype":"hook","platform":"yt_shorts","score":92},
  ... 19 more ...
]}
```

---

## Agent 7 — Description Agent
**Model:** Gemini 3 Pro
**Task:** Platform-specific descriptions:
- Instagram: 2200 char cap, emoji-rich, 3-line hook + CTA.
- YouTube: SEO description with timestamps if clip > 30s.
- X (Twitter): 280 char, hook + link placeholder.
- LinkedIn: long-form professional tone.
- Facebook: shareable, casual.
**Output:** `{platform_copies: {...}}`.

---

## Agent 8 — Hashtag Agent
**Model:** Gemini 3 Pro
**Task:** Generate trending + niche + platform-specific tags. Volumes:
- IG: 15–30 tags (mix of broad, mid, niche)
- YT: 5–10
- X: 2–4
**Output:** structured per platform; flagged with relevance scores.

---

## Agent 9 — Thumbnail Agent
**Models:** Gemini 3 Pro (concept text) → Gemini Nano Banana (image generation, **gemini-2.5-flash-image**)
**Flow:**
1. Gemini 3 Pro proposes 4 thumbnail concepts (description + text overlay) using `editing_planner.thumbnail_concept` as seed.
2. For each concept, call Nano Banana with prompt:
   `"Photo-real YouTube thumbnail, 9:16 ratio, bold sans-serif text '<text>', dramatic lighting, viral aesthetic. Concept: <concept>."`
3. Store base64 PNGs into `thumbnails`.
**Output:** 4 thumbnail docs per clip.

---

## Agent 10 — Strategy Agent
**Model:** Gemini 3 Pro
**Task:** Posting schedule + content calendar + repurposing plan.
**Output schema:**
```json
{
  "posting_schedule": [
    {"clip_id":"...", "platform":"ig_reels", "post_at":"2026-05-12T18:30:00Z", "reason":"peak audience window"}
  ],
  "calendar_30d": [...],
  "repurposing": [
    {"clip_id":"...", "secondary_uses":["LinkedIn carousel from quote at 0:08","X thread from key points"]}
  ]
}
```

---

## "Create With Me" Mode

### Slider → AI Action Mapping
| Slider | 0 baseline | 100 maxed (action) |
|---|---|---|
| Energy | normal pacing | aggressive cuts every 1.2s, beat-sync |
| Cinematic | flat | letterbox bars + color grade + slow-mo accents |
| Storytelling | raw clip | chapter intro + outro CTA + narrative reorder |
| Humor | none | meme-style captions + reaction zooms |
| Professional | casual | corporate caption style, muted palette, lower-thirds |
| Emotional | none | piano underscore + slow zoom + tear-jerker pacing |
| Pacing | original | silence-removed + 1.15x speed |
| Audio Quality | as-is | denoise + normalize + de-esser |
| Visual Impact | none | sharpen + saturation + vignette |
| Engagement | none | hook-first reorder + caption hooks at 0s |

Slider values POSTed to `/ai/sliders/{project_id}`; orchestrator translates them into a re-runnable editing plan.

### AI Commands (Natural Language)
Backend parser (Gemini 3 Pro) classifies user text into one of:
- `remove_silence`, `improve_audio`, `add_captions`, `make_cinematic`, `make_emotional`,
  `create_reel`, `generate_thumbnail`, `create_youtube_short`, `custom`.

The matching micro-pipeline runs (subset of the 10 agents).

### AI Suggestions Engine
Cron-like trigger on project open. Recommends top 3 actions based on:
- if `silence_ratio > 0.15` → suggest "Remove silence"
- if no captions → "Add captions"
- if `clip_score < 70` on best clip → "Improve hook"
- if no thumbnails → "Generate thumbnail"
- if pacing avg shot > 5s → "Improve pacing"

---

## Reliability & Cost Controls

- **Token budget per job:** 80k tokens cap (Gemini 3 Pro). Truncate transcript to most relevant 30 minutes if longer (chunked content analysis).
- **Caching:** identical transcript hash + agent → cached output for 24h.
- **Idempotency:** all `/regenerate` endpoints use a server-issued idempotency key.
- **Observability:** every agent run logs `{job_id, agent, latency_ms, input_tokens, output_tokens, cost_est}` into `audit_logs`.

## Failure Modes
| Failure | Detection | Action |
|---|---|---|
| LLM timeout | 30s no response | Retry w/ shorter context |
| Invalid JSON | json.loads error | Retry w/ "respond strict JSON" reinforcement |
| Quota exhausted | 429 from provider | Mark job failed, surface to user |
| FFmpeg crash | non-zero exit | Mark step failed, no retry (deterministic) |
