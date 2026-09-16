# Timeline Review

The timeline review screen turns canonical ProjectState into a visual, source-aware
editing surface.

## What it shows

- current ProjectState version and active sequence;
- latest completed render, with an inline video player;
- whether the preview matches the current timeline version;
- Export QA status for the preview;
- fixed track labels for video, overlays, audio and captions;
- zoomable time ruler;
- every clip/caption positioned from canonical timeline ticks.

## Selection inspector

Selecting a timeline block shows:

- exact timeline range;
- source range for media clips;
- duration and playback rate;
- source asset filename;
- AI provenance such as speaker, narrative role, B-roll, semantic replacement,
  pacing retime, AI plan and QA-repair metadata.

## Exact-range Create With Me actions

Timeline actions open Create With Me with explicit start/end seconds already
filled in. Examples:

- primary video -> tighten pacing;
- diarized primary video -> remove the selected speaker;
- overlay -> replace/remove B-roll;
- music -> lower/remove music;
- caption -> restyle/remove caption.

The timeline itself does not mutate ProjectState. Every change still goes through
the constrained proposal/review/version-safe apply flow.

## Preview rendering

The screen can request a render for the current active sequence and polls the
export record until completion/failure. A preview from an older ProjectState
version is visibly marked stale so creators do not judge an outdated render as the
current edit.
