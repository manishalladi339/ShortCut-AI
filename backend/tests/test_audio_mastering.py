"""Tests for deterministic two-pass audio mastering helpers."""
import math

from services.audio_mastering import (
    build_master_filter,
    build_measure_filter,
    has_measurable_signal,
    parse_loudnorm_json,
)


def _stderr(
    *,
    input_i="-23.05",
    input_tp="-2.34",
    input_lra="7.80",
    input_thresh="-33.12",
    output_i="-13.98",
    output_tp="-1.50",
    output_lra="7.70",
    output_thresh="-24.02",
    target_offset="-0.02",
):
    return f"""
[Parsed_loudnorm_0 @ 0x123] some log line
{{
    "input_i" : "{input_i}",
    "input_tp" : "{input_tp}",
    "input_lra" : "{input_lra}",
    "input_thresh" : "{input_thresh}",
    "output_i" : "{output_i}",
    "output_tp" : "{output_tp}",
    "output_lra" : "{output_lra}",
    "output_thresh" : "{output_thresh}",
    "normalization_type" : "dynamic",
    "target_offset" : "{target_offset}"
}}
"""


def test_parse_loudnorm_json_extracts_measurements():
    result = parse_loudnorm_json(_stderr())
    assert result["input_i"] == -23.05
    assert result["input_tp"] == -2.34
    assert result["output_i"] == -13.98
    assert result["output_tp"] == -1.5
    assert result["target_offset"] == -0.02
    assert result["normalization_type"] == "dynamic"


def test_silent_measurement_is_not_used_for_second_pass():
    result = parse_loudnorm_json(
        _stderr(
            input_i="-inf",
            input_tp="-inf",
            input_lra="0.00",
            input_thresh="-70.00",
            output_i="-inf",
            output_tp="-inf",
            output_lra="0.00",
            output_thresh="-70.00",
            target_offset="0.00",
        )
    )
    assert math.isinf(result["input_i"])
    assert has_measurable_signal(result) is False


def test_measure_filter_contains_configured_targets():
    value = build_measure_filter(
        target_lufs=-14.0,
        true_peak_dbtp=-1.5,
        loudness_range=11.0,
    )
    assert "I=-14.00" in value
    assert "TP=-1.50" in value
    assert "LRA=11.00" in value
    assert "print_format=json" in value


def test_master_filter_uses_first_pass_measurements():
    measured = parse_loudnorm_json(_stderr())
    value = build_master_filter(
        measured,
        target_lufs=-14.0,
        true_peak_dbtp=-1.5,
        loudness_range=11.0,
    )
    assert "measured_I=-23.0500" in value
    assert "measured_TP=-2.3400" in value
    assert "measured_LRA=7.8000" in value
    assert "measured_thresh=-33.1200" in value
    assert "offset=-0.0200" in value
    assert "linear=true" in value
