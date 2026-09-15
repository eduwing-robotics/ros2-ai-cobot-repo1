from copy import deepcopy
import pytest
from smd01_small_lip import RULE, small_lip_candidate, independent_lip_candidate, raw_y_outside_deadband


def sample():
    return dict(slot_id='smd_capacitor_01', component_type='SMD Capacitor', stages={
        'presence': dict(authority='ADVISORY_ONLY', predicted_state='PRESENT', confidence=.99),
        'pose': dict(authority='ADVISORY_ONLY', confidence=.38, measured={'raw_offset_mm': [1.4, -.90]}),
        'surface': dict(authority='ADVISORY_ONLY', score=.22)})


def test_detect_and_preserve():
    row = sample()
    old = deepcopy(row)
    assert small_lip_candidate(row)
    assert row == old
    row['stages']['pose']['measured']['raw_offset_mm'][1] = .96
    assert small_lip_candidate(row)


@pytest.mark.parametrize('y', [0, RULE['raw_y_min_mm'], RULE['raw_y_max_mm'], float('nan'), float('inf')])
def test_normal_and_invalid(y):
    row = sample()
    row['stages']['pose']['measured']['raw_offset_mm'][1] = y
    assert not small_lip_candidate(row)


@pytest.mark.parametrize('provider', ['presence', 'pose', 'surface'])
def test_unavailable(provider):
    row = sample()
    row['stages'][provider]['authority'] = 'UNAVAILABLE'
    assert not small_lip_candidate(row)


def test_corroboration_and_scope():
    for key, value in [('slot_id', 'smd_capacitor_02'), ('component_type', 'HBM')]:
        row = sample()
        row[key] = value
        assert not small_lip_candidate(row)
    for provider, key, value in [('presence', 'predicted_state', 'EMPTY'),
                                  ('presence', 'confidence', .89), ('pose', 'confidence', .19),
                                  ('surface', 'score', .09)]:
        row = sample()
        row['stages'][provider][key] = value
        assert not small_lip_candidate(row)
    assert not small_lip_candidate({})


def test_independent_fallback_is_guarded():
    row = sample()
    row['stages']['pose'] = dict(reason='YOLO_AUXILIARY_CANDIDATE_MISSING')
    row['smd01_outline_evidence'] = dict(valid=True, alignment_valid=True, raw_y_mm=-1.5)
    original = deepcopy(row)
    assert independent_lip_candidate(row)
    assert original == row
    for field, value in [('valid',False), ('alignment_valid',False), ('raw_y_mm',0), ('raw_y_mm',float('nan'))]:
        altered = deepcopy(row)
        altered['smd01_outline_evidence'][field] = value
        assert not independent_lip_candidate(altered)
    row['stages']['pose']['reason'] = 'AUXILIARY_POSE_WITHIN_LIMIT'
    assert not independent_lip_candidate(row)


def test_restored_normal_subpixel_excess_abstains_but_lip_is_kept():
    assert not raw_y_outside_deadband(-0.7653384336739731, 1.0)
    assert raw_y_outside_deadband(-1.2699285088368877, 1.0)
    assert RULE['boundary_deadband_px'] == 0.0
    assert raw_y_outside_deadband(-0.7653384336739731)
    assert not raw_y_outside_deadband(float('nan'))


def test_guard_applies_to_both_sides():
    pixel = RULE['canonical_y_mm_per_px']
    assert not raw_y_outside_deadband(RULE['raw_y_min_mm'] - 0.5 * pixel, 1.0)
    assert not raw_y_outside_deadband(RULE['raw_y_max_mm'] + 0.5 * pixel, 1.0)
    assert raw_y_outside_deadband(RULE['raw_y_min_mm'] - 1.5 * pixel, 1.0)
    assert raw_y_outside_deadband(RULE['raw_y_max_mm'] + 1.5 * pixel, 1.0)


@pytest.mark.parametrize('score', [.115, .116, .129, .139999])
def test_weak_surface_does_not_nominate_lip(score):
    row = sample()
    row['stages']['surface']['score'] = score
    original = deepcopy(row)
    assert not small_lip_candidate(row)
    assert row == original


def test_subtle_archived_defect_keeps_candidate():
    row = sample()
    row['stages']['pose']['measured']['raw_offset_mm'][1] = -.767
    row['stages']['surface']['score'] = .218
    assert small_lip_candidate(row)
    assert RULE['boundary_deadband_px'] == 0.0
