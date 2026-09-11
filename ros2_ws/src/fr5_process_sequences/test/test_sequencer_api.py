from copy import deepcopy
from pathlib import Path
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from fr5_process_sequences.real_contract import parse_operation, ContractError
from fr5_process_sequences.real_backend import BackendFailure
from fr5_process_sequences.real_ros_node import FairinoRobotPort, RosTargetVisionPort
from fr5_process_sequences.real_vision_adapter import build_target_payload
from fr5_process_sequences.sequencer_robot_client import SequencerRobotClient, OperationFailed
from test_real_backend import backend, pick, place, JOB, target
from test_real_ghost import FakeNode
from fr5_process_sequences.real_ghost import RealGhostTargetPublisher

ROOT = Path(__file__).resolve().parents[4]


def recipe():
    return yaml.safe_load((ROOT/'assembly_integration/config/sequencer_recipe.example.yaml').read_text())


def test_all_25_yaml_steps_roundtrip_mock_backend_and_external_handlers():
    real, vision, robot, ghost, events = backend()
    vision.validate_operation = lambda op: None
    lookups = []
    def indexed(part, index, job):
        lookups.append((part, index, job))
        return target()
    vision.locate_part_by_index = indexed
    vision.locate_slot_for_job = lambda *args: target(300, -200, 20)
    sent, external = [], []
    def send(command):
        sent.append(command)
        client.on_event(real.execute(command).to_dict())
    client = SequencerRobotClient(job_id=JOB, recipe=recipe(), send_command=send, send_pause=lambda _: None)
    handlers = {name: (lambda value, name=name: external.append((name,value)))
                for name in ('conveyor.move_to','vision.resolve_targets','inspection.run')}
    results = client.runRecipe(handlers)
    assert len(results) == 155
    assert len(sent) == 151
    assert len(ghost.targets) == 256
    assert [c['action'] for c in sent[:6]] == ['robot.move_joint','robot.move_joint','robot.pick',
        'robot.move_joint','robot.move_joint','robot.place']
    cap = [c for c in sent if c['action']=='robot.pick' and c['part_id']=='CAP']
    assert [(c['order'],c['source_index']) for c in cap] == [(14,1),(15,2),(16,3),(17,4),(18,5)]
    assert ('CAP',1,JOB) in lookups
    assert [c['part_id'] for c in sent if c['action']=='robot.pick'] == [s['part_id'] for s in recipe()['steps']]
    assert external == [('conveyor.move_to','ASSEMBLY'),('vision.resolve_targets','recipe_steps'),
                        ('conveyor.move_to','INSPECTION'),('inspection.run','assembled_pcb')]


def test_client_waits_for_correlated_terminal_and_deduplicates():
    sent=[]
    client=SequencerRobotClient(job_id=JOB, send_command=sent.append, send_pause=lambda _:None)
    oid=str(uuid4())
    future=client.moveJoint('home',[0]*6,operation_id=oid)
    assert not future.cancel()
    assert client.moveJoint('home',[0]*6,operation_id=oid) is future
    with pytest.raises(RuntimeError,match='previous operation'):
        client.moveJoint('home',[1]*6)
    event=dict(job_id=str(uuid4()),operation_id=oid,action='robot.move_joint',event='OPERATION_COMPLETED')
    assert not client.on_event(event)
    event['job_id']=JOB;event['event']='PHASE_COMPLETED'
    assert not client.on_event(event)
    event['event']='OPERATION_COMPLETED'
    assert client.on_event(event)
    assert future.result() == event
    assert len(sent)==1
    with pytest.raises(ValueError,match='different content'):
        client.moveJoint('home',[1]*6,operation_id=oid)


def test_failed_recipe_stops_before_any_next_step():
    sent=[]
    def send(cmd):
        sent.append(cmd)
        client.on_event(dict(cmd,event='OPERATION_FAILED',error_code='IK_FAILED',message='no solution'))
    client=SequencerRobotClient(job_id=JOB,recipe=recipe(),send_command=send,send_pause=lambda _:None)
    with pytest.raises(OperationFailed,match='IK_FAILED'):
        client.runRecipe({name:lambda _:None for name in ('conveyor.move_to','vision.resolve_targets','inspection.run')})
    assert len(sent)==1


