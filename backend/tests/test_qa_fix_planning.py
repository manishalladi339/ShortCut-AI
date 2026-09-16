"""Tests for reviewable Export QA fix planning."""
from datetime import datetime, timezone

from services.qa_fix_planning import build_qa_fix_proposal


def _state():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    return {
        "project_id": "project-1",
        "user_id": "user-1",
        "version": 7,
        "active_sequence_id": "seq",
        "created_at": now,
        "updated_at": now,
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
                                "id": "v1",
                                "asset_id": "a",
                                "timeline_start": 0,
                                "duration": 10000,
                                "source_start": 0,
                                "source_duration": 10000,
                                "metadata": {"ai_plan_id": "plan"},
                            }
                        ],
                    }
                ],
                "captions": [
                    {
                        "id": "c1",
                        "start": 0,
                        "duration": 3500,
                        "text": "First caption",
                        "style": {"source": "transcript"},
                    },
                    {
                        "id": "c2",
                        "start": 3000,
                        "duration": 3000,
                        "text": (
                            "This is a deliberately very long caption containing enough words "
                            "to exceed the visual readability limit and force ShortCut to split "
                            "the cue into multiple smaller caption phrases without changing the text."
                        ),
                        "style": {"source": "transcript"},
                    },
                    {
                        "id": "c3",
                        "start": 9000,
                        "duration": 2500,
                        "text": "Ending caption",
                        "style": {"source": "transcript"},
                    },
                ],
            }
        ],
    }


def _export():
    return {
        "id": "export-1",
        "sequence_id": "seq",
        "project_state_version": 7,
        "qa_report": {
            "issues": [
                {
                    "code": "captions.overlap",
                    "auto_fixable": True,
                    "evidence": {"caption_id": "c2"},
                },
                {
                    "code": "captions.long_text",
                    "auto_fixable": True,
                    "evidence": {"caption_id": "c2"},
                },
                {
                    "code": "captions.out_of_bounds",
                    "auto_fixable": True,
                    "evidence": {"caption_id": "c3", "visual_duration_sec": 10.0},
                },
                {
                    "code": "audio.peak_near_zero",
                    "auto_fixable": False,
                    "evidence": {"max_volume_db": -0.05},
                },
            ]
        },
    }


def test_qa_fix_planner_repairs_only_supported_caption_issues():
    proposal = build_qa_fix_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        export_doc=_export(),
    )

    assert proposal["project_state_version"] == 7
    assert proposal["interpreted_intents"] == ["fix_export_qa"]
    assert len(proposal["operations"]) == 2

    c2 = next(
        operation
        for operation in proposal["operations"]
        if operation["payload"]["caption_id"] == "c2"
    )
    assert c2["operation"] == "repair_caption"
    assert c2["payload"]["qa_issue_codes"] == [
        "captions.long_text",
        "captions.overlap",
    ]
    replacements = c2["payload"]["replacements"]
    assert len(replacements) >= 2
    assert replacements[0]["start"] == 3500
    assert sum(item["duration"] for item in replacements) == 2500
    assert " ".join(item["text"] for item in replacements) == (
        " ".join(_state()["sequences"][0]["captions"][1]["text"].split())
    )

    c3 = next(
        operation
        for operation in proposal["operations"]
        if operation["payload"]["caption_id"] == "c3"
    )
    assert c3["payload"]["qa_issue_codes"] == ["captions.out_of_bounds"]
    repaired = c3["payload"]["replacements"][0]
    assert repaired["start"] == 9000
    assert repaired["duration"] == 1000
    assert repaired["text"] == "Ending caption"


def test_qa_fix_planner_preserves_non_caption_timeline_decisions():
    proposal = build_qa_fix_proposal(
        project_id="project-1",
        user_id="user-1",
        state=_state(),
        export_doc=_export(),
    )
    assert all(operation["component"] == "captions" for operation in proposal["operations"])
    assert any(
        "Preserve every primary story clip" in rule
        for rule in proposal["preserve_rules"]
    )


def test_qa_fix_planner_rejects_report_without_supported_safe_fixes():
    export_doc = _export()
    export_doc["qa_report"]["issues"] = [
        {
            "code": "audio.long_silence",
            "auto_fixable": False,
            "evidence": {},
        }
    ]
    try:
        build_qa_fix_proposal(
            project_id="project-1",
            user_id="user-1",
            state=_state(),
            export_doc=export_doc,
        )
    except ValueError as exc:
        assert "no currently supported safe QA fixes" in str(exc)
    else:
        raise AssertionError("unsupported QA findings should not create a proposal")
