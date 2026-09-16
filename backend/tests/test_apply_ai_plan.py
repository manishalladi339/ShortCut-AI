"""Unit-level tests for AI-plan application data constraints.

Integration application requires analyzed media, so these tests focus on request
schema behavior while API integration remains covered by the shared state tests.
"""
from models.ai_plan import ApplyAIEditPlanRequest, CreateAIEditPlanRequest


def test_apply_plan_defaults_to_non_destructive_behavior():
    body = ApplyAIEditPlanRequest(expected_version=3)
    assert body.expected_version == 3
    assert body.replace_existing_video_clips is False
    assert body.operation_ids is None


def test_apply_plan_accepts_reviewed_operation_ids():
    body = ApplyAIEditPlanRequest(
        expected_version=4,
        operation_ids=["primary-1", "primary-2", "caption-1"],
    )
    assert body.operation_ids == [
        "primary-1",
        "primary-2",
        "caption-1",
    ]



def test_ai_plan_smart_reframe_is_on_by_default_and_can_be_disabled():
    assert CreateAIEditPlanRequest().smart_reframe is True
    assert CreateAIEditPlanRequest(smart_reframe=False).smart_reframe is False
