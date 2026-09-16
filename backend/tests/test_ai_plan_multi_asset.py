"""Schema tests for standard vs Multi-Asset Director limits."""
import pytest
from pydantic import ValidationError

from models.ai_plan import CreateAIEditPlanRequest


def test_standard_mode_keeps_short_form_limits():
    request = CreateAIEditPlanRequest(
        director_mode="standard",
        target_duration_sec=300,
        max_clips=30,
    )
    assert request.director_mode == "standard"

    with pytest.raises(ValidationError):
        CreateAIEditPlanRequest(
            director_mode="standard",
            target_duration_sec=301,
        )

    with pytest.raises(ValidationError):
        CreateAIEditPlanRequest(
            director_mode="standard",
            max_clips=31,
        )


def test_multi_asset_mode_allows_long_form_story_plans():
    request = CreateAIEditPlanRequest(
        director_mode="multi_asset",
        target_duration_sec=900,
        max_clips=80,
        min_source_assets=4,
        max_source_share=0.45,
    )
    assert request.director_mode == "multi_asset"
    assert request.target_duration_sec == 900
    assert request.max_clips == 80
    assert request.min_source_assets == 4
    assert request.max_source_share == 0.45
