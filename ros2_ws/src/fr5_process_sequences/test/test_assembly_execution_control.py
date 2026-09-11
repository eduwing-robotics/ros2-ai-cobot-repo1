import copy
import threading
from types import SimpleNamespace as NS
from uuid import uuid4
import pytest

REAL_THREAD_START = threading.Thread.start

from test_assembly_execution import production
from test_assembly_cycle_api import controller
from fr5_process_sequences.assembly_execution_control import AssemblyExecutionControl
from fr5_process_sequences.real_backend import BackendFailure


@pytest.fixture
def rig(production):
    contract,data,process,calls=production
    log=[]
    state=NS(robot_motion_done=1,gripper_feedback_valid=True,gripperfaultnum=0,grippererro=0,
             grip_motion_done=2,gripper_position=17.,**{'cart_'+a+'_cur_pos':0. for a in 'xyzabc'})
    robot=NS(_fresh_state=lambda:state,_assert_health=lambda _:None,
        pause_motion=lambda:log.append('pause'),observe_stopped=lambda:'fresh_feedback_verified_stopped',
        resume_motion=lambda:log.append('resume') or 'fresh_feedback_resume_applied')
    backend=NS(_robot=robot,held_part=None,_active=None,_paused=threading.Event(),_recovery_required=False,
               control=NS(checks={}),continuous_transfer_enabled=True)
    control=AssemblyExecutionControl(contract.controller,backend,enabled=True,buffered_verified=True)
    contract.control=control;contract.command(data)
    return contract,control,state,log,data


def request(rig,action='pause',sequence=1):
    contract,control,state,log,data=rig
    result=dict(schema=data['schema'],action='assembly.'+action,execution_id=data['execution_id'],
                control_id=str(uuid4()),control_sequence=sequence)
    if action=='resume':result['pause_control_id']=contract.controller.state.get('pause_control_id')
    return result


def apply(rig,data):
    contract,control,*_=rig
    accepted=contract.command(data)
    assert accepted['request_accepted'] and not accepted['control_applied']
    control._apply(data)  # Fixture suppresses worker start; deterministic fake hardware.
    return contract.snapshot(data['execution_id'])


def test_verified_pause_then_same_execution_resume_without_child_signal(rig):
    contract,control,state,log,data=rig
    paused=apply(rig,request(rig))
    assert paused['status']=='paused' and paused['stop_verified'] and paused['resume_available']
    assert control.blocked.is_set()
    resumed=apply(rig,request(rig,'resume',2))
    assert resumed['status']=='running' and not control.blocked.is_set()
    assert resumed['execution_id']==data['execution_id']
    assert log==['pause','resume'] and not contract.controller.process.signals


def test_duplicate_controls_do_not_repeat_hardware(rig):
    contract,control,state,log,data=rig
    pause=request(rig);apply(rig,pause)
    assert contract.command(pause)['control_applied']
    resume=request(rig,'resume',2);apply(rig,resume)
    assert contract.command(resume)['resume_applied']
    assert log==['pause','resume']


def test_late_resume_from_earlier_pause_is_rejected(rig):
    contract,control,state,log,data=rig
    apply(rig,request(rig));old=request(rig,'resume',2);apply(rig,old)
    apply(rig,request(rig,'pause',3))
    stale=dict(old,control_id=str(uuid4()),control_sequence=4)
    with pytest.raises(BackendFailure,match='previous pause'):contract.command(stale)
    assert log==['pause','resume','pause'] and control.blocked.is_set()


def test_pause_cannot_claim_verified_on_missing_feedback(rig):
    contract,control,state,log,data=rig
    control.robot.observe_stopped=lambda:'stop_not_verified_feedback_timeout'
    result=apply(rig,request(rig))
    assert result['status']=='recovery_required' and not result['resume_available']
    assert control.blocked.is_set() and control.backend._recovery_required


def test_resume_rejects_changed_gripper(rig):
    contract,control,state,log,data=rig
    apply(rig,request(rig));state.gripper_position=20.
    result=apply(rig,request(rig,'resume',2))
    assert result['status']=='recovery_required' and 'resume' not in log
    assert control.blocked.is_set()


def test_buffered_pause_requires_explicit_commissioning(rig):
    contract,control,state,log,data=rig;control.buffered_verified=False
    assert not contract.capabilities()['pause']
    with pytest.raises(BackendFailure,match='not commissioned'):contract.command(request(rig))
    assert not log and not control.blocked.is_set()


