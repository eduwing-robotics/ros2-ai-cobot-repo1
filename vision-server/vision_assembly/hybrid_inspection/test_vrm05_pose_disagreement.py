from copy import deepcopy
from vrm05_pose_disagreement import conflicting_pose


def sample():
    return dict(slot_id='vrm_05',component_type='VRM',stages={
        'presence':dict(predicted_state='CORRECT'),
        'vrm_boundary':dict(authority='ADVISORY_ONLY',reason='VRM_BOUNDARY_UNCERTAIN',codes=[],
                            measured=dict(position=[5,5,5],confidence=.97),
                            position_bounds_px=[[4,6]]*3,position_margin_px=[1]*3)})


def test_disagreement_preserves_input():
    row=sample()
    old=deepcopy(row)
    assert conflicting_pose(row)
    assert row==old


def test_scope_and_missing():
    assert not conflicting_pose({})
    row=sample()
    row['slot_id']='vrm_04'
    assert not conflicting_pose(row)


def test_outside_weak_invalid_do_not_veto():
    for value in [8,float('nan')]:
        row=sample()
        row['stages']['vrm_boundary']['measured']['position'][0]=value
        assert not conflicting_pose(row)
    row=sample()
    row['stages']['vrm_boundary']['codes']=['RIGHT?']
    assert not conflicting_pose(row)
    row=sample()
    row['stages']['vrm_boundary']['measured']['confidence']=.5
    assert not conflicting_pose(row)
