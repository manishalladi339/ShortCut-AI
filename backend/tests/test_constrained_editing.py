"""Tests for localized Create-With-Me planning and safe mutation."""
from services.constrained_editing import (
    apply_constrained_operations,
    build_constrained_proposal,
)


def _state():
    return {
        "project_id": "project-1",
        "user_id": "user-1",
        "version": 4,
        "active_sequence_id": "seq",
        "created_at": "2026-09-16T00:00:00+00:00",
        "updated_at": "2026-09-16T00:00:00+00:00",
        "sequences": [
            {
                "id": "seq",
                "name": "Main",
                "width": 1080,
                "height": 1920,
                "timebase": {"numerator": 1000, "denominator": 1},
                "tracks": [
                    {
                        "id": "video",
                        "kind": "video",
                        "name": "Video",
                        "locked": False,
                        "muted": False,
                        "clips": [
                            {
                                "id": "primary",
                                "asset_id": "a",
                                "timeline_start": 0,
                                "duration": 20000,
                                "source_start": 0,
                                "source_duration": 20000,
                                "metadata": {"ai_plan_id": "plan"},
                            }
                        ],
                    },
                    {
                        "id": "overlay",
                        "kind": "overlay",
                        "name": "Overlay",
                        "locked": False,
                        "muted": False,
                        "clips": [
                            {
                                "id": "broll-1",
                                "asset_id": "b",
                                "timeline_start": 2000,
                                "duration": 3000,
                                "source_start": 0,
                                "source_duration": 3000,
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            },
                            {
                                "id": "broll-2",
                                "asset_id": "b",
                                "timeline_start": 15000,
                                "duration": 3000,
                                "source_start": 3000,
                                "source_duration": 3000,
                                "metadata": {"ai_plan_id": "plan", "broll": True},
                            },
                        ],
                    },
                    {
                        "id": "audio",
                        "kind": "audio",
                        "name": "Audio",
                        "locked": False,
                        "muted": False,
                        "clips": [
                            {
                                "id": "music",
                                "asset_id": "m",
                                "timeline_start": 0,
                                "duration": 20000,
                                "source_start": 0,
                                "source_duration": 20000,
                                "volume": 0.12,
                                "metadata": {"ai_plan_id": "plan", "music_bed": True},
                            }
                        ],
                    },
                ],
                "captions": [
                    {
                        "id": "cap-1",
                        "start": 1000,
                        "duration": 3000,
                        "text": "First caption",
                        "style": {"source": "transcript"},
                    },
                    {
                        "id": "cap-2",
                        "start": 12000,
                        "duration": 3000,
                        "text": "Second caption",
                        "style": {"source": "transcript"},
                    },
                ],
            }
        ],
    }


def test_caption_change_is_scoped_and_preserves_story_clips():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Make the captions smaller in the first 5 seconds",
    )
    assert proposal["interpreted_intents"] == ["restyle_captions"]
    assert proposal["scope_start_sec"] == 0
    assert proposal["scope_end_sec"] == 5
    assert len(proposal["operations"]) == 1
    assert proposal["operations"][0]["payload"]["caption_id"] == "cap-1"

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    sequence = changed["sequences"][0]
    assert sequence["captions"][0]["style"]["size_scale"] == 0.85
    assert "size_scale" not in sequence["captions"][1]["style"]
    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    assert video["clips"][0]["id"] == "primary"
    assert video["clips"][0]["duration"] == 20000


def test_remove_broll_only_removes_overlays_inside_scope():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove B-roll from the intro",
    )
    assert proposal["scope_end_sec"] == 10
    assert len(proposal["operations"]) == 1

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    overlay = next(
        track for track in changed["sequences"][0]["tracks"] if track["id"] == "overlay"
    )
    assert [clip["id"] for clip in overlay["clips"]] == ["broll-2"]