def test_foreign_execution_and_sequence_conflict_do_not_touch_owner(rig):
    contract,control,state,log,data=rig;pause=request(rig)
    with pytest.raises(BackendFailure):contract.command(dict(pause,execution_id=str(uuid4())))
    apply(rig,pause)
    before=copy.deepcopy(contract.controller.state)
    with pytest.raises(BackendFailure):contract.command(dict(pause,control_sequence=2))
    assert contract.controller.state==before


def test_dispatch_waits_through_pause_and_sends_once_after_resume(rig):
    contract,control,state,log,data=rig
    apply(rig,request(rig));sent=[]
    def dispatch():
        with control.dispatch():
            sent.append('move')
    thread=threading.Thread(target=dispatch,daemon=True)
    REAL_THREAD_START(thread)
    thread.join(.03);assert not sent
    apply(rig,request(rig,'resume',2))
    thread.join(1.);assert sent==['move'] and not thread.is_alive()


def test_expired_observation_disables_resume_and_never_sends_resume(rig):
    contract,control,state,log,data=rig
    control.backend._active=NS(job_id=data['execution_id'],operation_id='pick')
    def expired():
        raise BackendFailure('OBSERVATION_EXPIRED','source observation expired during pause')
    control.backend.control.checks['pick']=expired
    paused=apply(rig,request(rig))
    assert not paused['resume_available']
    assert 'expired' in paused['resume_unavailable_reason']
    result=apply(rig,request(rig,'resume',2))
    assert result['status']=='recovery_required' and 'resume' not in log
    assert control.blocked.is_set()


def test_cancel_available_without_retained_pause_commissioning(rig):
    contract,control,state,log,data=rig
    control.enabled=False;control.buffered_verified=False
    control.robot.stop_motion=lambda:log.append('stop')
    cancel=request(rig,'cancel')
    assert contract.capabilities()['cancel'] and not contract.capabilities()['pause']
    accepted=contract.command(cancel)
    assert accepted['request_accepted'] and contract.controller.state['status']=='stop_requested'
    assert control.blocked.is_set()
    control._cancel(cancel)
    assert log==['stop'] and contract.controller.process.signals
    result=contract.command(cancel)
    assert result['event']=='CANCEL_STOP_CONFIRMED' and result['stop_verified']
    assert not result['resume_available'] and result['recovery_required']
    assert log==['stop']
    with pytest.raises(BackendFailure):contract.command(request(rig,'resume',2))


def test_cancel_from_paused_does_not_resume(rig):
    contract,control,state,log,data=rig
    apply(rig,request(rig))
    control.robot.stop_motion=lambda:log.append('stop')
    cancel=request(rig,'cancel',2);contract.command(cancel);control._cancel(cancel)
    assert log==['pause','stop'] and control.backend._paused.is_set()
    assert control.backend._recovery_required


def test_cancel_failure_never_claims_stopped_and_interrupts_worker(rig):
    contract,control,state,log,data=rig
    def fail():raise BackendFailure('SAFETY_STOP','stop failed')
    control.robot.stop_motion=fail
    cancel=request(rig,'cancel');contract.command(cancel);control._cancel(cancel)
    reply=contract.command(cancel)
    assert reply['event']=='CONTROL_FAILED' and not reply['stop_verified']
    assert contract.controller.process.signals and control.blocked.is_set()


def test_boundary_pause_and_resume_do_not_send_controller_pause(rig):
    contract,control,state,log,data=rig
    control.boundary_pause=True;control.buffered_verified=False
    control.robot.observe_stopped=lambda **kwargs:'fresh_feedback_verified_stopped'
    assert contract.capabilities()['pause']
    assert contract.capabilities()['pause_behavior']=='after_dispatched_motion'
    paused=apply(rig,request(rig))
    assert paused['status']=='paused' and paused['resume_available'] and not log
    resumed=apply(rig,request(rig,'resume',2))
    assert resumed['status']=='running' and not log and not control.blocked.is_set()


def test_boundary_resume_rejects_changed_pose(rig):
    contract,control,state,log,data=rig
    control.boundary_pause=True
    control.robot.observe_stopped=lambda **kwargs:'fresh_feedback_verified_stopped'
    apply(rig,request(rig));state.cart_x_cur_pos=1
    resumed=apply(rig,request(rig,'resume',2))
    assert resumed['status']=='recovery_required' and not log and control.blocked.is_set()
