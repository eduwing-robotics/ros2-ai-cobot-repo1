from dataclasses import replace
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from execute_full_fixed_cycle import PreflightWaypoint
from full_cycle_motion import MotionPlanError
from linear_tray_return import coalesce_tray_return
from tray_home_gate import HOME

SPEEDS=dict(travel=25,combined_rotation=25,vertical=10,high_transfer=40)
START=(-623.,-117.,350.,-180.,0.,-10.)

def joints(tcp):return ((tcp[0]+528)*.01,-80.,75.,-85.,-90.,90.-tcp[5])

class Node:
    def __init__(self,branch_jump=False):self.queries=[];self.branch_jump=branch_jump
    def response_values(self,result,count,label):return np.asarray(result)
    def service(self,cmd):
        self.queries.append(cmd)
        if cmd=='GetJointSoftLimitDeg(1)':return [-175.]*6+[175.]*6
        if cmd=='GetSafetyStopState()':return [0.,0.]
        assert cmd.startswith('GetInverseKinRef(')
        v=list(map(float,cmd.split('(',1)[1][:-1].split(',')));q=list(joints(v[1:7]))
        if self.branch_jump and 30<v[6]<40:q[0]=60.
        return q

def planned():
    reference=joints(START)
    result=[PreflightWaypoint('CAP-05','tray_after_raise',START,True,30,reference,reference,50)]
    end=(*HOME[:2],350.,*HOME[3:])
    for i in range(1,4):
        tcp=tuple(START[k]+(end[k]-START[k])*i/3 for k in range(6));q=joints(tcp)
        result.append(PreflightWaypoint('CAP-05','tray_after_mid_travel' if i<3 else 'tray_after_travel',tcp,False,40,reference,q,50))
        reference=q
    result.append(PreflightWaypoint('CAP-05','tray_after_inspect',HOME,True,10,reference,joints(HOME),50))
    return result


def test_entire_return_is_one_movel_with_dense_continuous_branch_checks():
    original=planned();result,evidence=coalesce_tray_return(Node(),original,SPEEDS)
    assert len(result)==3 and len(original)==5
    assert result[0]==original[0] and result[-1]==original[-1]
    move=result[1]
    assert move.linear and move.label=='tray_after_travel'
    assert np.allclose(move.target_joints,original[-2].target_joints)
    assert move.tcp==original[-2].tcp and move.reference_joints==original[0].target_joints
    assert move.speed_percent==40
    assert evidence['motion_commands']==1 and evidence['previous_motion_commands']==3
    assert evidence['endpoint_joint_span_deg']==100
    assert len(evidence['validated_samples'])>=20 and evidence['sample_maximum_joint_step_deg']<=10


@pytest.mark.parametrize('change',['curve','low','tilt','part','inspection'])
def test_unsafe_or_different_path_is_rejected(change):
    data=planned()
    if change=='curve':data[1]=replace(data[1],tcp=(data[1].tcp[0]+2,*data[1].tcp[1:]))
    if change=='low':data[0]=replace(data[0],tcp=(*START[:2],349.,*START[3:]))
    if change=='tilt':data[0]=replace(data[0],tcp=(*START[:3],170.,*START[4:]))
    if change=='part':data[2]=replace(data[2],slot_code='OTHER')
    if change=='inspection':data[-1]=replace(data[-1],label='place_final_50mm_vertical')
    with pytest.raises(MotionPlanError):coalesce_tray_return(Node(),data,SPEEDS)


def test_hidden_ik_branch_jump_on_the_line_is_rejected():
    with pytest.raises(MotionPlanError):coalesce_tray_return(Node(branch_jump=True),planned(),SPEEDS)


def test_existing_one_movel_arrival_stays_one():
    data=planned();original=[data[0],replace(data[-2],linear=True),data[-1]]
    result,evidence=coalesce_tray_return(Node(),original,SPEEDS)
    assert result==original and evidence is None


def test_executor_sends_exactly_one_return_movel():
    from types import SimpleNamespace as NS
    from execute_full_fixed_cycle import move_preflighted
    updated,_=coalesce_tray_return(Node(),planned(),SPEEDS)
    w=updated[1];commands=[];state=NS(robot_motion_done=1)
    def service(command,**kwargs):
        if kwargs.get('state_validator'):kwargs['state_validator'](state)
        commands.append(command)
        return '0'
    node=NS(spin_state=lambda **kwargs:state,safety_error=lambda s:None,
        state_joints=lambda s:np.array(w.reference_joints),service=service,
        wait_pose=lambda tcp,joints:tcp)
    move_preflighted(node,w)
    assert len(commands)==2 and commands[0].startswith('JNTPoint(')
    assert commands[1]=='MoveL(JNT1,40,1,0)'
