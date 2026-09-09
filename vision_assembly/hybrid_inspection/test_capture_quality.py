from copy import deepcopy
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from capture_quality import assess_capture_quality, build_evidence_audit


def fixture():
    rng = np.random.default_rng(42)
    image = rng.integers(30, 190, (512, 512, 3), dtype=np.uint8)
    mask = np.full((512, 512), 255, np.uint8)
    mask[150:350, 150:350] = 0
    return image, mask


def test_original_input_preserved_and_no_gross_issue_is_not_pass():
    image, mask = fixture()
    before, before_mask = image.copy(), mask.copy()
    result = assess_capture_quality(image, image, mask)
    assert result['status'] == 'NO_GROSS_ISSUE_DETECTED'
    assert result['authority'] == 'ADVISORY_ONLY'
    assert result['policy']['validated'] is False and not result['blocks_decision']
    assert result['metrics']['laplacian_ratio_median'] == 1
    np.testing.assert_array_equal(before, image)
    np.testing.assert_array_equal(before_mask, mask)


@pytest.mark.parametrize('mode', ['blur', 'black', 'white', 'flat'])
def test_gross_degradation_recommends_recapture_not_component_fail(mode):
    image, mask = fixture()
    altered = cv2.GaussianBlur(image, (25, 25), 6) if mode == 'blur' else np.full_like(
        image, {'black': 0, 'white': 255, 'flat': 80}[mode])
    result = assess_capture_quality(altered, image, mask)
    assert result['status'] == 'RECAPTURE_RECOMMENDED'
    assert result['blocks_decision'] and result['flags']


def test_component_change_cannot_drive_quality_metrics():
    image, mask = fixture()
    altered = image.copy()
    altered[150:350, 150:350] = 255
    a = assess_capture_quality(image, image, mask)
    b = assess_capture_quality(altered, image, mask)
    assert a['metrics'] == b['metrics'] and b['flags'] == []


def test_moderate_brightness_change_not_automatic_failure():
    image, mask = fixture()
    result = assess_capture_quality((image * 1.15).astype(np.uint8), image, mask)
    assert not result['blocks_decision']


def test_invalid_registration_and_unusable_reference_are_not_pass():
    image, mask = fixture()
    assert assess_capture_quality(image, image, mask, alignment_valid=False)['blocks_decision']
    assert assess_capture_quality(image, np.full_like(image, 80), mask)['status'] == 'NOT_EVALUATED'
    assert assess_capture_quality(image, image, np.zeros_like(mask))['blocks_decision']
    assert assess_capture_quality(image, image, None)['flags'] == ['QUALITY_INPUT_INVALID']


def test_all_stage_audit_keeps_hidden_flags_without_fabricating_findings():
    rows = [{'slot_id': 'hbm_01', 'stages': {
        'presence': {'status': 'FAIL', 'authority': 'ADVISORY_ONLY', 'reason': 'EMPTY'},
        'pose': {'status': 'FAIL', 'authority': 'ADVISORY_ONLY', 'measured': {'x': 1}},
        'orientation': {'status': 'UNKNOWN'}, 'surface': {'status': 'PASS'}}}]
    before = deepcopy(rows)
    result = build_evidence_audit(rows, [{'slot_id': 'hbm_01', 'codes': ['MISSING?']}])
    assert result['raw_fail_count'] == 2 and result['undisplayed_count'] == 1
    assert result['items'][1]['stage'] == 'pose'
    assert result['items'][1]['measured'] == {'x': 1}
    assert result['items'][1]['displayed_as_candidate'] is False
    assert rows == before


def test_missing_display_precedence_and_boundary_audit():
    rows = [{'slot_id': 'vrm_01', 'stages': {
        'pose': {'status': 'FAIL'}, 'vrm_boundary': {'status': 'FAIL'}}}]
    audit = build_evidence_audit(rows, [{'slot_id': 'vrm_01', 'codes': ['MISSING?', 'POSE?', 'RIGHT?']}])
    assert audit['undisplayed_count'] == 2
    assert build_evidence_audit(rows, [{'slot_id': 'vrm_01', 'codes': ['RIGHT?']}])['undisplayed_count'] == 0


def test_missing_provider_is_not_zero_anomaly():
    from capture_quality import build_provider_health
    rows = [{'slot_id': 'ai_gpu', 'stages': {'surface': {
        'status': 'UNKNOWN', 'authority': 'UNAVAILABLE', 'reason': 'PATCHCORE_PROVIDER_ERROR'}}}]
    result = build_provider_health(rows)
    assert result['status'] == 'INCOMPLETE'
    assert result['patchcore_unavailable_slots'] == ['ai_gpu']
    assert result['unavailable_count'] == 1
    yolo = build_provider_health([], yolo_status='UNAVAILABLE', yolo_reason='no cuda')
    assert yolo['status'] == 'INCOMPLETE' and yolo['unavailable_count'] == 1
    assert yolo['unavailable'][0]['stage'] == 'yolo_auxiliary'


def test_invalid_patchcore_outputs_cannot_disappear_as_normal_maps():
    from patchcore_inspector import valid_prediction
    assert valid_prediction(dict(score=0.1, anomaly_map=np.zeros((8, 8))))
    assert not valid_prediction(dict(score=float('nan'), anomaly_map=np.zeros((8, 8))))
    assert not valid_prediction(dict(score=0.1, anomaly_map=np.full((8, 8), float('inf'))))
    assert not valid_prediction(dict(score=0.1, anomaly_map=None))
    assert not valid_prediction(dict(score=0.1, anomaly_map=[]))


def test_quality_and_registration_cannot_promote_board_pass_or_bad_capture_fail():
    from main import fuse_board_result
    quality = dict(blocks_decision=False, flags=[], policy={'validated': False})
    slots = [{'slot_id': f'slot_{index:02d}', 'status': 'PASS'} for index in range(25)]
    assert fuse_board_result(slots, True, 'OK', quality)[0] == 'UNKNOWN'
    quality['policy']['validated'] = True
    assert fuse_board_result(slots, True, 'OK', quality)[0] == 'PASS'
    slots[0]['status'] = 'FAIL'
    assert fuse_board_result(slots, True, 'OK', quality)[0] == 'FAIL'
    quality.update(blocks_decision=True, flags=['GROSS_BLUR_OR_TEXTURE_LOSS'])
    assert fuse_board_result(slots, True, 'OK', quality)[0] == 'UNKNOWN'
    assert fuse_board_result(slots, False, 'BAD_ALIGNMENT', quality)[0] == 'UNKNOWN'
    quality['blocks_decision'] = False
    assert fuse_board_result([], True, 'OK', quality)[0] == 'UNKNOWN'
