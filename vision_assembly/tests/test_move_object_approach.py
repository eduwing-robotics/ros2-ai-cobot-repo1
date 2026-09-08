import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "calibration"
    / "scripts"
    / "move_object_approach.py"
)
SPEC = importlib.util.spec_from_file_location("move_object_approach", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("shortest", 87.0),
        ("positive", 87.0),
        ("negative", -93.0),
    ],
)
def test_symmetric_rotation_branch_from_close_view(branch, expected):
    assert MODULE.symmetric_angle_delta_deg(177.0, 90.0, branch) == pytest.approx(
        expected
    )


def test_negative_branch_flips_already_aligned_axis():
    assert MODULE.symmetric_angle_delta_deg(177.0, 177.0, "negative") == pytest.approx(
        -180.0
    )


def test_completion_rejects_stale_sample_inside_loose_rotation_tolerance():
    assert not MODULE.completion_sample_eligible(
        motion_done=1,
        xyz_error_mm=0.0,
        angle_error_deg=0.568,
        joint_error_deg=0.568,
        saw_motion_in_progress=False,
        elapsed_sec=0.05,
    )


def test_completion_accepts_strict_target_after_command_settle_time():
    assert MODULE.completion_sample_eligible(
        motion_done=1,
        xyz_error_mm=0.01,
        angle_error_deg=0.01,
        joint_error_deg=0.01,
        saw_motion_in_progress=False,
        elapsed_sec=0.3,
    )


def test_completion_accepts_normal_tolerance_after_motion_transition():
    assert MODULE.completion_sample_eligible(
        motion_done=1,
        xyz_error_mm=0.5,
        angle_error_deg=0.5,
        joint_error_deg=0.5,
        saw_motion_in_progress=True,
        elapsed_sec=0.1,
    )


@pytest.mark.parametrize("delta", [-5.0, -1.0, 0.0, 1.0, 5.0])
def test_manual_yaw_safety_bound_examples(delta):
    assert MODULE.bounded_manual_yaw_delta(delta) == pytest.approx(delta)


@pytest.mark.parametrize("delta", [-5.01, 5.01, float("nan"), float("inf")])
def test_manual_yaw_rejects_out_of_bound_or_nonfinite(delta):
    with pytest.raises(ValueError):
        MODULE.bounded_manual_yaw_delta(delta)


def test_half_degree_manual_yaw_creates_rotation_waypoint():
    assert MODULE.needs_rotation_waypoint(-0.5, manual_adjustment=True)
    assert not MODULE.needs_rotation_waypoint(-0.5, manual_adjustment=False)


def test_vrm_validated_axis_offset_stays_inside_bounded_yaw_envelope():
    assert MODULE.bounded_manual_yaw_delta(-4.5) == pytest.approx(-4.5)


@pytest.mark.parametrize("delta", [-95.0, -89.9, 0.0, 89.9, 95.0])
def test_held_part_yaw_safety_bound_examples(delta):
    assert MODULE.bounded_held_part_yaw_delta(delta) == pytest.approx(delta)


@pytest.mark.parametrize("delta", [-95.01, 95.01, float("nan"), float("inf")])
def test_held_part_yaw_rejects_out_of_bound_or_nonfinite(delta):
    with pytest.raises(ValueError):
        MODULE.bounded_held_part_yaw_delta(delta)