def test_lower_music_keeps_non_music_tracks_untouched():
    state = _state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Lower the music",
    )
    assert proposal["interpreted_intents"] == ["lower_music"]
    assert len(proposal["operations"]) == 1

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    music = next(
        track for track in changed["sequences"][0]["tracks"] if track["id"] == "audio"
    )["clips"][0]
    assert music["volume"] == 0.06
    assert changed["sequences"][0]["tracks"][0]["clips"][0]["id"] == "primary"


def test_primary_cut_pacing_request_is_supported():
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        instruction="Make the first ten seconds faster",
    )
    assert proposal["interpreted_intents"] == ["tighten_pacing"]
    assert proposal["scope_start_sec"] == 0
    assert proposal["scope_end_sec"] == 10
    assert proposal["operations"][0]["operation"] == "retime_scope"
    assert proposal["operations"][0]["payload"]["scope_end"] == 10000



def test_scoped_edit_never_mutates_an_item_that_crosses_the_scope_boundary():
    state = _state()
    overlay = next(
        track for track in state["sequences"][0]["tracks"] if track["id"] == "overlay"
    )
    overlay["clips"][0]["timeline_start"] = 9000
    overlay["clips"][0]["duration"] = 3000
    overlay["clips"][0]["source_duration"] = 3000

    try:
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=state,
            instruction="Remove B-roll from the intro",
        )
    except ValueError as exc:
        assert "no matching timeline items" in str(exc)
    else:
        raise AssertionError("boundary-crossing B-roll must be preserved")


def test_local_music_request_does_not_change_a_full_length_music_bed():
    try:
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=_state(),
            instruction="Lower the music in the intro",
        )
    except ValueError as exc:
        assert "no matching timeline items" in str(exc)
    else:
        raise AssertionError("localized music change must not leak outside scope")



def _speaker_state():
    state = _state()
    sequence = state["sequences"][0]
    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    video["clips"] = [
        {
            "id": "p1",
            "asset_id": "a",
            "timeline_start": 0,
            "duration": 5000,
            "source_start": 0,
            "source_duration": 5000,
            "metadata": {
                "ai_plan_id": "plan",
                "primary_speaker": "speaker_0",
            },
        },
        {
            "id": "p2",
            "asset_id": "a",
            "timeline_start": 5000,
            "duration": 5000,
            "source_start": 5000,
            "source_duration": 5000,
            "metadata": {
                "ai_plan_id": "plan",
                "primary_speaker": "speaker_1",
            },
        },
        {
            "id": "p3",
            "asset_id": "a",
            "timeline_start": 10000,
            "duration": 5000,
            "source_start": 10000,
            "source_duration": 5000,
            "metadata": {
                "ai_plan_id": "plan",
                "primary_speaker": "speaker_0",
            },
        },
    ]
    overlay = next(track for track in sequence["tracks"] if track["id"] == "overlay")
    overlay["clips"] = [
        {
            "id": "speaker-b-broll",
            "asset_id": "b",
            "timeline_start": 6000,
            "duration": 2500,
            "source_start": 0,
            "source_duration": 2500,
            "metadata": {"ai_plan_id": "plan", "broll": True},
        },
        {
            "id": "after-broll",
            "asset_id": "b",
            "timeline_start": 11000,
            "duration": 2000,
            "source_start": 2500,
            "source_duration": 2000,
            "metadata": {"ai_plan_id": "plan", "broll": True},
        },
    ]
    audio = next(track for track in sequence["tracks"] if track["id"] == "audio")
    audio["clips"][0]["duration"] = 15000
    audio["clips"][0]["source_duration"] = 15000
    sequence["captions"] = [
        {
            "id": "speaker-a-caption",
            "start": 1000,
            "duration": 3000,
            "text": "Speaker A",
            "style": {"source": "transcript", "ai_plan_id": "plan"},
        },
        {
            "id": "speaker-b-caption",
            "start": 5500,
            "duration": 3500,
            "text": "Speaker B",
            "style": {"source": "transcript", "ai_plan_id": "plan"},
        },
        {
            "id": "speaker-a-after",
            "start": 11000,
            "duration": 2500,
            "text": "Speaker A returns",
            "style": {"source": "transcript", "ai_plan_id": "plan"},
        },
    ]
    return state


