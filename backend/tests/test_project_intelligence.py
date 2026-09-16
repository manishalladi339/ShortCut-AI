"""Tests for deterministic whole-project intelligence synthesis."""
from services.project_intelligence import synthesize_project_intelligence


def test_project_intelligence_clusters_cross_asset_topics_and_preserves_sources():
    records = [
        {
            "id": "intel-a",
            "asset_id": "asset-a",
            "semantic_units": [
                {"start": 0, "end": 5, "text": "The factory almost ran out of cash.", "speakers": ["speaker_0"]},
                {"start": 8, "end": 13, "text": "Customers needed a faster workflow.", "speakers": ["speaker_0"]},
            ],
            "semantic_vectors": [[1.0, 0.0], [0.0, 1.0]],
            "visual_observations": [
                {"time": 2, "shot_type": "wide", "people_count": 1, "visible_objects": ["factory"], "text_on_screen": None}
            ],
            "speakers": ["speaker_0"],
        },
        {
            "id": "intel-b",
            "asset_id": "asset-b",
            "semantic_units": [
                {"start": 2, "end": 7, "text": "We were nearly bankrupt before the turnaround.", "speakers": ["speaker_0"]},
                {"start": 9, "end": 15, "text": "The customer onboarding process became much faster.", "speakers": ["speaker_1"]},
            ],
            "semantic_vectors": [[0.98, 0.02], [0.05, 0.95]],
            "visual_observations": [
                {"time": 4, "shot_type": "close-up", "people_count": 0, "visible_objects": ["machine"], "text_on_screen": "Before"}
            ],
            "speakers": ["speaker_0", "speaker_1"],
        },
    ]
    assets = [
        {"id": "asset-a", "filename": "founder.mp4", "kind": "video", "duration_sec": 20},
        {"id": "asset-b", "filename": "customer.mp4", "kind": "video", "duration_sec": 20},
    ]

    result = synthesize_project_intelligence(
        project_id="project-1",
        user_id="user-1",
        records=records,
        assets=assets,
    )

    assert result["asset_count"] == 2
    assert result["semantic_unit_count"] == 4
    assert len(result["topic_clusters"]) == 2
    assert any(len(topic["asset_ids"]) == 2 for topic in result["topic_clusters"])
    evidence_assets = {
        evidence["asset_id"]
        for topic in result["topic_clusters"]
        for evidence in topic["evidence"]
    }
    assert evidence_assets == {"asset-a", "asset-b"}
    # Speaker labels are source-local; speaker_0 from different assets is not merged.
    assert {(item["asset_id"], item["speaker"]) for item in result["speaker_presences"]} >= {
        ("asset-a", "speaker_0"),
        ("asset-b", "speaker_0"),
    }
    assert result["visual_library"]["observation_count"] == 2
    assert result["visual_library"]["observations_with_text"] == 1


def test_project_intelligence_handles_assets_without_semantic_vectors():
    result = synthesize_project_intelligence(
        project_id="project-1",
        user_id="user-1",
        records=[
            {
                "id": "intel-a",
                "asset_id": "asset-a",
                "semantic_units": [{"start": 0, "end": 3, "text": "hello"}],
                "semantic_vectors": [],
                "visual_observations": [],
            }
        ],
        assets=[{"id": "asset-a", "kind": "video"}],
    )
    assert result["semantic_unit_count"] == 0
    assert result["topic_clusters"] == []



def test_latest_records_per_asset_prefers_newest_analysis():
    from services.project_intelligence import latest_records_per_asset

    records = [
        {"id": "old", "asset_id": "asset-a", "updated_at": "2026-09-01T00:00:00"},
        {"id": "new", "asset_id": "asset-a", "updated_at": "2026-09-02T00:00:00"},
        {"id": "other", "asset_id": "asset-b", "updated_at": "2026-09-01T00:00:00"},
    ]
    selected = latest_records_per_asset(records)
    assert [(item["asset_id"], item["id"]) for item in selected] == [
        ("asset-a", "new"),
        ("asset-b", "other"),
    ]
