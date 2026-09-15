"""Unit-level tests for AI-plan application data constraints.

Integration application requires analyzed media, so these tests focus on request
schema behavior while API integration remains covered by the shared state tests.
"""
from models.ai_plan import ApplyAIEditPlanRequest


def test_apply_plan_defaults_to_non_destructive_behavior():
    body = ApplyAIEditPlanRequest(expected_version=3)
    assert body.expected_version == 3
    assert body.replace_existing_video_clips is False