def test_remove_speaker_b_ripples_all_synchronized_tracks():
    state = _speaker_state()
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove Speaker B",
    )
    assert proposal["interpreted_intents"] == ["remove_speaker_1"]
    assert len(proposal["operations"]) == 1
    operation = proposal["operations"][0]
    assert operation["operation"] == "remove_speaker_ripple"
    assert operation["component"] == "story"
    assert operation["payload"]["clip_ids"] == ["p2"]

    changed = apply_constrained_operations(
        state=state,
        operations=proposal["operations"],
    )
    sequence = changed["sequences"][0]
    video = next(track for track in sequence["tracks"] if track["id"] == "video")
    assert [clip["id"] for clip in video["clips"]] == ["p1", "p3"]
    assert [clip["timeline_start"] for clip in video["clips"]] == [0, 5000]

    overlay = next(track for track in sequence["tracks"] if track["id"] == "overlay")
    assert [clip["id"] for clip in overlay["clips"]] == ["after-broll"]
    assert overlay["clips"][0]["timeline_start"] == 6000

    audio = next(track for track in sequence["tracks"] if track["id"] == "audio")
    assert audio["clips"][0]["duration"] == 10000
    assert audio["clips"][0]["source_duration"] == 10000

    assert [cue["id"] for cue in sequence["captions"]] == [
        "speaker-a-caption",
        "speaker-a-after",
    ]
    assert sequence["captions"][1]["start"] == 6000


def test_speaker_removal_refuses_locked_track_that_would_lose_sync():
    state = _speaker_state()
    audio = next(
        track for track in state["sequences"][0]["tracks"] if track["id"] == "audio"
    )
    audio["locked"] = True
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Remove Speaker B",
    )

    try:
        apply_constrained_operations(
            state=state,
            operations=proposal["operations"],
        )
    except ValueError as exc:
        assert "locked" in str(exc)
        assert "lose sync" in str(exc)
    else:
        raise AssertionError("locked synchronized track must block ripple editing")


def test_scoped_speaker_removal_only_selects_fully_contained_primary_clips():
    state = _speaker_state()
    try:
        build_constrained_proposal(
            project_id="project-1",
            user_id="user-1",
            state=state,
            instruction="Remove Speaker B from the first 4 seconds",
        )
    except ValueError as exc:
        assert "no matching timeline items" in str(exc)
    else:
        raise AssertionError("speaker outside the scope should not be removed")



def test_replace_broll_preserves_exact_timeline_slot():
    state = _state()
    operation = {
        "id": "replace-1",
        "operation": "replace_broll",
        "component": "broll",
        "payload": {
            "sequence_id": "seq",
            "track_id": "overlay",
            "clip_id": "broll-1",
            "asset_id": "replacement-video",
            "source_start": 4000,
            "source_duration": 3000,
            "source_intelligence_id": "intel-replacement",
            "source_observation_index": 2,
            "relevance_score": 0.91,
            "replacement_query": "factory footage",
        },
        "reason": "Grounded semantic replacement",
    }

    changed = apply_constrained_operations(state=state, operations=[operation])
    overlay = next(
        track for track in changed["sequences"][0]["tracks"] if track["id"] == "overlay"
    )
    replaced = next(clip for clip in overlay["clips"] if clip["id"] == "broll-1")
    assert replaced["timeline_start"] == 2000
    assert replaced["duration"] == 3000
    assert replaced["asset_id"] == "replacement-video"
    assert replaced["source_start"] == 4000
    assert replaced["source_duration"] == 3000
    assert replaced["metadata"]["semantic_replacement"] is True
    assert replaced["metadata"]["replacement_from_asset_id"] == "b"
    assert replaced["metadata"]["source_intelligence_id"] == "intel-replacement"
    untouched = next(clip for clip in overlay["clips"] if clip["id"] == "broll-2")
    assert untouched["asset_id"] == "b"
    assert untouched["timeline_start"] == 15000


