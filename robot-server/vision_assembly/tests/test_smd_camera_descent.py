from dataclasses import replace
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cycle_camera_stage import coalesce_smd_camera_descent
from execute_full_fixed_cycle import PreflightWaypoint


def planned():
    points=[];reference=(0.,)*6
    for i,z in enumerate([350.,300.,250.,200.,150.,127.862,77.862]):
        joints=(float(i),)*6
        points.append(PreflightWaypoint('SMDView',
            'place_combined_xy_abc' if i==0 else 'place_final_50mm_vertical' if i==6 else 'camera_clearance_vertical',
            (-527.998,-120.961,z,180.,0.,89.999),i>0,10 if i==6 else 30,
            reference,joints,40.))
        reference=joints
    return points


def test_six_validated_descent_segments_execute_as_one_slow_straight_move():
    original=planned();result,evidence=coalesce_smd_camera_descent(original,'SMDView')
    assert len(original)==7 and len(result)==2
    assert result[0]==original[0]
    end=result[-1]
    assert end.linear and end.label=='camera_descent_continuous'
    assert end.tcp==original[-1].tcp and end.target_joints==original[-1].target_joints
    assert end.reference_joints==original[1].reference_joints
    assert end.speed_percent==10
    assert len(evidence['validated_samples'])==6
    assert evidence['motion_commands']==1 and evidence['previous_motion_commands']==6


@pytest.mark.parametrize('mutation',['other_camera','xy','orientation','ascending','nonlinear','joint_jump','contact'])
def test_ineligible_or_unsafe_suffix_is_not_coalesced(mutation):
    original=planned();point='SMDView'
    if mutation=='other_camera':point='TrayHome'
    if mutation=='xy':original[3]=replace(original[3],tcp=(-525.,*original[3].tcp[1:]))
    if mutation=='orientation':original[3]=replace(original[3],tcp=(*original[3].tcp[:5],80.))
    if mutation=='ascending':original[-1]=replace(original[-1],tcp=(*original[-1].tcp[:2],180.,*original[-1].tcp[3:]))
    if mutation=='nonlinear':original[-1]=replace(original[-1],linear=False)
    if mutation=='joint_jump':original[-1]=replace(original[-1],target_joints=(100.,0.,0.,0.,0.,0.))
    if mutation=='contact':original[-1]=replace(original[-1],label='pick_final_50mm_vertical')
    result,evidence=coalesce_smd_camera_descent(original,point)
    assert result==original and evidence is None


def test_executor_sends_exactly_one_slow_descent_movel():
    import numpy as np
    from types import SimpleNamespace as NS
    from execute_full_fixed_cycle import move_preflighted
    updated,_=coalesce_smd_camera_descent(planned(),'SMDView')
    w=updated[-1];commands=[];state=NS(robot_motion_done=1)
    node=NS(spin_state=lambda **kwargs:state,safety_error=lambda s:None,
        state_joints=lambda s:np.array(w.reference_joints),
        service=lambda command,**kwargs:commands.append(command),wait_pose=lambda tcp,joints:tcp)
    move_preflighted(node,w)
    assert len(commands)==2 and commands[1]=='MoveL(JNT1,10,1,0)'
