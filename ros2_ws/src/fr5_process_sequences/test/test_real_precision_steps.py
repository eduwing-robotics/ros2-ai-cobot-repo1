"""No hardware. Real route generation/preflight, synthetic feedback and vision."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import json
import sys
import time

import numpy as np
import pytest
from fr5_process_sequences.real_precision_steps import PrecisionSteps, single_route, digest
from fr5_process_sequences.real_contract import Action, Event
from fr5_process_sequences.real_backend import RealRobotBackend
from fr5_process_sequences.real_ros_node import OperationJournal
from test_real_backend import backend, JOB

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'vision_assembly/scripts'))
from full_cycle_plan import build_plan
from execute_full_fixed_cycle import build_tcp_route
from tray_home_gate import HOME, add_inspections, check_pick_removal


@pytest.fixture
def plan():
    snapshot=json.loads((ROOT/'vision_assembly/data/fixed_cycle_full_restart_retry2_2026-09-02.json').read_text())
    return build_plan(snapshot, json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text()),
                      json.loads((ROOT/'vision_assembly/config/assembly_slots_r1.json').read_text()))


@pytest.mark.parametrize('slot', ['HBM-01','HBM-07','PM-02','PM-04','GPU-01','CAP-01','CAP-05','IND-02','VRM-05'])
def test_single_routes_preserve_tested_pick_and_home_to_place(plan,slot):
    item=next(i for i in plan['plan'] if i['slot_code']==slot)
    original=add_inspections(build_tcp_route([item],list(HOME),350,resume_after_grasp=False),HOME)
    cut=next(i for i,(_,w) in enumerate(original) if w.label=='tray_after_inspect')
    pick=single_route(item,HOME,350,Action.PICK)
    place=single_route(item,HOME,350,Action.PLACE)
    assert pick==original[:cut+1]
    assert place==original[cut+1:]
    assert pick[-1][1].tcp==HOME
    assert all(s==slot for s,_ in pick+place)
    assert not any('place_' in w.label for _,w in pick)
    assert not any('pick_' in w.label or w.label.endswith('inspect') for _,w in place)
    assert place[-1][1].tcp[2]==pytest.approx(item['place_final_tcp'][2]+100)


class SimExecutor:
    def __init__(self,backend,operation):
        self.backend=backend;self.operation=operation;self.state=backend._robot.sim
        self.waypoint=None;self.phase='';self.last_pose_verification=None
    def spin_state(self,**_):
        self.backend._assert_not_paused();return self.state
    def state_tcp(self,state):return list(state.tcp)
    def state_joints(self,state):return np.zeros(6)
    def safety_error(self,state):return None
    def response_values(self,response,count,label):
        return np.array([float(v) for v in response.split(',')[1:]])
    def service(self,command,**kwargs):
        if command.startswith('GetJointSoft'):return '0,'+','.join(map(str,[-360]*6+[360]*6))
        if command.startswith('GetSafetyStop'):return '0,0,0'
        if command.startswith('GetInverseKin'):return '0,0,0,0,0,0,0'
        if command.startswith(('MoveJ','MoveL')):
            self.backend._robot.log.append(('arm',self.operation.slot_code,self.waypoint.label))
        return '0'
    def wait_pose(self,tcp,joints):
        self.state.tcp=list(tcp);self.last_pose_verification={'tcp':tcp};return list(tcp)
    def gripper(self,position,profile):
        self.backend._assert_not_paused()
        self.backend._robot.log.append(('gripper',position,profile))
        self.state.gripper_position=position


def setup_real(tmp_path, plan, monkeypatch, slot='HBM-01'):
    _,vision,robot,ghost,events=backend()
    robot.sim=SimpleNamespace(tcp=list(HOME),gripper_feedback_valid=True,robot_motion_done=1,gripper_position=25)
    robot.log.clear()
    calibration=tmp_path/'calibration/data/handeye_result.json';calibration.parent.mkdir(parents=True)
    calibration.write_text('{}')
    config=tmp_path/'vision_assembly/config';config.mkdir(parents=True)
    (config/'part_gripper_recipes.json').write_text('{}')
    (config/'assembly_slots_r1.json').write_text('{}')
    item=next(i for i in plan['plan'] if i['slot_code']==slot)
    prefix=slot.split('-')[0]
    opening=dict(pregrasp_opening_percent=item['tray_open_position'],grasp_opening_percent=item['grip_position'],release_opening_percent=item['release_position'])
    row=dict(job_id=JOB,part_id=prefix,slot_code=slot,order=1,source_index=item['tray_instance_index'],
             expected_gripper=opening,gripper_profiles={p:dict(velocity_percent=20,force_percent=1) for p in ('PREOPEN','GRASP','RELEASE')})
    payload=dict(job_id=JOB,calibration_digests=dict(recipes=digest({}),slots=digest({})),source_cycle_id='synthetic-scene',precision_plan=plan,plan_sha256=digest(plan),
        timestamp_ros_ns=int(time.time()*1e9),target_mode='frozen_unit',parts=[row],
        tray_inspection_reference=dict(handeye_sha256=hashlib.sha256(b'{}').hexdigest(),bindings=[
            dict(part_type=item['part_type'],physical_index=item['tray_instance_index'],reference_center_pixel=[10.,20.])]))
    vision.precision_snapshot=lambda _:deepcopy(payload)
    monkeypatch.setattr('tray_home_gate.wait_inventory',lambda *a,**k:dict(evidence='picked_cell_absent_not_physical_holding_proof',distinct_consecutive_frames=3))
    executor=PrecisionSteps(tmp_path,executor_factory=SimExecutor)
    real=RealRobotBackend(vision=vision,robot=robot,ghost=ghost,event_sink=events.append,
        step_executor=executor,operation_store=OperationJournal(tmp_path/'runtime/robot_operations'))
    pick=dict(job_id=JOB,operation_id=str(uuid4()),action='robot.pick',part_id=prefix,slot_code=slot,
        order=1,source_index=item['tray_instance_index'],approach_dz_mm=100.,retract_dz_mm=100.,**opening)
    place={k:v for k,v in pick.items() if k not in ('pregrasp_opening_percent','grasp_opening_percent')}
    place.update(action='robot.place',operation_id=str(uuid4()))
    return real,robot,executor,payload,pick,place,events


@pytest.mark.parametrize('slot',['HBM-01','GPU-01','PM-02','CAP-01'])
def test_pick_then_separate_place_no_next_part_and_exact_replay(tmp_path,plan,monkeypatch,slot):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch,slot)
    result=real.execute(pick)
    assert result.event is Event.OPERATION_COMPLETED, result
    assert robot.sim.tcp==list(HOME)
    assert real.held_part.slot_code==slot
    assert 'not_physical_holding_proof' in result.message
    before=list(robot.log)
    assert real.execute(pick)==result and robot.log==before
    placed=real.execute(place)
    assert placed.event is Event.OPERATION_COMPLETED, placed
    assert real.held_part is None
    assert all(row[1]==slot for row in robot.log if row[0]=='arm')
    assert len([row for row in robot.log if row[0]=='gripper'])==3
    phases=[e.phase for e in events if e.event is Event.PHASE_STARTED]
    assert len(phases)==len(set((e.operation_id,e.phase) for e in events if e.event is Event.PHASE_STARTED))
    another=dict(pick,operation_id=str(uuid4()))
    before=list(robot.log)
    assert real.execute(another).event is Event.OPERATION_FAILED
    assert not [r for r in robot.log[len(before):] if r[0] in ('arm','gripper')]


def test_failed_removal_blocks_place_and_survives_restart(tmp_path,plan,monkeypatch):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch,'GPU-01')
    def occupied(*a,**k):raise RuntimeError('picked cell still occupied')
    monkeypatch.setattr('tray_home_gate.wait_inventory',occupied)
    result=real.execute(pick)
    assert result.event is Event.OPERATION_FAILED and 'occupied' in result.message
    assert real.held_part is not None and executor.verified_pick is None
    before=list(robot.log)
    assert real.execute(place).error_code=='SAFETY_STOP'
    assert robot.log==before
    _, recovery=OperationJournal(tmp_path/'runtime/robot_operations').restore()
    assert recovery


@pytest.mark.parametrize('change', ['stale','hash','profile','offset','reference','source'])
def test_invalid_precision_input_never_starts_motion(tmp_path,plan,monkeypatch,change):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch)
    if change=='stale':payload['timestamp_ros_ns']-=1801_000_000_000
    if change=='hash':payload['plan_sha256']='changed'
    if change=='profile':pick['grasp_opening_percent']+=1
    if change=='offset':pick['approach_dz_mm']=99
    if change=='reference':payload['tray_inspection_reference']['bindings']=[]
    if change=='source':pick['source_index']=2
    result=real.execute(pick)
    assert result.event is Event.OPERATION_FAILED, result
    assert not [r for r in robot.log if r[0] in ('arm','gripper')]
    assert real.held_part is None


def test_cap_removal_uses_registered_tray_cells_and_rejects_weak_presence():
    reference=dict(handeye_sha256='h',bindings=[dict(part_type='right_white_brown',physical_index=1,reference_center_pixel=[10,20])])
    live=dict(timestamp_ros_ns=100_000_000_000,handeye_sha256='h',tray_registration='TRACKING',
        base_transform_status='OK',stable_detections=[dict(part_type='hbm')],detections=[])
    assert check_pick_removal(live,reference,{'CAP-01'},'CAP-01',101,99)['picked_slot']=='CAP-01'
    live['detections']=[dict(part_type='right_white_brown',reference_center_pixel=[10,20],confidence=.01)]
    with pytest.raises(RuntimeError,match='occupied'):
        check_pick_removal(live,reference,{'CAP-01'},'CAP-01',101,99)


def test_facade_publishes_exact_current_ghost_immediately_before_move():
    from fr5_process_sequences.real_precision_steps import PortExecutor
    log=[]
    robot=SimpleNamespace(assert_ready=lambda:None,_fresh_state=lambda:'fresh',
        _service=lambda command,code: log.append(('command',command)) or '0')
    joints=(1.,2.,3.,4.,5.,6.)
    ghost=SimpleNamespace(publish_stage_target=lambda values,**kw:log.append(('ghost',values,kw)))
    b=SimpleNamespace(_robot=robot,_ghost=ghost,_assert_not_paused=lambda:None)
    op=SimpleNamespace(job_id=JOB,operation_id='operation',action=Action.PICK,slot_code='HBM-01')
    facade=PortExecutor(b,op);facade.phase='02_pick_combined_xy_abc'
    facade.waypoint=SimpleNamespace(target_joints=joints)
    facade.service('JNTPoint(1,1,2,3,4,5,6)')
    facade.service('MoveJ(JNT1,25,1,0)',state_validator=lambda s:None)
    assert [v[0] for v in log]==['command','ghost','command']
    assert log[1][1]==joints and log[1][2]['phase']=='02_pick_combined_xy_abc'


def test_facade_rejects_unchanged_cached_feedback():
    import threading
    from fr5_process_sequences.real_precision_steps import PortExecutor
    from fr5_process_sequences.real_backend import BackendFailure
    robot=SimpleNamespace(_lock=threading.Lock(),_state=object(),_state_sequence=1,
        _state_received_at=time.monotonic())
    b=SimpleNamespace(_robot=robot,_assert_not_paused=lambda:None)
    with pytest.raises(BackendFailure,match='distinct fresh'):
        PortExecutor(b,None).spin_state(timeout_sec=.01)


def test_frozen_targets_keep_old_source_stamp_and_live_age_policy():
    from test_sequencer_api import payload_fixture
    from fr5_process_sequences.real_vision_adapter import build_target_payload
    snapshot,steps,planner=payload_fixture()
    args=dict(snapshot=snapshot, recipes=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text()),
        slots={},steps=steps,job_id=JOB,plan_builder=planner,now=1000)
    with pytest.raises(ValueError,match='stale'):build_target_payload(**args)
    result=build_target_payload(**args,frozen_unit=True)
    assert result['timestamp_ros_ns']==99_000_000_000
    assert result['target_mode']=='frozen_unit'
    with pytest.raises(ValueError,match='stale'):
        build_target_payload(**dict(args,now=2000),frozen_unit=True)


def test_real_recipe_not_ready_is_rejected_before_any_handlers():
    from fr5_process_sequences.sequencer_robot_client import RosSequencerRobotClient
    client=object.__new__(RosSequencerRobotClient)
    client._real_transport=True;client.recipe={'real_execution_ready':False}
    with pytest.raises(ValueError,match='not commissioned'):client.runRecipe({})
