from copy import deepcopy
import pytest
from vrm_rotation_geometry import multi_axis_rotation, strong_boundary_rotation


def sample():
    return dict(component_type='VRM',
        vrm_state_evidence=dict(probabilities=dict(EMPTY=.002,CORRECT=.976,ROTATED=.022)),
        stages=dict(vrm_boundary=dict(authority='ADVISORY_ONLY',reason='VRM_BOUNDARY_UNCERTAIN',
            measured=dict(axes=[-9.6375,-7.7318],confidence=.9829,position=[98.0935,205.5917,168])),
            pose=dict(authority='ADVISORY_ONLY',confidence=.3047,
                limits=dict(expected_axis_angle_deg=90),
                measured=dict(axis_angle_checked=True,axis_angle_deg=80.9097,center_px=[98.6257,209.4888]))))


def test_three_axes_without_vote_mutation():
    row=sample();before=deepcopy(row)
    assert multi_axis_rotation(row)
    assert row == before


@pytest.mark.parametrize('axes,actual,expected',[
    ([7,7.5],97.8,False), ([8.53,7.03],98.3,True),
    ([-9.63,-7.73],99.1,False), ([10,7],99,False),
    ([170.37,172.27],260.91,True), ([0,0],90,False),
    ([float('nan'),9],99,False), ([],99,False)])
def test_angle_consensus(axes,actual,expected):
    row=sample();row['stages']['vrm_boundary']['measured']['axes']=axes
    row['stages']['pose']['measured']['axis_angle_deg']=actual
    assert multi_axis_rotation(row) is expected


@pytest.mark.parametrize('value',[.94,1.01,float('nan')])
def test_boundary_confidence(value):
    row=sample();row['stages']['vrm_boundary']['measured']['confidence']=value
    assert not multi_axis_rotation(row)


def test_wrong_object_empty_and_bad_inputs():
    row=sample();row['stages']['pose']['measured']['center_px']=[120,220]
    assert not multi_axis_rotation(row)
    row=sample();row['vrm_state_evidence']['probabilities']=dict(EMPTY=.9,CORRECT=.09,ROTATED=.01)
    assert not multi_axis_rotation(row)
    row=sample();row['vrm_state_evidence']['probabilities']['EMPTY']=.5
    assert not multi_axis_rotation(row)
    row=sample();row['stages']['pose']['measured']['axis_angle_checked']=False
    assert not multi_axis_rotation(row)
    row=sample();row['stages']['pose']['authority']='AUTHORITATIVE'
    assert not multi_axis_rotation(row)
    row=sample();row['stages']['vrm_boundary']=None
    assert not multi_axis_rotation(row)
    assert not multi_axis_rotation({})


def test_runtime_nomination_preserves_unknown_authority():
    from main import build_advisory_candidates, fuse_required_stages
    row=sample();row['slot_id']='vrm_05'
    row['stages']['presence']=dict(status='UNKNOWN',authority='ADVISORY_ONLY')
    row['stages']['orientation']=dict(status='UNKNOWN',authority='ADVISORY_ONLY')
    row['stages']['surface']=dict(status='UNKNOWN',authority='ADVISORY_ONLY')
    row['stages']['pose']['status']='UNKNOWN'
    before=deepcopy(row)
    candidates=build_advisory_candidates([row])
    assert candidates[0]['codes']==['DIR?']
    assert candidates[0]['authority']=='ADVISORY_ONLY'
    assert candidates[0]['confirmed_defect'] is False
    assert row==before
    assert fuse_required_stages(row['stages'])[0]=='UNKNOWN'


def strong_sample():
    row=sample()
    row['vrm_presence_context']=dict(available=True,authority='ADVISORY_ONLY',present_probability=.9966)
    row['stages']['vrm_boundary']['measured']['axes']=[-5.71,-7.33]
    row['stages']['pose']['limits']['angle_tolerance_deg']=3
    row['stages']['pose']['measured']['axis_angle_deg']=88.025
    return row


def test_strong_boundary_not_vetoed_by_weak_auxiliary_angle():
    row=strong_sample();before=deepcopy(row)
    assert strong_boundary_rotation(row)
    assert not multi_axis_rotation(row)
    assert row==before


@pytest.mark.parametrize('axes',[[0,1],[4.99,6],[6,-6],[5,8],[float('nan'),6]])
def test_strong_boundary_normal_or_disagreement(axes):
    row=strong_sample();row['stages']['vrm_boundary']['measured']['axes']=axes
    assert not strong_boundary_rotation(row)


@pytest.mark.parametrize('field,value', [('present_probability',.989),('present_probability',1.1),('present_probability',float('nan')),('available',False),('authority','INVALID')])
def test_context_quality_required(field,value):
    row=strong_sample();row['vrm_presence_context'][field]=value
    assert not strong_boundary_rotation(row)


def test_tolerance_and_empty_probabilities_respected():
    row=strong_sample();row['stages']['pose']['limits']['angle_tolerance_deg']=6
    assert not strong_boundary_rotation(row)
    row=strong_sample();row['vrm_state_evidence']['probabilities']=dict(EMPTY=.9,CORRECT=.09,ROTATED=.01)
    assert not strong_boundary_rotation(row)
    row=strong_sample();row['stages']['vrm_boundary']['measured']['confidence']=.96
    assert not strong_boundary_rotation(row)
    assert not strong_boundary_rotation({})
