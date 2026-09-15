"""Tests for safe granular AI-plan review selection."""
import pytest

from services.plan_review import (
    PlanReviewError,
    assign_operation_ids,
    select_reviewed_operations,
)


def _operations():
    return [
        {"id": "p1", "operation": "add_clip", "payload": {}},
        {"id": "p2", "operation": "add_clip", "payload": {}},
        {"id": "b1", "operation": "add_broll_overlay", "payload": {}},
        {"id": "c1", "operation": "add_caption", "payload": {}},
    ]


def test_assign_operation_ids_makes_ids_present_and_unique():
    operations = [
        {"operation": "add_clip", "payload": {}},
        {"operation": "add_caption", "payload": {}},
    ]
    assign_operation_ids(operations)
    ids = [item["id"] for item in operations]
    assert all(ids)
    assert len(set(ids)) == 2


def test_no_review_selection_applies_everything():
    selected, applied, skipped = select_reviewed_operations(
        _operations(),
        None,
    )
    assert len(selected) == 4
    assert applied == ["p1", "p2", "b1", "c1"]
    assert skipped == []


def test_optional_broll_and_caption_can_be_reviewed_individually():
    selected, applied, skipped = select_reviewed_operations(
        _operations(),
        ["p1", "p2", "c1"],
    )
    assert [item["id"] for item in selected] == ["p1", "p2", "c1"]
    assert applied == ["p1", "p2", "c1"]
    assert skipped == ["b1"]


def test_primary_story_cannot_be_partially_selected():
    with pytest.raises(PlanReviewError) as exc:
        select_reviewed_operations(
            _operations(),
            ["p1", "b1"],
        )
    assert exc.value.code == "planner.primary_story_partial_selection"


def test_unknown_operation_id_is_rejected():
    with pytest.raises(PlanReviewError) as exc:
        select_reviewed_operations(
            _operations(),
            ["p1", "p2", "missing"],
        )
    assert exc.value.code == "planner.unknown_operation_selection"


def test_legacy_plan_requires_regeneration_for_granular_review():
    legacy = [{"operation": "add_clip", "payload": {}}]
    with pytest.raises(PlanReviewError) as exc:
        select_reviewed_operations(legacy, ["anything"])
    assert exc.value.code == "planner.plan_not_reviewable"
