"""Feedback-schema tests."""
import pytest
from pydantic import ValidationError

from models.planner_feedback import PlannerFeedbackRequest


def test_feedback_accepts_supported_outcomes():
    assert PlannerFeedbackRequest(outcome="accepted").outcome == "accepted"
    assert PlannerFeedbackRequest(outcome="modified").outcome == "modified"


def test_feedback_rejects_unknown_outcome():
    with pytest.raises(ValidationError):
        PlannerFeedbackRequest(outcome="maybe")
