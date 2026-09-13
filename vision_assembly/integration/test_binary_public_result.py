"""Operator-facing decisions are binary without rewriting the diagnostic truth."""
from copy import deepcopy
import json

import pytest

from inspection_api import public_result


def fixture(reasons=None):
    reasons = reasons or ['NO_DISPLAYED_DEFECT_CANDIDATE']
    status = 'PASS' if reasons == ['NO_DISPLAYED_DEFECT_CANDIDATE'] else 'FAIL'
    return dict(decision=status, operational_decision=dict(
        mode='PROVISIONAL_BINARY_V1', validated=False, status=status, reasons=reasons),
        validated_decision={'status': 'UNKNOWN'}, diagnostics={'raw_status': 'UNKNOWN'},
        summary={'slot_decisions': {'UNKNOWN': 25}}, findings=[],
        slots=[dict(slot_id=str(i), decision='UNKNOWN', reason='RAW_UNKNOWN',
                    stages={'pose': {'status': 'UNKNOWN'}},
                    measurements={'presence_state': 'UNKNOWN', 'pin_status': 'UNKNOWN',
                                  'position_error_mm': None}) for i in range(25)])


def test_provisional_pass_is_binary_and_original_is_unchanged():
    raw = fixture()
    snapshot = deepcopy(raw)
    view = public_result(raw)
    assert view['decision'] == 'PASS'
    assert view['summary']['slot_decisions'] == {'PASS': 25, 'FAIL': 0}
    assert 'UNKNOWN' not in json.dumps(view)
    assert view['operational_decision']['validated'] is False
    assert raw == snapshot
    assert public_result(view) == view


def test_candidate_rejects_its_slot_without_becoming_confirmed():
    raw = fixture(['DEFECT_CANDIDATE'])
    raw['findings'] = [dict(slot_id='2', decision='UNKNOWN', authority='ADVISORY_ONLY',
                            confirmed_defect=False, measurements={'pin_status': 'UNKNOWN'})]
    view = public_result(raw)
    assert view['decision'] == 'FAIL'
    assert view['summary']['slot_decisions'] == {'PASS': 24, 'FAIL': 1}
    assert view['findings'][0]['decision'] == 'FAIL'
    assert view['findings'][0]['confirmed_defect'] is False
    assert 'UNKNOWN' not in json.dumps(view)


@pytest.mark.parametrize('reason', ['PROVIDER_UNAVAILABLE', 'PRESENCE_NOT_CONFIRMED',
                                   'REGISTRATION_INVALID', 'CAPTURE_QUALITY_BLOCKED', 'VALIDATED_FAIL'])
def test_global_gates_do_not_allow_provisional_slot_pass(reason):
    view = public_result(fixture([reason]))
    assert view['decision'] == 'FAIL'
    assert view['summary']['slot_decisions'] == {'PASS': 0, 'FAIL': 25}


def test_legacy_unknown_fails_closed_without_changing_original():
    raw = {'decision': 'UNKNOWN'}
    assert public_result(raw) == {'decision': 'FAIL', 'reason': 'INSPECTION_INCONCLUSIVE'}
    assert raw['decision'] == 'UNKNOWN'