def test_delivery_unknown_and_timeout_do_not_advance_or_retry():
    def broken(_):raise OSError('network')
    client=SequencerRobotClient(job_id=JOB,send_command=broken,send_pause=lambda _:None)
    with pytest.raises(RuntimeError,match='delivery unknown'):client.moveJoint('home',[0]*6)
    with pytest.raises(RuntimeError,match='previous operation'):client.moveJoint('home',[0]*6)
    client=SequencerRobotClient(job_id=JOB,send_command=lambda _:None,send_pause=lambda _:None)
    future=client.moveJoint('home',[0]*6)
    with pytest.raises(TimeoutError):future.result(timeout=0.001)
    with pytest.raises(RuntimeError,match='previous operation'):client.moveJoint('home',[0]*6)


@pytest.mark.parametrize('index',[0,-1,True,1.5])
def test_invalid_source_index_rejected(index):
    with pytest.raises(ContractError):parse_operation(dict(pick(),source_index=index))


def test_preopen_is_independent_and_legacy_contract_still_works():
    real,_,robot,_,_=backend()
    assert not real.execute(dict(pick(),pregrasp_opening_percent=18)).error_code
    assert [v[1] for v in robot.log if v[0]=='gripper']==[18,18]
    with pytest.raises(ContractError):parse_operation(dict(pick(),pregrasp_opening_percent=101))


def test_stage_goal_is_exact_prepared_goal_before_motion():
    real,_,robot,ghost,_=backend()
    log=[]
    robot.prepare_motion=lambda t,j: (log.append(('prepare',tuple(j))) or tuple(j))
    ghost.publish_stage_target=lambda j,**meta: log.append(('ghost',tuple(j),meta))
    original=robot.move_cartesian
    robot.move_cartesian=lambda t,j,**kw:(log.append(('move',tuple(j))),original(t,j,**kw))
    assert not real.execute(pick()).error_code
    assert [x[0] for x in log]==['prepare','ghost','move']*3
    for i in range(0,9,3):assert log[i][1]==log[i+1][1]==log[i+2][1]
    assert [x[2]['phase'] for x in log if x[0]=='ghost']==['APPROACH','DESCEND','RETRACT']


def test_live_preflight_failure_sends_no_ghost_or_move():
    real,_,robot,ghost,_=backend()
    def fail(*_):raise BackendFailure('IK_FAILED','live branch changed')
    robot.prepare_motion=fail
    result=real.execute(pick())
    assert result.error_code=='IK_FAILED' and result.phase=='APPROACH'
    assert not ghost.targets
    assert not any(row[0].startswith('move_') or row[0]=='gripper' for row in robot.log)


def test_pause_during_first_move_blocks_remaining_phases():
    real,_,robot,ghost,_=backend()
    robot.wait_arm_complete=lambda *_:real.pause()
    result=real.execute(pick())
    assert result.error_code=='SAFETY_STOP'
    assert len(ghost.targets)==1
    assert not any(row[0]=='gripper' for row in robot.log)


def test_ros_live_ik_branch_check_preserves_exact_goal():
    port=object.__new__(FairinoRobotPort)
    port._maximum_joint_step=95
    port.assert_ready=lambda:None
    port.current_joints_deg=lambda:(0,)*6
    port.validate_joint_target=lambda j:None
    port.inverse_kinematics=lambda t,r:(10.1,)*6
    assert port.prepare_motion(target(),(10,)*6)==(10.1,)*6
    port.inverse_kinematics=lambda t,r:(12,)*6
    with pytest.raises(BackendFailure,match='branch'):port.prepare_motion(target(),(10,)*6)
    with pytest.raises(BackendFailure,match='step'):port.prepare_motion(None,(96,)*6)


def test_ghost_stage_has_ids_units_and_legacy_jointstate():
    node=FakeNode();publisher=RealGhostTargetPublisher(node,backend='real')
    publisher.publish_stage_target([0,90,0,0,0,0],job_id=JOB,operation_id='op',action='robot.pick',phase='DESCEND')
    data=json.loads(node.publisher.messages[0].data)
    assert data['target_id']==f"{data['server_instance_id']}:{data['target_sequence']}"
    assert data['stage_id']=='DESCEND' and data['target_sequence']==1
    assert data['positions_rad'][1]==pytest.approx(1.57079632679)
    assert data['positions_deg'][1]==90
    assert len(node.publisher.messages)==2


