"""Representative frame-time selection tests."""
from services.frame_sampler import representative_times


def test_representative_times_use_scene_midpoints():
    scenes = [
        {"start": 0.0, "end": 10.0},
        {"start": 10.0, "end": 20.0},
    ]
    assert representative_times(scenes, duration_sec=20.0, max_frames=10) == [5.0, 15.0]


def test_representative_times_downsample_deterministically():
    scenes = [
        {"start": float(i * 10), "end": float((i + 1) * 10)}
        for i in range(10)
    ]
    times = representative_times(scenes, duration_sec=100.0, max_frames=3)
    assert times == [5.0, 45.0, 95.0]
