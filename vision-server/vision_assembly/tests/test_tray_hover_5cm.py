import json
import sys
from pathlib import Path

import numpy as np
import pytest


VISION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = VISION_ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import move_tray_part_approach as approach  # noqa: E402
import run_tray_part_hover_5cm as runner  # noqa: E402
import capture_live_tray_hover_target as capture  # noqa: E402
from tray_hover_contract import (  # noqa: E402
    TrayHoverContractError,
    load_contract,
    normalize_part_type,
    summarize_samples,
    validate_registration,
    validate_surface_workspace,
    validate_unity_target,
)


CONFIG = VISION_ROOT / 'config/tray_hover_5cm.json'


def make_registration(now_ns):
    return {
        'timestamp_ros_ns': now_ns - 100_000_000,
        'state': 'TRACKING',
        'at_trayhome': True,
        'homography_reference_to_image': np.eye(3).tolist(),
    }


def make_unity_state(now_ns, part_type='gpu', xyz=None, angle=179.8):
    if xyz is None:
        xyz = [-517.1, -189.0, -41.7]
    return {
        'schema': 'fr5.tray.unity_state/v1',
        'sequence': 100,
        'timestamp_ros_ns': now_ns - 100_000_000,
        'valid': True,
        'registration_state': 'TRACKING',
        'base_transform_status': 'VALID_COORDINATES_ONLY',
        'coordinate_frame': 'base_link',
        'position_units': 'mm',
        'counts': {part_type: 1},
        'parts': [{
            'id': f'{part_type}:01',
            'part_type': part_type,
            'display_name': part_type,
            'instance_index': 1,
            'reference_xy_px': [690.0, 849.0],
            'camera_xyz_m': [-0.098, 0.105, 0.474],
            'base_xyz_mm': xyz,
            'angle_base_deg': angle,
            'observation_frames': 40,
        }],
    }


def test_contract_supports_five_non_smd_aliases_and_rejects_smd():
    contract = load_contract(CONFIG)
    assert normalize_part_type('nvidia', contract) == 'gpu'
    assert normalize_part_type('sk-hynix', contract) == 'hbm'
    assert normalize_part_type('vrm', contract) == 'black_block'
    assert normalize_part_type('power module', contract) == 'long_orange'
    assert normalize_part_type('inductor', contract) == 'marked_white'
    with pytest.raises(TrayHoverContractError, match='excluded'):
        normalize_part_type('smd', contract)


def test_live_state_requires_fresh_trayhome_and_depth_base_coordinates():
    contract = load_contract(CONFIG)
    now_ns = 1_800_000_000_000_000_000
    registration = validate_registration(
        make_registration(now_ns), contract, now_ns=now_ns
    )
    target = validate_unity_target(
        make_unity_state(now_ns), 'gpu', 1, contract, now_ns=now_ns
    )
    assert registration['state'] == 'TRACKING'
    assert np.allclose(target['base_xyz_mm'], [-517.1, -189.0, -41.7])
    assert target['observation_frames'] == 40

    bad_registration = make_registration(now_ns)
    bad_registration['at_trayhome'] = False
    with pytest.raises(TrayHoverContractError, match='waiting pose'):
        validate_registration(bad_registration, contract, now_ns=now_ns)

    stale = make_unity_state(now_ns)
    stale['timestamp_ros_ns'] = now_ns - 4_000_000_000
    with pytest.raises(TrayHoverContractError, match='stale'):
        validate_unity_target(stale, 'gpu', 1, contract, now_ns=now_ns)


def test_surface_workspace_rejects_wrong_tray_or_bad_depth():
    contract = load_contract(CONFIG)
    assert np.allclose(
        validate_surface_workspace([-748.3, -227.1, -47.8], contract),
        [-748.3, -227.1, -47.8],
    )
    with pytest.raises(TrayHoverContractError, match='outside'):
        validate_surface_workspace([-100.0, -20.0, 500.0], contract)


def test_sample_summary_handles_180_degree_axis_and_rejects_jitter():
    contract = load_contract(CONFIG)
    samples = [
        {
            'base_xyz_mm': np.array([-517.0, -189.0, -41.5]),
            'long_axis_angle_base_deg': 179.8,
        },
        {
            'base_xyz_mm': np.array([-517.2, -188.9, -41.8]),
            'long_axis_angle_base_deg': -0.1,
        },
    ]
    summary = summarize_samples(samples, contract)
    assert summary['max_position_jitter_mm'] < 0.3
    assert abs(approach.symmetric_angle_delta_deg(
        summary['axis_angle_base_deg'], 0.0
    )) < 0.2

    samples[-1]['base_xyz_mm'] = np.array([-510.0, -180.0, -35.0])
    with pytest.raises(TrayHoverContractError, match='position jitter'):
        summarize_samples(samples, contract)