def payload_fixture():
    snapshot={'cycle_id':'test','board_capture':{'captured_unix':99},
              'tray_capture':{'captured_unix':98.5},'smd_close_capture':{'captured_unix':99.5},
              'smd_close_captured':True}
    steps=[dict(order=14,part_id='CAP',slot_code='CAP-01')]
    def planner(*_,**kwargs):
        assert kwargs['phase']=='smd'
        return {'plan':[dict(slot_code='CAP-01',part_type='right_white_brown',tray_instance_index=1,
            pick_final_tcp=[1,2,3,180,0,0],place_final_tcp=[4,5,6,180,0,180],
            tray_open_position=18,grip_position=12,release_position=17)]}
    return snapshot,steps,planner


def make_payload(snapshot=None):
    base,steps,planner=payload_fixture()
    return build_target_payload(snapshot=snapshot or base, recipes=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text()),slots={},steps=steps,
        job_id=JOB,plan_builder=planner,now=100)


def test_adapter_keeps_original_timestamp_identity_and_corrected_coordinates():
    data=make_payload()
    assert data['timestamp_ros_ns']==99000000000
    assert data['parts'][0]['timestamp_ros_ns']==99500000000
    assert data['parts'][0]['source_index']==1 and data['parts'][0]['order']==14
    assert data['parts'][0]['tcp_pose_mm_deg']==[1,2,3,180,0,0]
    assert data['parts'][0]['expected_gripper']['pregrasp_opening_percent']==18


@pytest.mark.parametrize('stamp',[90,101,float('nan')])
def test_adapter_rejects_stale_future_nonfinite_without_restamping(stamp):
    snapshot,_,_=payload_fixture();snapshot['board_capture']['captured_unix']=stamp
    with pytest.raises(ValueError):make_payload(snapshot)


def test_adapter_propagates_precision_planner_rejection():
    snapshot,steps,_=payload_fixture()
    def reject(*_,**kw):raise RuntimeError('SMD center jitter')
    with pytest.raises(RuntimeError,match='jitter'):
        build_target_payload(snapshot=snapshot,recipes=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text()),slots={},steps=steps,job_id=JOB,plan_builder=reject,now=100)


def vision_port():
    port=object.__new__(RosTargetVisionPort)
    port._node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=100000000000)))
    port._maximum_age_sec=2.5
    port._snapshot=lambda:make_payload()
    return port


def test_indexed_targets_match_job_and_real_gripper_recipe():
    port=vision_port()
    assert port.locate_part_by_index('CAP',1,JOB).x_mm==1
    with pytest.raises(BackendFailure):port.locate_part_by_index('CAP',14,JOB)
    with pytest.raises(BackendFailure):port.locate_part_by_index('CAP',1,str(uuid4()))
    command=dict(pick(),order=14,part_id='CAP',slot_code='CAP-01',source_index=1,
                 pregrasp_opening_percent=18,grasp_opening_percent=12,release_opening_percent=17)
    port.validate_operation(parse_operation(command))
    command['grasp_opening_percent']=5
    with pytest.raises(BackendFailure,match='calibrated 12'):
        port.validate_operation(parse_operation(command))


