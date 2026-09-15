# Media intelligence pipeline

This layer converts processed media into an auditable, time-aligned representation
that later AI planning can consume.

## Pipeline

```text
Processed asset
  -> mono 16 kHz speech audio
  -> timestamped transcription
  -> scene-change detection
  -> normalized word/segment timeline
  -> semantic units
  -> later: embeddings, retrieval, diarization, highlights and edit planning
```

## Current implementation

- authenticated analysis trigger per asset
- idempotent queued/running behavior
- background media-intelligence job
- FFmpeg audio extraction
- OpenAI-compatible transcription adapter
- word and segment timestamp normalization
- deterministic FFmpeg scene-change detection
- retrieval-ready semantic units that preserve original transcript wording
- persisted analysis document and job metrics

## Provider boundary

Transcription is behind a provider protocol. The current production adapter uses
an OpenAI-compatible audio transcription REST endpoint. API keys are supplied only
through environment variables and are never committed.

## Important limitations

Diarization is not yet implemented. The schema already carries optional
`speaker` fields so a diarization provider can enrich words/segments later.

Semantic units are deterministic transcript chunks, not LLM-written summaries.
This avoids injecting hallucinated meaning before the evaluation layer exists.

Embeddings, vector retrieval, highlight ranking and AI edit planning are the next
milestones.
