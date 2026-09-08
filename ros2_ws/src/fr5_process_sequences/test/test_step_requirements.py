import json
from uuid import uuid4
import pytest
from fr5_process_sequences.real_backend import RealRobotBackend
from fr5_process_sequences.real_contract import Event
from fr5_process_sequences.real_ros_node import OperationJournal, require_commissioned_step
from fr5_process_sequences.assembly_cycle_api import AssemblyCycleController
from fr5_process_sequences.real_ghost import RealGhostTargetPublisher
from test_real_backend import backend, pick, JOB
from test_real_ghost import FakeNode


def make_backend(directory, commissioned=None):
    _,vision,robot,ghost,events=backend()
    journal=OperationJournal(directory)
    real=RealRobotBackend(vision=vision,robot=robot,ghost=ghost,event_sink=events.append,
                          operation_store=journal,commissioning_check=commissioned)
    return real,robot,journal


def move():
    return dict(job_id=JOB,operation_id=str(uuid4()),action='robot.move_joint',joint_point=[0]*6,point_name='home')


def test_completed_move_replays_after_restart_without_motion(tmp_path):
    real,robot,_=make_backend(tmp_path);request=move();result=real.execute(request)
    assert result.event is Event.OPERATION_COMPLETED
    restarted,newrobot,_=make_backend(tmp_path)
    assert restarted.execute(request)==result
    assert not newrobot.log
    conflict=dict(request,joint_point=[1]*6)
    assert restarted.execute(conflict).event is Event.REQUEST_REJECTED
    assert not newrobot.log


def test_pending_intent_after_restart_blocks_replay_and_new_motion(tmp_path):
    real,robot,journal=make_backend(tmp_path);request=move()
    from fr5_process_sequences.real_contract import parse_operation
    from fr5_process_sequences.real_backend import _fingerprint
    operation=parse_operation(request);journal.begin(operation,_fingerprint(operation))
    restarted,newrobot,_=make_backend(tmp_path)
    assert restarted.execute(request).error_code=='SAFETY_STOP'
    assert restarted.execute(move()).error_code=='SAFETY_STOP'
    assert not newrobot.log
    assert json.loads(next(tmp_path.glob('*.json')).read_text())['status']=='intent'


def test_uncommissioned_transfer_never_moves_or_claims_holding(tmp_path):
    real,robot,_=make_backend(tmp_path,require_commissioned_step)
    request=dict(job_id=JOB, operation_id=str(uuid4()), action="robot.transfer",
        object_id="assembled_pcb", approach_dz_mm=100., retract_dz_mm=100.,
        assembled_pcb_drop_approach_dz_mm=150., grasp_opening_percent=0., release_opening_percent=100.)
    result=real.execute(request)
    assert result.event is Event.OPERATION_FAILED and result.error_code=='SAFETY_STOP'
    assert not robot.log and real.held_part is None


def test_home_placeholder_ready_point_is_not_accepted_as_commissioned(tmp_path):
    real,robot,_=make_backend(tmp_path,require_commissioned_step)
    request=move();request['point_name']='assembly_ready'
    assert real.execute(request).error_code=='SAFETY_STOP'
    assert not robot.log


def test_missing_result_storage_never_reports_success(tmp_path,monkeypatch):
    real,robot,journal=make_backend(tmp_path)
    def fail(*args):raise OSError('disk unavailable')
    monkeypatch.setattr(journal,'finish',fail)
    result=real.execute(move())
    assert result.event is Event.OPERATION_FAILED
    assert 'persistence' in result.message and real._recovery_required


def test_legacy_ghost_uses_required_frame_and_radians():
    node=FakeNode();ghost=RealGhostTargetPublisher(node,backend='real')
    ghost.publish_joint_target([0,90,0,0,0,0]);message=node.publisher.messages[-1]
    assert message.header.frame_id=='base_link'
    assert message.name==['j1','j2','j3','j4','j5','j6']
    assert message.position[1]==pytest.approx(1.5707963267948966)


def test_production_bridge_rejects_batch_start_without_subprocess(tmp_path):
    d=tmp_path/'vision_assembly/config';d.mkdir(parents=True)
    (d/'assembly_launcher_revision.json').write_text(json.dumps({'revision':'r'}))
    def forbidden(*args,**kwargs):raise AssertionError('must not launch a cycle')
    controller=AssemblyCycleController(tmp_path,forbidden,lambda _:None,forbidden,allow_batch_start=False)
    assert 'assembly.start' not in controller.snapshot()['supported_actions']
    request=dict(schema='fr5.assembly_cycle/v1',action='assembly.start',job_id=str(uuid4()),operation_id=str(uuid4()),recipe_revision='r',confirm_scene_ready=True)
    from fr5_process_sequences.real_backend import BackendFailure
    with pytest.raises(BackendFailure,match='Sequencer'):controller.command(request)
