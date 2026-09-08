from types import SimpleNamespace as NS
import numpy as np
import pytest
from fr5_process_sequences.continuous_transfer import transfer_group,execute_transfer


def points():
    return [NS(label=label,linear=False,tcp=(0,0,350,180,0,i),slot_code='IND-01',
               reference_joints=(i,)*6,target_joints=(i+1,)*6,speed_percent=40)
            for i,label in enumerate(['tray_after_mid_travel','tray_after_mid_travel','tray_after_travel'])]


def rig(fail=False):
    calls=[];state=NS(robot_mode=0,tool_num=1,work_num=0)
    def send(cmd,code):
        calls.append(cmd)
        if fail and cmd.startswith('MoveJ(JNT2'):raise RuntimeError('transport failed')
    robot=NS(assert_continuous_driver=lambda:None,assert_ready=lambda:None,_service=send,stop_motion=lambda:calls.append('STOP'))
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
