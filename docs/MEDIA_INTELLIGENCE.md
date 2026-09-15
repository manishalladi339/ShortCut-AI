# Media intelligence pipeline

This layer converts processed media into an auditable, time-aligned multimodal
representation for retrieval and AI edit planning.

## Pipeline

```text
Processed asset
  -> mono 16 kHz speech audio
  -> diarized transcription
  -> speaker-labelled segments
  -> scene-change detection
  -> representative scene frames
  -> visual observations
  -> speaker-aware semantic units
  -> embeddings
  -> project-scoped semantic retrieval
  -> planner
```

## Speech intelligence

The OpenAI-compatible transcription adapter supports normal timestamped
transcription and diarized transcription.

The default configuration now uses `gpt-4o-transcribe-diarize` with
`diarized_json`. Speaker annotations are preserved on transcript segments and
speaker labels are exposed on the media-intelligence record.

When diarization is enabled, semantic units can split at speaker changes so a
single retrieval unit does not accidentally merge two different speakers into
one statement.

For providers/models without diarization, the same schemas remain valid with
empty speaker fields.

## Visual intelligence

Video analysis uses deterministic scene detection first. The system then samples
representative frames from scene midpoints, with a configured maximum frame
budget.

`VISION_PROVIDER=openai` sends only those representative frames to the visual
provider rather than blindly sampling every second of a video.

Each returned observation can contain:
- timestamp
- visual description
- shot type
- visible-object labels
- visible people count
- on-screen text
- editing notes
- provider/model provenance

The provider is explicitly instructed not to infer the identity of people in a
frame.

`VISION_PROVIDER=disabled` preserves deterministic frame timestamps while
skipping model analysis.

## Semantic retrieval

Transcript semantic units remain grounded in original transcript wording. They
are embedded in batches and searched project-wide using cosine similarity.

Retrieval results contain:
- asset ID
- intelligence record ID
- semantic-unit index
- source time range
- original transcript text
- similarity score

## Grounding principle

Multimodal observations are additional planning signals; they do not replace
source timestamps or transcript grounding.

The planner should always be able to explain:
1. which source asset a proposed edit came from,
2. which time range was selected,
3. which transcript/visual evidence informed it,
4. which model/provider produced non-deterministic annotations.

## Current limitations

Still to build:
- known-speaker enrollment/reference samples
- cross-asset speaker identity continuity
- visual-observation embeddings
- visual-semantic retrieval
- subject tracking across shots
- face-safe active-speaker association
- B-roll recommendation and placement
- music/beat/silence intelligence
- creator preference memory
