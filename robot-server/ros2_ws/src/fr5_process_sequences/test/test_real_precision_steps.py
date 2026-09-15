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


@pytest.mark.parametrize('slot', ['GPU-01'] + [f'HBM-{i:02d}' for i in range(1,9)]
    + [f'PM-{i:02d}' for i in range(1,5)] + [f'VRM-{i:02d}' for i in range(1,6)]
    + ['IND-01','IND-02'] + [f'CAP-{i:02d}' for i in range(1,6)])
def test_single_routes_preserve_tested_pick_and_home_to_place(plan,slot):
    item=next(i for i in plan['plan'] if i['slot_code']==slot)
    original=add_inspections(build_tcp_route([item],list(HOME),350,resume_after_grasp=False),HOME)
    cut=next(i for i,(_,w) in enumerate(original) if w.label=='tray_after_inspect')
    pick=single_route(item,HOME,350,Action.PICK)
    place=single_route(item,HOME,350,Action.PLACE)
    expected = [(s,w) for s,w in original[:cut+1]
                if w.label != 'post_grasp_proof_lift_100mm_vertical']
    if len(pick) == len(expected) - 2:
        # A short arrival replaces only the two intermediate points and uses
        # Cartesian interpolation; every other target remains unchanged.
        expected = [(s,w) for s,w in expected if w.label != 'tray_after_mid_travel']
        assert [(s,w.label,w.tcp) for s,w in pick] == [(s,w.label,w.tcp) for s,w in expected]
        assert next(w for _,w in pick if w.label == 'tray_after_travel').linear
    else:
        assert pick == expected
    assert place==original[cut+1:]
    assert pick[-1][1].tcp==HOME
    assert all(s==slot for s,_ in pick+place)
    assert not any('place_' in w.label for _,w in pick)
    assert not any('pick_' in w.label or w.label.endswith('inspect') for _,w in place)
    assert place[-1][1].tcp[2]==pytest.approx(item['place_final_tcp'][2]+100)


class SimExecutor:
    def __init__(self,backend,operation):
        self.backend=backend;self.operation=operation;self.state=backend._robot.sim
        self.robot=backend._robot
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
    robot.sim=SimpleNamespace(tcp=list(HOME),gripper_feedback_valid=True,robot_motion_done=1,gripper_position=25,robot_mode=0,tool_num=1,work_num=0)
    robot.assert_motion_permitted=robot.assert_ready
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
             source_id='source-'+slot,tray_registration_id='reg',source_observation_id='obs',calibration_instance_index=item['tray_instance_index'],
             expected_gripper=opening,gripper_profiles={p:dict(velocity_percent=20,force_percent=1) for p in ('PREOPEN','GRASP','RELEASE')})
    payload=dict(job_id=JOB,calibration_digests=dict(recipes=digest({}),slots=digest({})),source_cycle_id='synthetic-scene',precision_plan=plan,plan_sha256=digest(plan),
        timestamp_ros_ns=int(time.time()*1e9),target_mode='frozen_unit',parts=[row],
        tray_inspection_reference=dict(handeye_sha256=hashlib.sha256(b'{}').hexdigest(),bindings=[
            dict(part_type=item['part_type'],physical_index=item['tray_instance_index'],reference_center_pixel=[10.,20.])]))
    from fr5_process_sequences.source_bindings import validate_source_bindings
    payload['slots'] = [deepcopy(row)]
    payload['source_bindings_sha256'] = validate_source_bindings(payload)
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


@pytest.mark.parametrize('case', ['worker_delay', 'receive_gap_recovered', 'stale',
                                 'health_fault', 'cancel', 'between_waits_gap'])
