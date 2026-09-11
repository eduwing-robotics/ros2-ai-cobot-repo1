from copy import deepcopy
from hashlib import sha256

import pytest

from fixed_pose_reference import entries_digest, fit_offsets, validate_fixed_reference
from opencv_inspectors import check_auxiliary_pose


def sample(key, **offsets):
    return dict(source_sha256=key, raw_offsets_mm=offsets)


def test_frozen_reference_keeps_real_shared_motion_and_slot_independence():
    samples = [sample('a', pm=[.2, -.7], vrm=[-.4, -.6]),
               sample('b', pm=[.4, -.5], vrm=[-.2, -.4])]
    before = deepcopy(samples)
    refs = fit_offsets(samples, ['pm', 'vrm'], 'reference')
    for sid, ref in refs.items():
        def measure(shift):
            center = [ref['offset_mm'][i] + shift[i] for i in (0, 1)]
            return check_auxiliary_pose(
                dict(confidence=.9, evidence=dict(present=True, center_px=center,
                     expected_center_px=[0, 0], long_axis_angle_deg_undirected=0)),
                0, (100, 100), (100, 100),
                slot_reference_offset_mm=ref['offset_mm']).to_dict()
        assert measure([0, 0])['status'] == 'PASS'
        moved = measure([2, 1])
        assert moved['status'] == 'FAIL'
        assert moved['measured']['offset_mm'] == pytest.approx([2, 1])
        assert moved['authority'] == 'ADVISORY_ONLY'
    assert samples == before


def test_duplicate_insufficient_and_nonfinite_samples_rejected():
    for samples in ([sample('a', pm=[0, 0])]*2,
                    [sample('a', pm=[0, 0]), sample('b')],
                    [sample('a', pm=[0, 0]), sample('b', pm=[float('nan'), 0])]):
        with pytest.raises(ValueError):
            fit_offsets(samples, ['pm'], 'reference')


def fixture_config(tmp_path):
    dependency = tmp_path/'dependency'; dependency.write_bytes(b'unchanged')
    config = dict(component_bias_diagnostic_only=True, auxiliary_pose_use_active_slot_centers=True,
                  board_layout=str(dependency), physical_board=str(dependency),
                  provider_crop_config=str(dependency))
    samples = [sample('a', pm=[.1, .2]), sample('b', pm=[.3, .4])]
    refs = fit_offsets(samples, ['pm'], 'reference')
    config['auxiliary_pose_slot_reference_offsets_mm'] = refs
    config['fixed_pose_reference'] = dict(calibration_id='reference', samples=samples,
        entries_sha256=entries_digest(refs), dependencies={str(dependency):sha256(b'unchanged').hexdigest()})
    return config, dependency


@pytest.mark.parametrize('failure', ['model', 'bias', 'offset', 'coverage', 'samples', 'missing'])
def test_changed_reference_abstains_instead_of_using_stale_calibration(tmp_path, failure):
    c, dependency = fixture_config(tmp_path)
    assert validate_fixed_reference(c, tmp_path, ['pm'], dependency)['status'] == 'AVAILABLE'
    if failure == 'model': dependency.write_bytes(b'new weights')
    if failure == 'bias': c['component_bias_diagnostic_only'] = False
    if failure == 'offset': c['auxiliary_pose_slot_reference_offsets_mm']['pm']['offset_mm'][0] += 1
    if failure == 'coverage': c['auxiliary_pose_slot_reference_offsets_mm'] = {}
    if failure == 'samples': c['fixed_pose_reference']['samples'][0]['raw_offsets_mm']['pm'] = [9, 9]
    if failure == 'missing': dependency.unlink()
    result = validate_fixed_reference(c, tmp_path, ['pm'], dependency)
    assert result['status'] == 'UNAVAILABLE'
    assert result['authority'] == 'INVALID'


def test_missing_detector_stays_unknown_and_rotation_is_not_calibrated_away():
    assert check_auxiliary_pose(None, 0, (100, 100), (100, 100)).status == 'UNKNOWN'
    q = check_auxiliary_pose(dict(confidence=.9, evidence=dict(present=True,
        center_px=[.2, .3], expected_center_px=[0, 0], long_axis_angle_deg_undirected=15)),
        0, (100, 100), (100, 100), slot_reference_offset_mm=(.2, .3))
    assert q.status == 'FAIL' and q.measured['axis_angle_error_deg'] == 15


def test_legacy_config_is_not_implicitly_recalibrated(tmp_path):
    assert validate_fixed_reference({}, tmp_path, ['pm'], tmp_path/'missing') is None


def test_default_runtime_profile_has_complete_valid_frozen_reference():
    import json
    import main
    config = json.loads(main.DEFAULT_CONFIG.read_text())
    entries = config['auxiliary_pose_slot_reference_offsets_mm']
    assert len(entries) == 25
    health = validate_fixed_reference(config, main.PROJECT_DIR, entries,
        main.PROJECT_DIR/'vision_assembly/segmentation/models/s22_parts_seg_candidate.pt')
    assert health['status'] == 'AVAILABLE'
    assert health['authority'] == 'ADVISORY_ONLY'


def test_archive_counterfactual_keeps_unavailable_pose_and_source_pixels():
    from audit_fixed_pose_reference import recheck_slots
    slot = dict(slot_id='pm', stages=dict(pose=dict(status='UNKNOWN', measured={})))
    original = deepcopy(slot)
    assert recheck_slots([slot], {'pm': dict(offset_mm=[0, 0], calibration_id='fixed')},
                         {'pm': [50, 60]}) == [original]
    assert slot == original
