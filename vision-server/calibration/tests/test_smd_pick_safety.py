import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import detect_small_part_dry_run as detector  # noqa: E402
import full_pick_place_same_spot as workflow  # noqa: E402


def make_depth_detector(top_depth_m):
    instance = object.__new__(detector.SmallPartDetector)
    instance.args = SimpleNamespace(
        min_depth_pixels=9,
        min_depth_valid_fraction=0.55,
        max_depth_mad_mm=2.0,
        support_ring_outer_px=12,
        support_ring_inner_px=3,
        min_support_depth_pixels=40,
        max_support_plane_mad_mm=2.0,
        min_observed_height_mm=0.5,
        part_height_mm=3.0,
        height_tolerance_mm=2.0,
    )
    instance.K = np.asarray([
        [1000.0, 0.0, 50.0],
        [0.0, 1000.0, 50.0],
        [0.0, 0.0, 1.0],
    ])
    instance.depth = np.full((100, 100), 0.500, dtype=np.float32)
    contour = np.asarray([
        [[40, 45]], [[60, 45]], [[60, 55]], [[40, 55]],
    ], dtype=np.int32)
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    instance.depth[mask > 0] = top_depth_m
    base_t_camera = np.eye(4)
    base_t_camera[:3, :3] = np.diag([1.0, -1.0, -1.0])
    return instance, contour, mask, base_t_camera


def sample_geometry(top_depth_m):
    instance, contour, mask, base_t_camera = make_depth_detector(top_depth_m)
    return instance._sample_depth_geometry(
        contour, mask, 0, 0, 100, 100, 50.0, 50.0, base_t_camera
    )


def test_axis_mean_obeys_180_degree_symmetry():
    result = detector.axis_angle_mean_deg([-89.0, 89.0])
    assert abs(abs(result) - 90.0) < 1e-6


def test_component_top_is_separated_from_support_plane():
    result = sample_geometry(0.497)
    assert result is not None
    assert abs(result['observed_height_mm'] - 3.0) < 0.01


def test_flat_depth_cannot_claim_component_height():
    assert sample_geometry(0.500) is None


def test_approach_only_never_builds_gripper_or_descent_command(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow, 'validate_target_file', lambda *args: {})
    monkeypatch.setattr(
        workflow, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )
    monkeypatch.setattr(
        workflow, 'gripper_open',
        lambda position: (_ for _ in ()).throw(AssertionError('gripper called')),
    )
    monkeypatch.setattr(sys, 'argv', [
        'full_pick_place_same_spot.py',
        '--skip-detection', '--target-file', 'target.json',
        '--approach-only', '--execute', '--confirm-approach-only',
    ])

    workflow.main()

    flattened = ' '.join(str(value) for _, command in calls for value in command)
    assert len(calls) == 7
    assert flattened.count('--track-base-target-file') == 3
    assert '--verify-only' in calls[-1][1]
    assert 'run_vertical_test.sh' not in flattened
    assert 'run_grasp_place_cycle.sh' not in flattened


def test_full_cycle_uses_closed_loop_and_calibrated_grasp_offset(monkeypatch):
    calls = []
    gripper_positions = []
    monkeypatch.setattr(workflow, 'validate_target_file', lambda *args: {})
    monkeypatch.setattr(
        workflow, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )
    monkeypatch.setattr(
        workflow, 'gripper_open', gripper_positions.append,
    )
    monkeypatch.setattr(sys, 'argv', [
        'full_pick_place_same_spot.py',
        '--skip-detection', '--target-file', 'target.json',
        '--grasp-z-offset-mm', '-5',
        '--execute', '--confirm-full-cycle',
    ])

    workflow.main()

    assert len(calls) == 10
    assert gripper_positions == [100]
    descent = next(command for _, command in calls if 'run_vertical_test.sh' in command[0])
    cycle = next(command for _, command in calls if 'run_grasp_place_cycle.sh' in command[0])
    assert descent[descent.index('--target-z-offset-mm') + 1] == '-5.0'
    assert descent[descent.index('--max-target-xy-error-mm') + 1] == '1.0'
    assert cycle[cycle.index('--grasp-z-offset-mm') + 1] == '-5.0'


def test_provisional_handeye_blocks_full_cycle_before_motion(monkeypatch):
    calls = []
    monkeypatch.setattr(
        workflow, 'validate_target_file',
        lambda *args: {'handeye': {'warning': 'not validated'}},
    )
    monkeypatch.setattr(
        workflow, 'run',
        lambda command, label, timeout=None: calls.append((label, command)),
    )
    monkeypatch.setattr(sys, 'argv', [
        'full_pick_place_same_spot.py',
        '--skip-detection', '--target-file', 'target.json',
        '--grasp-z-offset-mm', '-5',
        '--execute', '--confirm-full-cycle',
    ])

    try:
        workflow.main()
    except RuntimeError as exc:
        assert 'provisional' in str(exc)
    else:
        raise AssertionError('provisional calibration was not blocked')
    assert calls == []
