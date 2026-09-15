"""Drive the real feedback loop with distinct simulated controller samples."""
from types import SimpleNamespace
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'vision_assembly/scripts'))
from fr5_process_sequences import real_precision_steps as module
from fr5_process_sequences.real_backend import BackendFailure


def executor(monkeypatch, phase, status, *, duplicate=False, position=14, fault=0):
    clock = SimpleNamespace(now=0.)
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: clock.now, time=lambda: clock.now))
    node = module.PortExecutor.__new__(module.PortExecutor)
    node.gripper_phase = phase
    node.backend = SimpleNamespace(_assert_not_paused=lambda: None, _gripper_timeout_sec=3.)
    sent = []
    def command(*args): sent.append(args)
    node.robot = SimpleNamespace(move_profiled_gripper=command)
    # Override the property with a small test subclass, preserving gripper().
    class Sim(module.PortExecutor):
        @property
        def state_sequence(self): return self.sequence
    node.__class__ = Sim
    node.sequence = 0
    def state():
        clock.now += .1
        if not sent or not duplicate: node.sequence += 1
        done = status(len(sent), clock.now) if callable(status) else status
        return SimpleNamespace(gripper_feedback_valid=True,
            gripperfaultnum=fault if sent else 0, grippererro=0,
            grip_motion_done=done, robot_motion_done=1,
            gripper_position=position, **{'cart_'+a+'_cur_pos':0. for a in 'xyzabc'})
    node.spin_state = state
    return node, sent


@pytest.mark.parametrize('phase', ['PREOPEN', 'RELEASE'])
@pytest.mark.parametrize('status', [1, 2])
def test_open_release_accept_completed_feedback(monkeypatch, phase, status):
    node, sent = executor(monkeypatch, phase, status)
    node.gripper(14, {})
    assert len(sent) == 1
    assert node.last_gripper_verification['continuous_feedback_verified']
    assert not node.last_gripper_verification['physical_holding_verified']


def test_close_without_object_is_explicit_failure(monkeypatch):
    node, sent = executor(monkeypatch, 'GRASP', 2)
    with pytest.raises(BackendFailure, match='GRASP_OBJECT_NOT_DETECTED'):
        node.gripper(14, {})
    assert len(sent) == 1
    assert node.last_gripper_verification['actual_position'] == 14
    assert node.last_gripper_verification['grip_motion_done'] == 2


def test_close_with_object_requires_continuous_feedback(monkeypatch):
    node, _ = executor(monkeypatch, 'GRASP', 1)
    node.gripper(14, {})
    assert node.last_gripper_verification['continuous_feedback_verified']


@pytest.mark.parametrize('status,duplicate,position', [(0,False,14),(1,True,14),(1,False,15)])
def test_busy_repeated_or_wrong_position_cannot_pass(monkeypatch,status,duplicate,position):
    node, _ = executor(monkeypatch, 'GRASP', status, duplicate=duplicate, position=position)
    with pytest.raises(BackendFailure, match='GRIPPER_FEEDBACK_TIMEOUT'):
        node.gripper(14, {})


@pytest.mark.parametrize('status,fault,reason', [(3,0,'unknown gripper'),(1,1,'feedback/fault')])
def test_unknown_status_and_fault_cannot_pass(monkeypatch,status,fault,reason):
    node, _ = executor(monkeypatch, 'GRASP', status, fault=fault)
    with pytest.raises(BackendFailure, match=reason): node.gripper(14, {})


def test_transient_no_object_can_settle_to_detected(monkeypatch):
    node, _ = executor(monkeypatch, 'GRASP', lambda sent, now: 2 if now < 1.3 else 1)
    node.gripper(14, {})
    assert node.last_gripper_verification['controller_object_detected']


def test_unknown_phase_sends_no_command(monkeypatch):
    node, sent = executor(monkeypatch, 'UNKNOWN', 1)
    with pytest.raises(BackendFailure, match='unknown gripper phase'): node.gripper(14,{})
    assert not sent
