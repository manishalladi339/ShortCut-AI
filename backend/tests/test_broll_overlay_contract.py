"""Contract tests for executable AI B-roll overlays."""
from models.project_state import Clip, ProjectStateDocument, Sequence, Timebase, Track


def test_overlay_track_accepts_muted_broll_clip():
    overlay = Track(id="broll", kind="overlay", name="AI B-roll", clips=[Clip(id="b1", asset_id="asset-b", timeline_start=1000, duration=3000, source_start=5000, source_duration=3000, volume=0.0, metadata={"broll": True, "replaces_primary_visual": True})])
    sequence = Sequence(id="seq", name="Reel", timebase=Timebase(), tracks=[Track(id="main", kind="video", name="Primary"), overlay])
    state = ProjectStateDocument(project_id="p", user_id="u", version=2, active_sequence_id="seq", sequences=[sequence], created_at="2026-01-01", updated_at="2026-01-01")
    clip = state.sequences[0].tracks[1].clips[0]
    assert clip.volume == 0.0
    assert clip.metadata["broll"] is True
    assert clip.metadata["replaces_primary_visual"] is True


def test_overlay_track_is_distinct_from_primary_video_track():
    sequence = Sequence(id="seq", name="Reel", tracks=[Track(id="main", kind="video", name="Primary"), Track(id="broll", kind="overlay", name="AI B-roll")])
    assert sequence.tracks[0].kind.value == "video"
    assert sequence.tracks[1].kind.value == "overlay"
