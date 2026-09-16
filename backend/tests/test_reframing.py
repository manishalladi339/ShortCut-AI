"""Tests for evidence-gated subject-aware reframing."""
from services.reframing import (
    build_reframe_suggestion,
    calculate_reframe_transform,
)


def _observation(*, people_count=1, subjects=None):
    return {
        "index": 2,
        "time": 5.0,
        "people_count": people_count,
        "subjects": subjects or [],
    }


def test_landscape_single_subject_gets_portrait_cover_crop():
    record = {
        "visual_observations": [
            _observation(
                subjects=[
                    {
                        "label": "person_1",
                        "box": {
                            "x": 0.68,
                            "y": 0.12,
                            "width": 0.20,
                            "height": 0.70,
                        },
                        "prominence": 0.82,
                        "speaking_likelihood": 0.9,
                    }
                ]
            )
        ]
    }
    result = build_reframe_suggestion(
        record=record,
        start=2.0,
        end=8.0,
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
    )

    assert result is not None
    assert result["strategy"] == "single_visible_subject"
    assert result["identity_claimed"] is False
    assert result["confidence"] == 0.82
    assert result["transform"]["scale"] > 3.0
    assert result["transform"]["position_x"] < 0
    assert result["observation_index"] == 2


def test_ambiguous_two_person_frame_is_not_reframed():
    record = {
        "visual_observations": [
            _observation(
                people_count=2,
                subjects=[
                    {
                        "label": "left_person",
                        "box": {"x": 0.05, "y": 0.1, "width": 0.35, "height": 0.8},
                        "prominence": 0.8,
                        "speaking_likelihood": 0.68,
                    },
                    {
                        "label": "right_person",
                        "box": {"x": 0.55, "y": 0.1, "width": 0.35, "height": 0.8},
                        "prominence": 0.8,
                        "speaking_likelihood": 0.61,
                    },
                ],
            )
        ]
    }
    result = build_reframe_suggestion(
        record=record,
        start=0.0,
        end=10.0,
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
    )
    assert result is None


def test_clear_visible_speaking_cue_can_reframe_multi_person_frame():
    record = {
        "visual_observations": [
            _observation(
                people_count=2,
                subjects=[
                    {
                        "label": "left_person",
                        "box": {"x": 0.03, "y": 0.08, "width": 0.38, "height": 0.82},
                        "prominence": 0.8,
                        "speaking_likelihood": 0.91,
                    },
                    {
                        "label": "right_person",
                        "box": {"x": 0.58, "y": 0.1, "width": 0.32, "height": 0.78},
                        "prominence": 0.75,
                        "speaking_likelihood": 0.42,
                    },
                ],
            )
        ]
    }
    result = build_reframe_suggestion(
        record=record,
        start=0.0,
        end=10.0,
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
    )
    assert result is not None
    assert result["strategy"] == "visible_speaking_cue"
    assert result["confidence"] == 0.91
    assert result["subject_label"] == "left_person"


def test_observation_must_be_inside_source_range():
    record = {
        "visual_observations": [
            {
                **_observation(
                    subjects=[
                        {
                            "label": "person",
                            "box": {
                                "x": 0.3,
                                "y": 0.1,
                                "width": 0.4,
                                "height": 0.8,
                            },
                            "prominence": 0.9,
                        }
                    ]
                ),
                "time": 12.0,
            }
        ]
    }
    result = build_reframe_suggestion(
        record=record,
        start=0.0,
        end=8.0,
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
    )
    assert result is None


def test_transform_never_exposes_canvas_outside_scaled_media():
    transform = calculate_reframe_transform(
        source_width=1920,
        source_height=1080,
        target_width=1080,
        target_height=1920,
        box={"x": 0.0, "y": 0.0, "width": 0.10, "height": 0.25},
    )
    assert transform is not None

    contain = min(1080 / 1920, 1920 / 1080)
    base_width = 1920 * contain
    base_height = 1080 * contain
    final_width = base_width * transform["scale"]
    final_height = base_height * transform["scale"]
    default_left = (1080 - final_width) / 2
    default_top = (1920 - final_height) / 2
    actual_left = default_left + transform["position_x"]
    actual_top = default_top + transform["position_y"]

    assert actual_left <= 0.001
    assert actual_top <= 0.001
    assert actual_left + final_width >= 1079.999
    assert actual_top + final_height >= 1919.999


def test_portrait_already_framed_subject_can_remain_unchanged():
    result = calculate_reframe_transform(
        source_width=1080,
        source_height=1920,
        target_width=1080,
        target_height=1920,
        box={"x": 0.3, "y": 0.1, "width": 0.4, "height": 0.72},
    )
    assert result is None
