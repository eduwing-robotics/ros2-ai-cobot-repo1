from copy import deepcopy
import json

import pytest

from inspection_api import DEMO_CONFIRMATION_POLICY, Store, public_result


def raw_result():
    return dict(decision='FAIL', operational_decision=dict(
        mode='PROVISIONAL_BINARY_V1', validated=False, status='FAIL',
        reasons=['DEFECT_CANDIDATE']),
        summary=dict(confirmed_defect_count=0, advisory_candidate_count=1), defects=[],
        slots=[dict(slot_id=str(i), slot_code=f'S-{i}', decision='UNKNOWN') for i in range(25)],
        findings=[dict(slot_id='2', slot_code='S-2', finding_id='inspection-S-2',
                       primary_defect_code='POSITION_ERROR', authority='ADVISORY_ONLY',
                       confirmed_defect=False, decision='UNKNOWN')])


def test_demo_confirmation_is_consistent_explicit_and_non_mutating():
    raw = raw_result()
    original = deepcopy(raw)
    result = public_result(raw, demo_confirmation=True)
    assert result['decision'] == 'FAIL'
    assert result['summary']['confirmed_defect_count'] == len(result['defects']) == 1
    assert result['summary']['advisory_candidate_count'] == 0
    assert result['summary']['slot_decisions'] == {'PASS': 24, 'FAIL': 1}
    f = result['findings'][0]
    assert f['authority'] == 'AUTHORITATIVE' and f['confirmed_defect'] is True
    assert f['source_authority'] == 'ADVISORY_ONLY' and f['source_confirmed_defect'] is False
    assert f['decision_basis'] == DEMO_CONFIRMATION_POLICY
    assert result['defects'] == [dict(slot_code='S-2', defect_type='POSITION_ERROR', finding_id='inspection-S-2')]
    assert result['confirmation_policy']['model_validated'] is False
    assert result['operational_decision']['validated'] is False
    assert raw == original
    assert public_result(result, demo_confirmation=True) == result


def test_demo_requires_explicit_enablement():
    result = public_result(raw_result())
    assert result['defects'] == []
    assert result['findings'][0]['authority'] == 'ADVISORY_ONLY'


@pytest.mark.parametrize('reason', ['PROVIDER_UNAVAILABLE', 'REGISTRATION_INVALID',
                                   'CAPTURE_QUALITY_BLOCKED', 'PRESENCE_NOT_CONFIRMED'])
def test_errors_are_never_invented_as_confirmed_defects(reason):
    raw = raw_result()
    raw['operational_decision']['reasons'].append(reason)
    result = public_result(raw, demo_confirmation=True)
    assert result['defects'] == []
    assert result['findings'][0]['confirmed_defect'] is False


@pytest.mark.parametrize('change', ['missing_slot', 'mismatched_slot', 'empty_findings', 'missing_id'])
def test_incomplete_candidate_records_are_not_promoted(change):
    raw = raw_result()
    if change == 'missing_slot': raw['slots'].pop()
    if change == 'mismatched_slot': raw['findings'][0]['slot_code'] = 'OTHER'
    if change == 'empty_findings': raw['findings'] = []
    if change == 'missing_id': raw['findings'][0].pop('finding_id')
    assert public_result(raw, demo_confirmation=True)['defects'] == []


def test_store_read_confirms_demo_without_rewriting_saved_evidence(tmp_path):
    store = Store(tmp_path, lambda: False, None)
    store.demo_confirmation = True
    record = dict(inspection_id='example', status='COMPLETED', result=raw_result(), image={'ready': False})
    store.save(record)
    store.records['example'] = deepcopy(record)
    path = tmp_path/'example'/'state.json'
    before = path.read_bytes()
    result = store.get('example')['result']
    assert result['summary']['confirmed_defect_count'] == 1
    assert path.read_bytes() == before
    assert json.loads(before)['result']['findings'][0]['authority'] == 'ADVISORY_ONLY'
