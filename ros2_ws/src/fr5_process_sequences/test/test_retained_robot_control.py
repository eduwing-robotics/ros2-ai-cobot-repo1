import json
import threading
import time
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fr5_process_sequences.real_backend import BackendFailure
from fr5_process_sequences.real_contract import Event, parse_operation
from test_real_backend import backend, pick, JOB, PICK_OP


def rig(enabled=True):
    real, _, robot, *rest = backend()
    real.control.enabled = enabled
    operation = parse_operation(pick())
    real._active = operation
    real._phase_name = 'DESCEND'
    state = SimpleNamespace(gripper_position=25., grip_motion_done=2,
        gripper_feedback_valid=True, gripperfaultnum=0, grippererro=0)
    robot._fresh_state = lambda: state
    robot.observe_stopped = lambda: 'fresh_feedback_verified_stopped'
    def resume():
        robot.log.append(('resume',))
        return 'fresh_feedback_resume_applied'
    robot.resume_motion = resume
    real.control.register(operation, lambda: None)
    return real, robot, state


def request(command='pause', seq=1, **kwargs):
    return dict(command=command, control_id=str(uuid4()), control_sequence=seq,
                job_id=JOB, operation_id=PICK_OP, **kwargs)


def test_pause_blocks_worker_resume_continues_same_context():
    real, robot, _ = rig()
    paused = real.control.request(request())
    assert paused.event is Event.PAUSE_CONFIRMED
    progressed = threading.Event()
    worker = threading.Thread(target=lambda: (real._assert_not_paused(), progressed.set()))
    worker.start()
    assert not progressed.wait(.05)
    resumed = real.control.request(request('resume', 2))
    worker.join(1)
    assert resumed.event is Event.RESUME_CONFIRMED
    assert progressed.is_set() and real._active.operation_id == PICK_OP
    assert [x[0] for x in robot.log].count('resume') == 1
    assert not any(x[0] in ('move_joint','move_cartesian','gripper') for x in robot.log)


def test_duplicate_control_replays_without_second_hardware_call():
    real, robot, _ = rig(); command = request()
    first = real.control.request(command)
    assert real.control.request(command) is first
    assert [x[0] for x in robot.log].count('pause') == 1
    command['command'] = 'resume'
    assert real.control.request(command).event is Event.CONTROL_REJECTED
    assert real.control.blocked.is_set()


def test_unknown_and_stale_control_cannot_resume():
    real, robot, _ = rig(); real.control.request(request(seq=3))
    assert real.control.request(request('resume',2)).event is Event.CONTROL_REJECTED
    command=request('resume',4); command['operation_id']=str(uuid4())
    assert real.control.request(command).event is Event.CONTROL_REJECTED
    assert not any(x[0]=='resume' for x in robot.log)


@pytest.mark.parametrize('bad',['stop_not_verified_feedback_timeout','transport failure'])
def test_stop_failure_never_claims_confirmed_pause(bad):
    real, robot, _ = rig();robot.observe_stopped=lambda:bad
    event=real.control.request(request())
    assert event.event is Event.CONTROL_FAILED
    assert not json.loads(event.message)['stop_verified']
    assert real.control.blocked.is_set()
    assert real.control.request(request('resume',2)).event is Event.CONTROL_FAILED


def test_legacy_stop_failure_does_not_publish_paused():
    real, robot, _ = rig();robot.observe_stopped=lambda:'stop_not_verified_feedback_timeout'
    assert real.pause().event is Event.CONTROL_FAILED


@pytest.mark.parametrize('failure',['expired','failed','gripper_changed','no_object','restart'])
def test_resume_rejects_expiry_failure_changed_or_unknown_holding(failure):
    real, robot, state = rig();real.control.request(request())
    if failure=='expired':
        def expired():raise BackendFailure('CAMERA_NOT_READY','source expired')
        real.control.register(real._active,expired)
    elif failure=='failed':real._recovery_required=True
    elif failure=='gripper_changed':state.gripper_position=14
    elif failure=='no_object':real._held=object()
    elif failure=='restart':real.control.checks.clear()
    result=real.control.request(request('resume',2))
    assert result.event in (Event.CONTROL_FAILED,Event.CONTROL_REJECTED)
    assert real.control.blocked.is_set()
    assert not any(x[0]=='resume' for x in robot.log)


def test_completion_during_pause_is_retained_but_new_operation_is_rejected():
    real, robot, _ = rig();op=real._active
    real.control.request(request())
    terminal=real._event(op,phase='DONE',event=Event.OPERATION_COMPLETED)
    real._completed[PICK_OP]=('fingerprint',terminal);real._active=None
    new=real.execute(pick(str(uuid4())))
    assert new.event is Event.REQUEST_REJECTED
    assert real.control.request(request('resume',2)).event is Event.RESUME_CONFIRMED
    assert real._completed[PICK_OP][1] is terminal


def test_confirmed_pause_excluded_from_operation_clock_only():
    real, _, _ = rig();real.control.request(request())
    before=real.control.clock(); wall=time.monotonic()
    time.sleep(.03)
    assert abs(real.control.clock()-before)<.01
    assert time.monotonic()-wall>=.02
    real.control.request(request('resume',2))
    assert abs(real.control.clock()-before)<.02


def test_uncommissioned_control_never_calls_hardware():
    real, robot, _ = rig(False)
    assert real.control.request(request()).event is Event.CONTROL_REJECTED
    assert not robot.log and not real.control.blocked.is_set()


def test_failed_terminal_cannot_be_reclassified_as_resume():
    real, robot, _ = rig();op=real._active
    real.control.request(request())
    terminal=real._event(op,phase='GRASP',event=Event.OPERATION_FAILED,error_code='GRIPPER_FAILED')
    real._completed[PICK_OP]=('fingerprint',terminal);real._active=None
    assert real.control.request(request('resume',2)).event is Event.CONTROL_REJECTED
    assert real._completed[PICK_OP][1] is terminal
