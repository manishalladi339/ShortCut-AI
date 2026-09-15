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
  -> embeddings
  -> project-scoped semantic retrieval
  -> later: diarization, highlights, narrative analysis and edit planning
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
- OpenAI-compatible embedding provider
- batched semantic-unit embeddings
- project-scoped cosine-similarity retrieval
- persisted analysis document and job metrics

The default embedding model is `text-embedding-3-small`, configurable through
`EMBEDDING_MODEL`. Embedding vectors are stored separately from the public
semantic-unit payload so normal API responses do not return large raw vectors.

## Retrieval

`POST /api/v1/projects/{project_id}/intelligence/search`

The query is embedded with the same model used for analyzed units. Results return:
- source asset
- intelligence record
- unit index
- time range
- transcript text
- cosine-similarity score

This gives the later AI planner a grounded way to locate moments such as
"the part where the guest explains the pricing problem" across project media.

## Provider boundary

Transcription and embeddings are behind provider interfaces. Current production
adapters use OpenAI-compatible REST endpoints. API keys are supplied only through
environment variables and are never committed.

OpenAI's embeddings API supports arrays of input strings, so semantic units are
embedded in batches rather than one request per unit.

## Important limitations

Speaker diarization is not yet implemented. The schema already carries optional
`speaker` fields so a diarization stage can enrich words and segments without
breaking the data model.

Semantic units remain deterministic transcript chunks, not LLM-written summaries.
Retrieval therefore grounds later reasoning in the original transcript rather than
a model-generated rewrite.

Highlight ranking, narrative/audience analysis and the structured AI edit planner
are the next milestones.
