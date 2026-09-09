from copy import deepcopy
import pytest
from vrm_context_pose import context_pose_codes


def sample():
    return dict(component_type='VRM',vrm_presence_context=dict(available=True,authority='ADVISORY_ONLY',present_probability=.993),
        stages=dict(presence=dict(status='UNKNOWN'),
        pose=dict(authority='ADVISORY_ONLY',confidence=.245,
                  limits=dict(expected_axis_angle_deg=90,angle_tolerance_deg=3,position_tolerance_mm=.75),
                  measured=dict(center_px=[84.66,414.72],axis_angle_deg=97.76,axis_angle_checked=True,raw_offset_mm=[-1.18,-.80])),
        vrm_boundary=dict(authority='ADVISORY_ONLY',measured=dict(confidence=.973,axes=[7.25,4.13],position=[86.21,413.80,158]))))


def test_conflict_does_not_block_corroborated_geometry_or_mutate():
    row=sample(); before=deepcopy(row)
    assert context_pose_codes(row)==['DIR?','POSE?']
    assert row==before


@pytest.mark.parametrize('probability',[.1,.94,float('nan'),1.1])
def test_weak_or_empty_context(probability):
    row=sample();row['vrm_presence_context']['present_probability']=probability
    assert context_pose_codes(row)==[]


def test_explicit_missing_abstains():
    row=sample();row['stages']['presence']['status']='FAIL'
    assert context_pose_codes(row)==[]


def test_advisory_correct_is_not_orientation_veto():
    row=sample()
    row['stages']['presence']={'status':'PASS','authority':'ADVISORY_ONLY','predicted_state':'CORRECT'}
    before=deepcopy(row)
    assert context_pose_codes(row)==['DIR?','POSE?']
    assert row==before
    row['stages']['pose']['measured']['axis_angle_deg']=90
    assert context_pose_codes(row)==[]


@pytest.mark.parametrize('authority,prediction',[('INVALID','CORRECT'),('AUTHORITATIVE','CORRECT'),('ADVISORY_ONLY','EMPTY')])
def test_invalid_or_other_pass_does_not_enable_route(authority,prediction):
    row=sample()
    row['stages']['presence']={'status':'PASS','authority':authority,'predicted_state':prediction}
    assert context_pose_codes(row)==[]


def test_disagreement_normal_and_missing_data():
    for angle in (90,80):
        row=sample();row['stages']['pose']['measured']['axis_angle_deg']=angle
        assert context_pose_codes(row)==[]
    row=sample();row['stages']['vrm_boundary']['measured']['position']=[100,450,158]
    assert context_pose_codes(row)==[]
    assert context_pose_codes({})==[]


def test_corrected_offset_does_not_create_position_vote():
    row=sample(); row['stages']['pose']['measured']['raw_offset_mm']=[.1,.2]
    row['stages']['pose']['measured']['position_error_mm']=99
    assert context_pose_codes(row)==['DIR?']


@pytest.mark.parametrize('boundary,aux,expected',[
    (.973,.245,True),(.930,.407,True),(.930,.245,False),
    (.899,.99,False),(.99,.199,False),(1.1,.9,False),(.93,float('nan'),False)])
def test_confidence_pair_not_single_score_relaxation(boundary,aux,expected):
    row=sample()
    row['stages']['pose']['confidence']=aux
    row['stages']['vrm_boundary']['measured']['confidence']=boundary
    assert bool(context_pose_codes(row)) is expected
