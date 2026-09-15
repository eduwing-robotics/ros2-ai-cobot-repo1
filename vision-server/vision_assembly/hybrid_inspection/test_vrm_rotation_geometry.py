from copy import deepcopy
import pytest
from vrm_rotation_geometry import corroborated_rotation


def sample():
    return {'component_type':'VRM','vrm_state_evidence':{'probabilities':{'EMPTY':0.01}},
            'stages':{'vrm_boundary':{'authority':'ADVISORY_ONLY','reason':'VRM_BOUNDARY_UNCERTAIN',
                       'measured':{'axes':[-10.76,-10.10],'confidence':0.97}}}}


def test_rotation_preserves_evidence():
    row=sample(); before=deepcopy(row)
    assert corroborated_rotation(row)
    assert row==before


@pytest.mark.parametrize('axes',[[0,1],[7,7],[10,-10],[10,15],[float('nan'),10],None])
def test_uncertain_or_normal_axes_abstain(axes):
    row=sample(); row['stages']['vrm_boundary']['measured']['axes']=axes
    assert not corroborated_rotation(row)


def test_empty_and_unavailable_abstain():
    row=sample(); row['vrm_state_evidence']['probabilities']['EMPTY']=0.9
    assert not corroborated_rotation(row)


def rotation_split():
    row=sample()
    row['vrm_state_evidence']['probabilities']={'EMPTY':.08605,'CORRECT':.76542,'ROTATED':.14853}
    row['stages']['vrm_boundary']['measured']={'axes':[8.3929,9.5869],'confidence':.9553}
    return row


def test_split_orientation_supports_presence_without_mutating_votes():
    row=rotation_split(); before=deepcopy(row)
    assert corroborated_rotation(row)
    assert row==before


@pytest.mark.parametrize('confidence',[.94,float('nan'),1.1])
def test_split_requires_stronger_boundary(confidence):
    row=rotation_split(); row['stages']['vrm_boundary']['measured']['confidence']=confidence
    assert not corroborated_rotation(row)


def test_split_bad_probability_and_normal_angle_abstain():
    row=rotation_split(); row['vrm_state_evidence']['probabilities']['CORRECT']=.99
    assert not corroborated_rotation(row)
    row=rotation_split(); row['stages']['vrm_boundary']['measured']['axes']=[1,2]
    assert not corroborated_rotation(row)
    row=rotation_split(); row['vrm_state_evidence']['probabilities']['EMPTY']=.11
    assert not corroborated_rotation(row)
    row=sample(); row['stages']['vrm_boundary']['reason']='VRM_BOUNDARY_UNAVAILABLE'
    assert not corroborated_rotation(row)
