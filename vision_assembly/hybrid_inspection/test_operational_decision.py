from operational_decision import decide
from copy import deepcopy

import pytest


def check(**overrides):
    args=dict(slots=[{'slot_id':str(i),'stages':{'presence':{'predicted_state':'PRESENT'}}} for i in range(25)], candidates=[], quality={'blocks_decision':False}, alignment_valid=True, health={'unavailable':[]},validated_status='UNKNOWN')
    args.update(overrides)
    return decide(**args)


def test_provisional_pass_does_not_claim_validation():
    r=check()
    assert r['status']=='PASS' and r['validated'] is False


def test_candidates_and_quality_and_errors_reject():
    assert check(candidates=[{'slot_id':'2'}])['status']=='FAIL'
    assert check(quality={'blocks_decision':True})['status']=='FAIL'
    assert check(alignment_valid=False)['status']=='FAIL'
    assert check(health={'unavailable':[{'stage':'surface'}]})['status']=='FAIL'
    assert check(slots=[])['status']=='FAIL'
    assert check(validated_status='FAIL')['status']=='FAIL'


def test_experimental_seating_exception_is_exact():
    row={'stage':'seating','reason':'VRM_SEATING_CANDIDATE_NOT_RUNTIME_ENABLED'}
    assert check(health={'unavailable':[row]})['status']=='PASS'
    assert check(health={'unavailable':[dict(row,reason='RUNTIME_ERROR')]})['status']=='FAIL'


def uncertain_position_slots():
    return [dict(slot_id=str(i), status='UNKNOWN', stages={
        'presence': {'predicted_state': 'PRESENT'},
        'pose': {'status': 'UNKNOWN', 'reason': 'POSITION_UNCERTAIN'},
    }) for i in range(25)]


def test_position_uncertainty_alone_passes_without_rewriting_evidence():
    slots = uncertain_position_slots()
    original = deepcopy(slots)
    result = check(slots=slots)
    assert result['status'] == 'PASS'
    assert result['validated'] is False
    assert slots == original


@pytest.mark.parametrize('overrides,reason', [
    ({'candidates': [{'slot_id': '2', 'stage': 'pose'}]}, 'DEFECT_CANDIDATE'),
    ({'candidates': [{'slot_id': '2', 'stage': 'pins'}]}, 'DEFECT_CANDIDATE'),
    ({'candidates': [{'slot_id': '2', 'stage': 'surface'}]}, 'DEFECT_CANDIDATE'),
    ({'candidates': [{'slot_id': '2', 'stage': 'orientation'}]}, 'DEFECT_CANDIDATE'),
    ({'health': {'unavailable': [{'stage': 'pose', 'reason': 'RUNTIME_ERROR'}]}}, 'PROVIDER_UNAVAILABLE'),
    ({'alignment_valid': False}, 'REGISTRATION_INVALID'),
    ({'quality': {'blocks_decision': True}}, 'CAPTURE_QUALITY_BLOCKED'),
    ({'validated_status': 'FAIL'}, 'VALIDATED_FAIL'),
])
def test_position_uncertainty_does_not_override_rejection(overrides, reason):
    result = check(slots=uncertain_position_slots(), **overrides)
    assert result['status'] == 'FAIL'
    assert reason in result['reasons']


def test_position_uncertainty_does_not_waive_missing_presence():
    slots = uncertain_position_slots()
    slots[0]['stages']['presence']['predicted_state'] = 'UNKNOWN'
    result = check(slots=slots)
    assert result['status'] == 'FAIL'
    assert 'PRESENCE_NOT_CONFIRMED' in result['reasons']