def test_runner_builds_only_fresh_capture_and_exact_50_mm_hover_commands(tmp_path):
    args, contract = runner.parse_args([
        '--part-type', 'vrm',
        '--instance', '2',
        '--target-file', str(tmp_path / 'target.json'),
        '--dry-run',
    ])
    capture, move = runner.build_commands(args, contract)
    assert capture[capture.index('--part-type') + 1] == 'black_block'
    assert move[move.index('--approach-offset-mm') + 1] == '50'
    assert move[move.index('--max-target-age-sec') + 1] == '15'
    assert '--dry-run' in move
    flattened = ' '.join(capture + move).lower()
    assert 'pick_part' not in flattened
    assert 'grasp_place' not in flattened
    assert 'set_gripper' not in flattened


def test_move_defaults_align_rectangles_but_preserve_inductor():
    gpu, _ = approach.parse_args(['--part-type', 'gpu'])
    inductor, _ = approach.parse_args(['--part-type', 'inductor'])
    assert gpu.approach_offset_mm == 50.0
    assert gpu.align_part is True
    assert inductor.align_part is False
    assert gpu.horizontal_speed_percent == 20
    assert gpu.vertical_speed_percent == 15
    assert gpu.rotation_speed_percent == 20


def test_hover_waypoints_never_go_below_fixed_target():
    current = [-528.0, -61.0, 338.0, 180.0, 0.0, 90.0]
    target = [-517.0, -189.0, 8.3]
    waypoints, safe_z = approach.build_waypoints(
        current,
        target,
        [180.0, 0.0, 89.5],
        -0.5,
        100.0,
        20,
        15,
        20,
    )
    assert safe_z == 338.0
    assert np.allclose(waypoints[-1][0][:3], target)
    assert min(stage[0][2] for stage in waypoints) == target[2]
    labels = ' '.join(stage[2] for stage in waypoints).lower()
    assert 'grasp' not in labels
    assert 'descent' not in labels


def test_orientation_arrival_error_handles_wrapped_euler_angles():
    assert approach.orientation_error_deg(
        [180.0, 0.0, 179.8], [-180.0, 0.0, -180.2]
    ) < 1e-6
    assert approach.orientation_error_deg(
        [180.0, 0.0, 90.0], [180.0, 0.0, 92.0]
    ) == pytest.approx(2.0)


def test_motion_confirmation_offset_speed_and_smd_gates():
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--execute'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--approach-offset-mm', '49'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--vertical-speed-percent', '31'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'smd'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--max-target-age-sec', '16'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--max-distance-mm', '651'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--tool-id', '2'])
    with pytest.raises(SystemExit):
        approach.parse_args(['--part-type', 'gpu', '--gripper-axis', 'tool_x'])
    with pytest.raises(SystemExit):
        capture.parse_args(['--part-type', 'gpu', '--max-jitter-mm', '2.1'])
    with pytest.raises(SystemExit):
        capture.parse_args(['--part-type', 'gpu', '--max-state-age-sec', '3.6'])


def test_frozen_target_contract_is_fail_safe(tmp_path):
    target_file = tmp_path / 'target.json'
    payload = {
        'mode': 'frozen_tray_part_target',
        'workflow': 'non_smd_tray_hover_only',
        'timestamp_unix': __import__('time').time(),
        'part_type': 'hbm',
        'instance_index': 1,
        'display_name': 'HBM',
        'part_center_base_mm': [-594.0, -49.7, -47.8],
        'long_axis_angle_base_deg': 0.0,
        'tray_at_home': True,
        'base_transform_status': 'VALID_COORDINATES_ONLY',
        'coordinate_frame': 'base_link',
        'position_units': 'mm',
        'contact_pick_authorized': False,
    }
    target_file.write_text(json.dumps(payload), encoding='utf-8')
    _, part, xyz = approach.load_target(target_file, 'hbm', 1, 15.0)
    assert part['part_type'] == 'hbm'
    assert np.allclose(xyz, [-594.0, -49.7, -47.8])

    payload['contact_pick_authorized'] = True
    target_file.write_text(json.dumps(payload), encoding='utf-8')
    with pytest.raises(RuntimeError, match='contact_pick_authorized'):
        approach.load_target(target_file, 'hbm', 1, 15.0)
