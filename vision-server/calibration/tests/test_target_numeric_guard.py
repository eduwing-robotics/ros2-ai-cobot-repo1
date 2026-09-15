import importlib
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from target_numeric_guard import finite_vector, validate_target_numbers
import full_pick_place_same_spot as workflow


def target():
    return {'timestamp_unix': time.time(), 'part_center_base_mm': [1, 2, 3],
            'depth_quality': {'accepted': True, 'valid_fraction_min': 0.8,
                              'local_mad_max_mm': 0.5},
            'part_size_input_mm': [6, 3.5, 2.5], 'long_axis_angle_base_deg': 0}


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf'), True, None])
@pytest.mark.parametrize('field', ['timestamp_unix', 'center', 'quality', 'size'])
def test_nonfinite_metadata_is_rejected_before_comparisons(bad, field):
    payload = target()
    if field == 'center':
        payload['part_center_base_mm'][1] = bad
    elif field == 'quality':
        payload['depth_quality']['local_mad_max_mm'] = bad
    elif field == 'size':
        payload['part_size_input_mm'][0] = bad
    else:
        payload[field] = bad
    with pytest.raises(ValueError):
        validate_target_numbers(payload)


def test_finite_target_is_preserved_and_old_freshness_limit_remains(tmp_path):
    payload = target()
    before = json.dumps(payload)
    validate_target_numbers(payload)
    assert json.dumps(payload) == before
    path = tmp_path / 'target.json'
    path.write_text(before)
    assert workflow.validate_target_file(path, 120) == payload
    payload['timestamp_unix'] -= 1000
    path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match='stale'):
        workflow.validate_target_file(path, 120)


def test_nan_timestamp_and_age_limit_cannot_bypass_workflow(tmp_path):
    path = tmp_path / 'target.json'
    payload = target()
    path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match='finite'):
        workflow.validate_target_file(path, float('nan'))
    payload['timestamp_unix'] = float('nan')
    path.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match='finite'):
        workflow.validate_target_file(path, 120)


@pytest.mark.parametrize('values', [[1, 2], [1, 2, 3, 4], [1, 2, float('nan')], '123'])
def test_vector_shape_and_finite_pose(values):
    with pytest.raises(ValueError):
        finite_vector(values, 3, 'pose')


@pytest.mark.parametrize('module_name', ['full_pick_place_same_spot', 'move_object_approach',
                                       'grasp_place_cycle', 'move_vertical_test'])
def test_nan_cli_rejected_before_device_initialization(monkeypatch, module_name):
    module = importlib.import_module(module_name)
    if hasattr(module, 'rclpy'):
        monkeypatch.setattr(module.rclpy, 'init', lambda *a, **k: pytest.fail('ROS initialized'))
    if hasattr(module, 'run'):
        monkeypatch.setattr(module, 'run', lambda *a, **k: pytest.fail('subprocess started'))
    monkeypatch.setattr(sys, 'argv', [module_name, '--target-file', 'unused.json',
                                    '--max-target-age-sec', 'nan'])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2