def test_feedback_wait_distinguishes_worker_delay_from_receive_loss(monkeypatch, case):
    import threading
    from fr5_process_sequences.real_precision_steps import PortExecutor
    from fr5_process_sequences.real_ros_node import FairinoRobotPort
    from fr5_process_sequences.real_backend import BackendFailure

    clock = [1.0]
    monkeypatch.setattr(time, 'monotonic', lambda: clock[0])
    robot = FairinoRobotPort.__new__(FairinoRobotPort)
    robot._lock = threading.Lock()
    robot._state = None
    robot._state_sequence = 0
    robot._state_received_at = 0.
    robot._state_gap_sequence = 0
    robot._state_gap_sec = 0.
    robot._state_callback(SimpleNamespace(fault=False))
    cancelled = [False]
    def check_cancel():
        if cancelled[0]:
            raise BackendFailure('CANCELLED', 'cancel requested')
    waiter = PortExecutor(SimpleNamespace(_robot=robot, _assert_not_paused=check_cancel), None)
    waiter.safety_error = lambda state: 'hardware fault' if state.fault else None

    def delay_worker(_):
        if case in ('receive_gap_recovered', 'between_waits_gap'):
            clock[0] = 1.27
            robot._state_callback(SimpleNamespace(fault=False))
            clock[0] = 1.30
            robot._state_callback(SimpleNamespace(fault=False))
        elif case != 'stale':
            for i in range(1, 31):
                clock[0] = 1.0 + i * .01
                robot._state_callback(SimpleNamespace(fault=case == 'health_fault'))
        clock[0] = 1.31
        cancelled[0] = case == 'cancel'
    monkeypatch.setattr(time, 'sleep', delay_worker)
    if case == 'between_waits_gap':
        delay_worker(0)  # An intervening service must not hide a receive gap.
    if case == 'worker_delay':
        assert waiter.spin_state() is robot._state
        assert robot._state_sequence == 31
        assert robot._state_gap_sequence == 0
    else:
        expected = ('receive gap' if 'gap' in case else 'hardware fault'
                    if case == 'health_fault' else 'cancel requested'
                    if case == 'cancel' else 'distinct fresh')
        with pytest.raises(BackendFailure, match=expected):
            waiter.spin_state()
        if 'gap' in case:
            assert robot._state_gap_sequence == 2  # Recovery frames preserve it.
            assert robot._state_gap_sec == pytest.approx(.27)


@pytest.mark.parametrize('slot', ['HBM-01', 'GPU-01', 'PM-02', 'VRM-01', 'CAP-01', 'IND-01'])
def test_pick_lift_removes_only_collinear_noninspection_stop(plan, slot):
    from execute_full_fixed_cycle import waypoint_speed
    item = next(i for i in plan['plan'] if i['slot_code'] == slot)
    old = add_inspections(build_tcp_route([item], list(HOME), 350,
                                         resume_after_grasp=False), HOME)
    route = single_route(item, HOME, 350, Action.PICK)
    idx = next(i for i, (_, w) in enumerate(route)
               if w.label == 'post_grasp_lift_50mm_vertical')
    low, high = route[idx][1], route[idx + 1][1]
    middle = next(w for _, w in old if w.label == 'post_grasp_proof_lift_100mm_vertical')
    assert high.label == 'tray_after_raise'
    assert low.linear and high.linear
    assert low.tcp[2] < middle.tcp[2] < high.tcp[2]
    for k in (0, 1, 3, 4, 5):
        assert low.tcp[k] == middle.tcp[k] == high.tcp[k]
    assert high.tcp[2] >= 350
    assert route[-1][1].label == 'tray_after_inspect'
    assert route[-1][1].tcp == HOME
    speeds = dict(vertical=10, travel=40, combined_rotation=40, clearance_lift=30)
    assert waypoint_speed(low.label, speeds) == 10
    assert waypoint_speed(high.label, speeds) == 30
    # The standalone diagnostic still retains its explicit 100 mm proof stop.
    assert any(w.label == 'post_grasp_proof_lift_100mm_vertical' for _, w in old)


@pytest.mark.parametrize('slot', ['HBM-05', 'HBM-06'])
def test_near_home_arrival_has_one_horizontal_segment_and_exact_inspection(plan, slot):
    item = next(i for i in plan['plan'] if i['slot_code'] == slot)
    route = single_route(item, HOME, 350, Action.PICK)
    start = next(i for i, (_,w) in enumerate(route) if w.label == 'tray_after_raise')
    tail = [w for _,w in route[start:]]
    assert [w.label for w in tail] == ['tray_after_raise', 'tray_after_travel', 'tray_after_inspect']
    assert all(w.linear for w in tail)
    assert tail[0].tcp[2] == tail[1].tcp[2] == 350
    assert tail[1].tcp[:2] == HOME[:2]
    assert tail[1].tcp[3:] == HOME[3:]
    assert tail[2].tcp == HOME
    assert tail[1].tcp[2] - tail[2].tcp[2] == pytest.approx(12.12)


def test_long_home_arrival_retains_original_high_queue(plan):
    item = next(i for i in plan['plan'] if i['slot_code'] == 'HBM-01')
    route = single_route(item, HOME, 350, Action.PICK)
    mids = [w for _,w in route if w.label == 'tray_after_mid_travel']
    assert len(mids) == 2
    assert all(not w.linear and w.tcp[2] == 350 for w in mids)


