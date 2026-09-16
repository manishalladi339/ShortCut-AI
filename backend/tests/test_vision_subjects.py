"""Tests for visual-subject normalization used by smart reframing."""
from services.vision import _data_url, _normalized_box, _normalized_subjects


def test_normalized_box_clamps_to_frame_bounds():
    box = _normalized_box(
        {
            "x": -0.2,
            "y": 0.1,
            "width": 1.4,
            "height": 0.95,
        }
    )
    assert box == {
        "x": 0.0,
        "y": 0.1,
        "width": 1.0,
        "height": 0.9,
    }


def test_normalized_box_rejects_start_at_far_edge():
    assert _normalized_box(
        {"x": 1.0, "y": 0.2, "width": 0.2, "height": 0.4}
    ) is None
    assert _normalized_box(
        {"x": 0.2, "y": 1.0, "width": 0.2, "height": 0.4}
    ) is None


def test_normalized_subjects_clamps_scores_and_drops_invalid_boxes():
    subjects = _normalized_subjects(
        [
            {
                "label": "visible person",
                "box": {
                    "x": 0.2,
                    "y": 0.1,
                    "width": 0.3,
                    "height": 0.7,
                },
                "prominence": 1.7,
                "speaking_likelihood": -0.4,
            },
            {
                "label": "invalid",
                "box": {
                    "x": 1.0,
                    "y": 0.1,
                    "width": 0.2,
                    "height": 0.4,
                },
            },
        ]
    )
    assert len(subjects) == 1
    assert subjects[0]["label"] == "visible person"
    assert subjects[0]["prominence"] == 1.0
    assert subjects[0]["speaking_likelihood"] == 0.0



def test_data_url_preserves_supported_image_mime(tmp_path):
    png = tmp_path / "still.png"
    png.write_bytes(b"not-real-png-but-mime-test")
    assert _data_url(png).startswith("data:image/png;base64,")

    webp = tmp_path / "still.webp"
    webp.write_bytes(b"not-real-webp-but-mime-test")
    assert _data_url(webp).startswith("data:image/webp;base64,")