def test_replace_broll_refuses_timeline_duration_change():
    state = _state()
    operation = {
        "id": "replace-1",
        "operation": "replace_broll",
        "component": "broll",
        "payload": {
            "sequence_id": "seq",
            "track_id": "overlay",
            "clip_id": "broll-1",
            "asset_id": "replacement-video",
            "source_start": 0,
            "source_duration": 2500,
        },
        "reason": "Invalid duration",
    }
    try:
        apply_constrained_operations(state=state, operations=[operation])
    except ValueError as exc:
        assert "exact timeline-slot duration" in str(exc)
    else:
        raise AssertionError("B-roll replacement must preserve target duration")


def test_additional_semantic_operation_builds_reviewable_proposal():
    state = _state()
    extra = {
        "id": "semantic-1",
        "operation": "replace_broll",
        "component": "broll",
        "payload": {
            "sequence_id": "seq",
            "track_id": "overlay",
            "clip_id": "broll-1",
            "asset_id": "replacement-video",
            "source_start": 0,
            "source_duration": 3000,
        },
        "reason": "Semantic alternative",
    }
    proposal = build_constrained_proposal(
        project_id="project-1",
        user_id="user-1",
        state=state,
        instruction="Replace B-roll in the intro",
        additional_intents=["replace_broll"],
        additional_operations=[extra],
    )
    assert proposal["interpreted_intents"] == ["replace_broll"]
    assert proposal["operations"] == [extra]
    assert "primary story clips" in proposal["preserve_rules"][-1]



def test_repair_caption_preserves_text_and_replaces_one_cue_with_reviewed_parts():
    state = _state()
    sequence = state["sequences"][0]
    sequence["captions"] = [
        {
            "id": "cap",
            "start": 1000,
            "duration": 3000,
            "text": "One caption becomes two parts",
            "style": {"source": "transcript"},
        }
    ]
    operation = {
        "id": "qa-1",
        "operation": "repair_caption",
        "component": "captions",
        "payload": {
            "sequence_id": "seq",
            "caption_id": "cap",
            "replacements": [
                {
                    "id": "qa-a",
                    "start": 1200,
                    "duration": 1200,
                    "text": "One caption",
                    "style": {"source": "transcript", "qa_repaired": True},
                },
                {
                    "id": "qa-b",
                    "start": 2400,
                    "duration": 1400,
                    "text": "becomes two parts",
                    "style": {"source": "transcript", "qa_repaired": True},
                },
            ],
        },
        "reason": "Repair QA caption",
    }

    changed = apply_constrained_operations(state=state, operations=[operation])
    cues = changed["sequences"][0]["captions"]
    assert [cue["id"] for cue in cues] == ["qa-a", "qa-b"]
    assert " ".join(cue["text"] for cue in cues) == "One caption becomes two parts"
    assert cues[0]["start"] == 1200
    assert cues[1]["start"] == 2400


def test_repair_caption_refuses_text_rewrite():
    state = _state()
    sequence = state["sequences"][0]
    sequence["captions"] = [
        {
            "id": "cap",
            "start": 1000,
            "duration": 3000,
            "text": "Keep these exact words",
            "style": {},
        }
    ]
    operation = {
        "id": "qa-1",
        "operation": "repair_caption",
        "component": "captions",
        "payload": {
            "sequence_id": "seq",
            "caption_id": "cap",
            "replacements": [
                {
                    "id": "qa-a",
                    "start": 1000,
                    "duration": 3000,
                    "text": "Different words",
                    "style": {},
                }
            ],
        },
        "reason": "Invalid rewrite",
    }
    try:
        apply_constrained_operations(state=state, operations=[operation])
    except ValueError as exc:
        assert "preserve the original caption text" in str(exc)
    else:
        raise AssertionError("QA repair must not rewrite caption text")