def test_short_home_arrival_cannot_bypass_clearance_gate(tmp_path, plan, monkeypatch):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch,'HBM-05')
    from fr5_process_sequences.real_backend import BackendFailure
    checked=[]
    def reject(node, group, check_context):
        checked.append(group[0].label)
        raise BackendFailure('SAFETY_STOP', 'test clearance not reached')
    monkeypatch.setattr('fr5_process_sequences.continuous_transfer.wait_transfer_start',reject)
    result=real.execute(pick)
    assert result.event is Event.OPERATION_FAILED
    assert 'clearance not reached' in result.message
    assert checked == ['tray_after_travel']
    assert not any(r[0]=='arm' and r[2] in ('tray_after_travel','tray_after_inspect') for r in robot.log)
    assert real._recovery_required


def test_hbm04_pick_splits_high_transfer_without_changing_pick(plan):
    from execute_full_fixed_cycle import build_tcp_route
    item=next(i for i in plan['plan'] if i['slot_code']=='HBM-04')
    prior=next(i for i in plan['plan'] if i['slot_code']=='HBM-03')
    start=list(prior['place_final_tcp']);start[2]+=100
    full=build_tcp_route([item],start,350,resume_after_grasp=False)
    api=single_route(item,start,350,Action.PICK)
    for route in (full,api):
        high=next(w for _,w in route if w.label=='pre_pick_safe_vertical')
        mids=[w for _,w in route if w.label=='pick_combined_xy_abc_midpoint']
        end=next(w for _,w in route if w.label=='pick_combined_xy_abc')
        assert len(mids)==1
        mid=mids[0]
        assert high.tcp[2]==mid.tcp[2]==end.tcp[2]==350
        assert mid.tcp[:2]==pytest.approx((np.asarray(high.tcp[:2])+end.tcp[:2])/2)
        for axis in (3,4,5):
            delta=(end.tcp[axis]-high.tcp[axis]+180)%360-180
            assert mid.tcp[axis]==pytest.approx(high.tcp[axis]+delta/2)
        final=next(w for _,w in route if w.label=='pick_final_50mm_vertical')
        assert final.tcp==pytest.approx(item['pick_final_tcp'])


@pytest.mark.parametrize('slot', ['GPU-01'] + [f'HBM-{i:02d}' for i in range(1,9)]
    + [f'PM-{i:02d}' for i in range(1,5)] + [f'VRM-{i:02d}' for i in range(1,6)]
    + ['IND-01','IND-02'] + [f'CAP-{i:02d}' for i in range(1,6)])
def test_all_25_sources_preserved_through_pick_and_place_callbacks(tmp_path,plan,monkeypatch,slot):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch,slot)
    assert real.execute(pick).event is Event.OPERATION_COMPLETED
    # Live vision changes cannot replace the already held plan for Place.
    payload['parts'][0]['source_id']='changed-live-source'
    assert real.execute(place).event is Event.OPERATION_COMPLETED
    for event in events:
        context=json.loads(event.message)
        assert context['source_id']=='source-'+slot
        assert context['source_index']==pick['source_index']
        assert context['tray_registration_id']=='reg' and context['source_observation_id']=='obs'
        assert context['attachment_binding_valid'] is True
        assert context['physical_holding_verified'] is False


@pytest.mark.parametrize('bad',['missing','duplicate','slot_mismatch','fingerprint'])
def test_bad_binding_rejected_before_arm_or_gripper(tmp_path,plan,monkeypatch,bad):
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch)
    if bad=='missing':payload['parts'][0]['source_id']=None
    if bad=='duplicate':payload['parts'].append(deepcopy(payload['parts'][0]));payload['slots'].append(deepcopy(payload['slots'][0]))
    if bad=='slot_mismatch':payload['slots'][0]['source_id']='other'
    if bad=='fingerprint':payload['source_bindings_sha256']='other'
    result=real.execute(pick)
    assert result.event is Event.OPERATION_FAILED and result.error_code=='INVALID_REQUEST'
    assert not any(x[0] in ('arm','gripper') for x in robot.log)


def test_binding_cannot_change_even_with_recomputed_fingerprint(tmp_path,plan,monkeypatch):
    from fr5_process_sequences.source_bindings import validate_source_bindings
    real,robot,executor,payload,pick,place,events=setup_real(tmp_path,plan,monkeypatch)
    executor.binding_plans[(JOB,payload['plan_sha256'])]=payload['source_bindings_sha256']
    for row in payload['parts']+payload['slots']:row['source_id']='replacement'
    payload['source_bindings_sha256']=validate_source_bindings(payload)
    result=real.execute(pick)
    assert result.event is Event.OPERATION_FAILED and 'changed after' in result.message
    assert not any(x[0] in ('arm','gripper') for x in robot.log)
