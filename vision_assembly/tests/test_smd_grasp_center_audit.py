import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from smd_grasp_center_audit import compare_observations, describe_center


RECIPE = {'grasp_center_correction_base_mm': {'x': -2.089, 'y': 2.779}}


def observations():
    return {'schema': 'fr5.smd_alignment_observations/v1', 'frame': 'base', 'units': 'mm',
            'calibration_id': 'test-calibration', 'view_id': 'test-view', 'tool_id': 1,
            'samples': [{'sample_id': 'one', 'alignment_confirmed': True,
                         'detected_part_base_xy_mm': [-626.338, -164.944],
                         'aligned_tcp_base_xy_mm': [-628.427, -162.165],
                         'aligned_tcp_abc_deg': [-180., 0., 4.924]}]}


def test_recorded_center_adds_base_correction_once_without_claiming_accuracy():
    r = describe_center(RECIPE, [-626.338, -164.944], [-628.427, -162.165])
    assert r['expected_tcp_base_xy_mm'] == pytest.approx([-628.427, -162.165])
    assert r['arithmetic_consistent'] is True
    assert r['physical_alignment_verified'] is False
    assert r['measured_remaining_error_xy_mm'] is None


def test_double_correction_is_visible():
    r = describe_center(RECIPE, [-626.338, -164.944], [-630.516, -159.386])
    assert r['arithmetic_consistent'] is False
    assert r['plan_minus_expected_xy_mm'] == pytest.approx([-2.089, 2.779])


def test_residual_sign_matches_additional_required_tcp_movement():
    data = observations()
    data['samples'][0]['aligned_tcp_base_xy_mm'] = [-627.427, -164.165]
    r = compare_observations(RECIPE, data)
    assert r['mean_remaining_correction_base_xy_mm'] == pytest.approx([1., -2.])
    assert r['max_residual_norm_mm'] == pytest.approx(5**.5)
    assert r['automatically_apply'] is False


@pytest.mark.parametrize('key,value', [('frame', 'camera'), ('units', 'm'), ('calibration_id', '')])
def test_rejects_unknown_coordinate_context(key, value):
    data = observations(); data[key] = value
    with pytest.raises(ValueError):
        compare_observations(RECIPE, data)


def test_rejects_mixed_tools_and_duplicate_samples():
    data = observations(); data['samples'][0]['tool_id'] = 2
    with pytest.raises(ValueError, match='mixed'):
        compare_observations(RECIPE, data)
    data = observations(); data['samples'].append(copy.deepcopy(data['samples'][0]))
    with pytest.raises(ValueError, match='unique'):
        compare_observations(RECIPE, data)


def test_rejects_unmeasured_empty_and_nonfinite_observations():
    for change in ('unconfirmed', 'empty', 'nonfinite'):
        data = observations()
        if change == 'unconfirmed': data['samples'][0]['alignment_confirmed'] = False
        if change == 'empty': data['samples'] = []
        if change == 'nonfinite': data['samples'][0]['aligned_tcp_base_xy_mm'][0] = float('nan')
        with pytest.raises(ValueError):
            compare_observations(RECIPE, data)


def test_report_does_not_modify_recipe_or_observations():
    recipe, data = copy.deepcopy(RECIPE), observations()
    before = copy.deepcopy(data)
    compare_observations(recipe, data)
    assert recipe == RECIPE and data == before
