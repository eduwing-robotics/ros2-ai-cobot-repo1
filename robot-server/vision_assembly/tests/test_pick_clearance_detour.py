"""Common high empty-pick fallback; contact/held routes and limits stay exact."""
from dataclasses import replace
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import execute_full_fixed_cycle as executor
from full_cycle_motion import MotionWaypoint, MotionPlanError, empty_pick_clearance_detour
from tray_home_gate import HOME

START=(72.519761,-544.091961,350.,-180.,0.,-178.889706)
TARGET=(-590.769,-17.126,350.,-180.,0.,91.797)
INITIAL=(86.680573,-84.446198,80.000237,-85.554039,-90.,-4.429717)
END=(-8.482231,-78.505997,73.109695,-84.603691,-90.,-10.279228)
VIA=(-4.688828,-86.854538,82.605637,-85.751099,-90.,-4.688828)
SPEEDS=dict(travel=25,combined_rotation=25,vertical=10,high_transfer=40,clearance_lift=30)

class IK:
    def __init__(self, end=END, via=VIA):self.end=end;self.via=via;self.queries=[]
    def response_values(self, result, count, label):return np.array(result,dtype=float)
    def service(self, command):
        self.queries.append(command)
        if command=='GetJointSoftLimitDeg(1)':return [-175.]*6+[175.]*6
        if command=='GetSafetyStopState()':return [0.,0.]
        assert command.startswith('GetInverseKinRef(')
        values=list(map(float,command.split('(',1)[1][:-1].split(',')))
        x,y=values[1:3]
        if abs(x-START[0])<1e-5:return INITIAL
        if abs(x-TARGET[0])<1e-5:return self.end
        assert abs(x-HOME[0])<1e-5 and abs(y-HOME[1])<1e-5
        return self.via


def route(slot='HBM-02'):
    return [(slot,MotionWaypoint('pre_pick_safe_vertical',START,True)),
            (slot,MotionWaypoint('pick_combined_xy_abc',TARGET,False))]


@pytest.mark.parametrize('slot',['GPU-01','HBM-02','HBM-08','PM-01','VRM-01'])
def test_common_policy_preserves_endpoints_speed_and_limits(slot):
    original=route(slot);node=IK()
    planned,summary=executor.preflight_route(node,original,np.array(INITIAL),SPEEDS)
    assert [w.label for w in planned]==['pre_pick_safe_vertical','pick_via_trayhome_high','pick_combined_xy_abc']
    assert planned[-1].tcp==TARGET and planned[-1].target_joints==END
    assert planned[0].tcp==START
    assert planned[1].tcp==(*HOME[:2],350.,*HOME[3:])
    assert planned[1].speed_percent==planned[-1].speed_percent==40
    assert planned[-1].reference_joints==planned[1].target_joints
    assert summary['maximum_joint_step_deg']==pytest.approx(91.369401)
    assert len(summary['route_adaptations'])==1
    assert original==route(slot)


def test_successful_direct_path_unchanged_and_no_detour_query():
    node=IK(end=(0.,*END[1:]))
    planned,summary=executor.preflight_route(node,route(),np.array(INITIAL),SPEEDS)
    assert len(planned)==2 and summary['route_adaptations']==[]
    assert len([c for c in node.queries if c.startswith('GetInverseKinRef')])==2


@pytest.mark.parametrize('change', ['held','midpoint','contact','low','tilt','unwind','height'])
def test_special_rotation_contact_and_held_transfers_are_never_rewritten(change):
    before,target=[w for _,w in route()]
    if change=='held':before=replace(before,label='carry_safe_vertical')
    if change=='midpoint':before=replace(before,label='pick_combined_xy_abc_midpoint',linear=False)
    if change=='contact':target=replace(target,label='pick_final_50mm_vertical',linear=True)
    if change=='low':before=replace(before,tcp=(*START[:2],349.,*START[3:]));target=replace(target,tcp=(*TARGET[:2],349.,*TARGET[3:]))
    if change=='tilt':target=replace(target,tcp=(*TARGET[:3],0.,0.,90.))
    if change=='unwind':target=replace(target,tcp=(*TARGET[:5],0.))
    if change=='height':target=replace(target,tcp=(*TARGET[:2],400.,*TARGET[3:]))
    assert empty_pick_clearance_detour(before,target,HOME) is None


def test_alternative_cannot_bypass_joint_step_gate():
    with pytest.raises(MotionPlanError,match='alternative rejected'):
        executor.preflight_route(IK(via=(-20.,*VIA[1:])),route(),np.array(INITIAL),SPEEDS)


def test_alternative_cannot_bypass_soft_limits():
    with pytest.raises(MotionPlanError,match='soft-limit'):
        executor.preflight_route(IK(via=(170.,*VIA[1:])),route(),np.array(INITIAL),SPEEDS)


def test_rejected_held_path_is_not_automatically_replanned():
    original=route();original[0]=(original[0][0],replace(original[0][1],label='carry_safe_vertical'))
    with pytest.raises(MotionPlanError,match='maximum is 95'):
        executor.preflight_route(IK(),original,np.array(INITIAL),SPEEDS)


def test_detour_is_a_stop_point_not_an_unverified_blended_corner():
    from fr5_process_sequences.continuous_transfer import transfer_group
    planned,_=executor.preflight_route(IK(),route(),np.array(INITIAL),SPEEDS)
    assert transfer_group(planned,1)==[]


def test_detour_does_not_exempt_j6_operational_bounds():
    with pytest.raises(MotionPlanError,match='alternative rejected'):
        executor.preflight_route(IK(via=(*VIA[:5],179.)),route(),np.array(INITIAL),SPEEDS)
