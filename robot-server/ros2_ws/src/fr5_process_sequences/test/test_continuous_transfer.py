from types import SimpleNamespace as NS
import numpy as np
import pytest
from fr5_process_sequences.continuous_transfer import transfer_group,execute_transfer


def points():
    return [NS(label=label,linear=False,tcp=(0,0,350,180,0,i),slot_code='IND-01',
               reference_joints=(i,)*6,target_joints=(i+1,)*6,speed_percent=40)
            for i,label in enumerate(['tray_after_mid_travel','tray_after_mid_travel','tray_after_travel'])]


def rig(fail=False):
    calls=[];state=NS(robot_mode=0,tool_num=1,work_num=0,robot_motion_done=1)
    def send(cmd,code):
        calls.append(cmd)
        if fail and cmd.startswith('MoveJ(JNT2'):raise RuntimeError('transport failed')
    robot=NS(assert_continuous_driver=lambda:None,assert_ready=lambda:None,assert_motion_permitted=lambda:None,_service=send,stop_motion=lambda:calls.append('STOP'))
    backend=NS(control=NS(enabled=False),_assert_not_paused=lambda:None,_recovery_required=False)
    node=NS(backend=backend,robot=robot,spin_state=lambda:state,state_tcp=lambda s:[0,0,350,180,0,0],
        state_joints=lambda s:np.zeros(6),service=lambda cmd:calls.append(cmd),
        wait_pose=lambda tcp,joints:(calls.append('WAIT_FINAL') or list(tcp)))
    return node,calls


def test_group_stops_before_descent_and_inspection():
    group=points();end=NS(linear=True,label='tray_after_inspect',tcp=(0,0,337,180,0,0))
    assert transfer_group(group+[end],0)==group
    group[1].tcp=(0,0,340,180,0,0)
    assert transfer_group(group,0)==[]


def test_queues_all_points_before_only_endpoint_wait():
    node,calls=rig();actual,accepted=execute_transfer(node,points(),lambda:None)
    assert len(accepted)==3 and actual[2]==350
    assert calls[-1]=='WAIT_FINAL' and calls.count('WAIT_FINAL')==1
    assert [c for c in calls if c.startswith('MoveJ')]==[
        'MoveJ(JNT1,40,1,0,0,0,0,0,50)',
        'MoveJ(JNT2,40,1,0,0,0,0,0,50)',
        'MoveJ(JNT3,40,1,0,0,0,0,0,0)']
    assert all(c.startswith('JNTPoint') for c in calls[:3])


def test_partial_queue_failure_stops_without_replay():
    node,calls=rig(True)
    with pytest.raises(RuntimeError):execute_transfer(node,points(),lambda:None)
    assert calls[-1]=='STOP' and node.backend._recovery_required
    assert not any(c.startswith('MoveJ(JNT3') for c in calls)


def test_retained_pause_combination_is_rejected_before_commands():
    node,calls=rig();node.backend.control.enabled=True
    with pytest.raises(Exception,match='cannot be combined'):execute_transfer(node,points(),lambda:None)
    assert calls==[]


def test_broken_reference_chain_rejected_before_commands():
    node,calls=rig();group=points();group[1].reference_joints=(99,)*6
    with pytest.raises(Exception,match='reference chain'):execute_transfer(node,group,lambda:None)
    assert calls==[]


def test_old_driver_is_rejected_without_motion():
    node,calls=rig()
    def reject():raise RuntimeError('old driver')
    node.robot.assert_continuous_driver=reject
    with pytest.raises(RuntimeError,match='old driver'):execute_transfer(node,points(),lambda:None)
    assert calls==[]


@pytest.fixture
def fast_clock(monkeypatch):
    clock=[0.]
    def now():
        clock[0]+=.05
        return clock[0]
    monkeypatch.setattr('fr5_process_sequences.continuous_transfer.time.monotonic',now)


def test_lift_early_completion_waits_without_lowering_clearance(fast_clock):
    node,calls=rig();heights=iter([349.5766296386719,349.7,349.79,349.99])
    seen=[]
    def tcp(state):
        z=next(heights,350.)
        seen.append(z)
        if z<349.8:assert not calls
        return [0,0,z,180,0,0]
    node.state_tcp=tcp
    execute_transfer(node,points(),lambda:None)
    assert seen[:3]==[349.5766296386719,349.7,349.79]
    assert node.last_transfer_start_verification['z_mm']>=349.8
    assert calls[-1]=='WAIT_FINAL'


def test_height_never_settles_no_point_or_move_commands(fast_clock):
    node,calls=rig();node.state_tcp=lambda s:[0,0,349.57,180,0,0]
    with pytest.raises(Exception,match='did not settle'):execute_transfer(node,points(),lambda:None)
    assert calls==[]


def test_settle_needs_stationary_feedback(fast_clock):
    node,calls=rig();node.spin_state=lambda:NS(robot_mode=0,tool_num=1,work_num=0,robot_motion_done=0)
    with pytest.raises(Exception,match='did not settle'):execute_transfer(node,points(),lambda:None)
    assert calls==[]


def test_stop_request_during_settling_prevents_all_commands(fast_clock):
    node,calls=rig()
    def cancelled():raise RuntimeError('operator cancelled')
    with pytest.raises(RuntimeError,match='operator cancelled'):execute_transfer(node,points(),cancelled)
    assert calls==[]


def test_higher_transfer_requires_its_actual_start_height(fast_clock):
    node,calls=rig();group=points()
    for w in group:w.tcp=(0,0,400,180,0,0)
    with pytest.raises(Exception,match='did not settle'):execute_transfer(node,group,lambda:None)
    assert calls==[]


def test_every_buffered_target_is_published_before_its_dispatch(fast_clock):
    node,calls=rig();node.phase='02_CONTINUOUS_TRANSFER'
    node.publish_motion_target=lambda w,phase:calls.append(('ghost',phase,w.target_joints))
    execute_transfer(node,points(),lambda:None)
    targets=[c for c in calls if isinstance(c,tuple)]
    assert len(targets)==3 and len({c[1] for c in targets})==3
    for i,target in enumerate(targets,1):
        index=calls.index(target)
        assert calls[index+1].startswith(f'MoveJ(JNT{i},')
        assert target[2]==points()[i-1].target_joints


def test_visualization_failure_does_not_stop_buffered_motion(fast_clock):
    node,calls=rig();node.phase='transfer'
    node.publish_motion_target=lambda *args:(_ for _ in ()).throw(RuntimeError('network'))
    execute_transfer(node,points(),lambda:None)
    assert calls[-1]=='WAIT_FINAL' and 'STOP' not in calls


def test_other_transfers_keep_original_blending_and_final_stop(fast_clock):
    node,calls=rig();group=points()
    for w,label in zip(group,['place_combined_xy_abc_midpoint','place_combined_xy_abc_midpoint','place_combined_xy_abc']):
        w.label=label
    _,accepted=execute_transfer(node,group,lambda:None)
    assert [a['blend_ms'] for a in accepted]==[50,50,0]
    assert calls[-1]=='WAIT_FINAL'
