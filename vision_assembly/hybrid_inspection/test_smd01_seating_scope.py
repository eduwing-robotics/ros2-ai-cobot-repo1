"""A projected outline offset cannot relabel the deferred lip-seating sample."""
from copy import deepcopy

import pytest

from main import build_advisory_candidates


def sample():
    return dict(slot_id='smd_capacitor_01', component_type='SMD Capacitor', stages=dict(
        presence=dict(predicted_state='PRESENT', status='UNKNOWN', confidence=.998,
                      authority='ADVISORY_ONLY', reason='UNVERIFIED_PRESENT_CANDIDATE'),
        orientation=dict(status='UNKNOWN', authority='ADVISORY_ONLY'),
        surface=dict(status='UNKNOWN', authority='ADVISORY_ONLY'),
        pose=dict(status='UNKNOWN', authority='ADVISORY_ONLY',
                  reason='YOLO_AUXILIARY_CANDIDATE_MISSING')),
        smd01_outline_evidence=dict(valid=True, alignment_valid=True,
            authority='ADVISORY_ONLY', reason='CONSENSUS', raw_y_mm=2.051,
            spread_px=.711, minimum_clahe_edge_support=.977))


@pytest.mark.parametrize('projected_offset', [2.051, -1.68, 0.345])
def test_outline_only_offset_does_not_relabel_deferred_seating(projected_offset):
    row = sample()
    row['smd01_outline_evidence']['raw_y_mm'] = projected_offset
    original_stages = deepcopy(row['stages'])
    assert build_advisory_candidates([row]) == []
    assert row['stages'] == original_stages
    assert row['smd01_outline_evidence']['raw_y_mm'] == projected_offset


def test_independent_yolo_position_evidence_is_still_reported():
    row = sample()
    row['stages']['pose'] = dict(status='FAIL', authority='ADVISORY_ONLY',
        confidence=.95, reason='AUXILIARY_POSE_OUTSIDE_LIMIT',
        measured=dict(position_error_mm=2., axis_angle_error_deg=0.,
                      absolute_transverse_offset_mm=2.),
        limits=dict(position_tolerance_mm=.75, angle_tolerance_deg=3.))
    findings = build_advisory_candidates([row])
    assert len(findings) == 1 and 'POSE?' in findings[0]['codes']
    assert findings[0]['confirmed_defect'] is False