def test_adapter_with_actual_precision_planner_keeps_user_order_and_real_values():
    import sys
    sys.path.insert(0,str(ROOT/'vision_assembly/scripts'))
    from full_cycle_plan import build_plan
    snapshot=json.loads((ROOT/'vision_assembly/data/fixed_cycle_full_restart_retry2_2026-09-02.json').read_text())
    # Synthetic test input only: historical data is never published or written.
    snapshot["smd_close_captured"] = True
    for key in ('board_capture','tray_capture','smd_close_capture'):
        snapshot.setdefault(key,{})['captured_unix']=99
        snapshot[key]['source_age_sec']=0
    data=build_target_payload(snapshot=snapshot,
        recipes=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text()),
        slots=json.loads((ROOT/'vision_assembly/config/assembly_slots_r1.json').read_text()),
        steps=recipe()['steps'],job_id=JOB,plan_builder=build_plan,now=100)
    assert len(data['parts'])==25
    assert [x['slot_code'] for x in data['parts']]==[s['slot_code'] for s in recipe()['steps']]
    cap=data['parts'][13]
    assert cap['part_id']=='CAP' and cap['source_index']==1
    assert cap['expected_gripper']==dict(pregrasp_opening_percent=18,grasp_opening_percent=12,release_opening_percent=17)
    assert cap['tcp_pose_mm_deg'][2]==-52.177
    caps=[row for row in data['parts'] if row['part_id']=='CAP']
    assert len(caps)==5
    for cap in caps:
        assert cap['expected_gripper']==dict(pregrasp_opening_percent=18,grasp_opening_percent=12,release_opening_percent=17)
        port=object.__new__(FairinoRobotPort)
        commands=[]
        port._service=lambda command,code:commands.append(command)
        for phase,position in [('PREOPEN',18),('GRASP',12),('RELEASE',17)]:
            assert cap['gripper_profiles'][phase]==dict(velocity_percent=80,force_percent=50)
            port.move_profiled_gripper(position,cap['gripper_profiles'][phase])
        assert commands==['MoveGripper(1,18.0,80.0,50.0)',
                          'MoveGripper(1,12.0,80.0,50.0)',
                          'MoveGripper(1,17.0,80.0,50.0)']
    # Legacy IND success used MoveGripper(1,position), i.e. driver80/50.
    # Check the actual recipe through the adapter and transport, not a mock profile.
    for ind in (row for row in data['parts'] if row['part_id']=='IND'):
        assert ind['expected_gripper']==dict(pregrasp_opening_percent=21,grasp_opening_percent=14,release_opening_percent=20)
        port=object.__new__(FairinoRobotPort)
        commands=[]
        port._service=lambda command,code:commands.append(command)
        for phase,position in [('PREOPEN',21),('GRASP',14),('RELEASE',20)]:
            assert ind['gripper_profiles'][phase]==dict(velocity_percent=80,force_percent=50)
            port.move_profiled_gripper(position,ind['gripper_profiles'][phase])
        assert commands==['MoveGripper(1,21.0,80.0,50.0)',
                          'MoveGripper(1,14.0,80.0,50.0)',
                          'MoveGripper(1,20.0,80.0,50.0)']


def test_profiled_gripper_preserves_explicit_low_force_in_driver_request():
    port=object.__new__(FairinoRobotPort)
    commands=[]
    port._service=lambda command,code:commands.append(command)
    port.move_profiled_gripper(12,dict(velocity_percent=50,force_percent=1))
    assert commands == ['MoveGripper(1,12.0,50.0,1.0)']


@pytest.mark.parametrize('removed_kind', ['gpu', 'hbm', 'long_orange', 'black_block', 'marked_white', 'right_white_brown'])
def test_adapter_preserves_selected_set_for_post_pick_inspection(removed_kind):
    import sys
    sys.path.insert(0, str(ROOT/'vision_assembly/scripts'))
    from tray_home_gate import check_pick_removal
    config=json.loads((ROOT/'vision_assembly/config/tray_cycle_set_selection.json').read_text())
    snapshot,_,_=payload_fixture()
    rule=config['parts'][removed_kind]
    width=config['reference_image_size_px']['width']
    height=config['reference_image_size_px']['height']
    polygon=rule['section_polygon_normalized']
    point=[sum(p[0] for p in polygon)/len(polygon)*width,
           sum(p[1] for p in polygon)/len(polygon)*height]
    axis=0 if rule['axis']=='x' else 1
    point[axis]=rule['boundary_px']-30
    other=list(point);other[axis]=rule['boundary_px']+30
    capture=snapshot['tray_capture']
    capture.update(handeye_sha256='test', assembly_set_selection={'set_index':1,'config':config},
        parts=[dict(part_type=removed_kind, instance_index=1, reference_center_pixel=point)])
    reference=make_payload(snapshot)['tray_inspection_reference']
    assert reference['assembly_set_selection']==capture['assembly_set_selection']
    assert reference['assembly_set_selection'] is not capture['assembly_set_selection']
    remaining=dict(part_type=removed_kind,instance_index=1,reference_center_pixel=other)
    live=dict(timestamp_ros_ns=100_000_000_000, tray_registration='TRACKING',
        base_transform_status='OK',handeye_sha256='test',stable_detections=[remaining],detections=[remaining])
    code={'gpu':'GPU','hbm':'HBM','long_orange':'PM','black_block':'VRM','marked_white':'IND','right_white_brown':'CAP'}[removed_kind]
    slot=code+'-01'
    assert check_pick_removal(live,reference,{slot},slot,100.1,99)['picked_slot']==slot
    occupied=dict(part_type=removed_kind,instance_index=1,reference_center_pixel=point)
    live['detections'].append(occupied)
    with pytest.raises(RuntimeError,match='still occupied'):
        check_pick_removal(live,reference,{slot},slot,100.1,99)
