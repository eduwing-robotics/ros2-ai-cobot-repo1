from types import SimpleNamespace
import threading

import pytest

from vision_server.conveyor_stop_lease import ConveyorStopLease
from vision_server.orchestration_action_server import OrchestrationActionServer
from vision_server.unity_calibration_server import UnityCalibrationServer
from test_orchestration_contract import pcb_payload


class Clock:
    def __init__(self):
        self.mono = 100.0
        self.wall = 10_000_000_000

    def advance(self, seconds):
        self.mono += seconds
        self.wall += int(seconds * 1_000_000_000)

    def info(self, writer=1, offset_ns=0):
        return dict(publisher_gid=bytes([writer] * 16),
                    source_timestamp=self.wall + offset_ns)


def lease_fixture():
    clock = Clock()
    lease = ConveyorStopLease(monotonic=lambda: clock.mono, wall_time_ns=lambda: clock.wall)
    return lease, clock


def ready(lease, clock, writer=1):
    lease.observe(True, clock.info(writer))
    clock.advance(.2)
    lease.observe(True, clock.info(writer))
    assert lease.current_session() is not None
    return lease.current_session()


def test_no_message_and_single_true_cannot_authorize():
    lease, clock = lease_fixture()
    assert lease.current_session() is None
    lease.observe(True, clock.info())
    assert lease.current_session() is None
    clock.advance(.2)
    lease.observe(True, clock.info())
    assert lease.current_session() is not None


def test_attribute_metadata_bindings_are_also_supported():
    lease, clock = lease_fixture()
    lease.observe(True, SimpleNamespace(**clock.info()))
    clock.advance(.2)
    lease.observe(True, SimpleNamespace(**clock.info()))
    assert lease.current_session() is not None


def test_lost_heartbeat_and_same_writer_restart_require_a_new_session():
    lease, clock = lease_fixture()
    old = ready(lease, clock)
    clock.advance(1.001)
    assert not lease.permits(old)
    lease.observe(True, clock.info())
    assert lease.current_session() is None
    clock.advance(.2)
    lease.observe(True, clock.info())
    assert lease.current_session() is not None
    assert not lease.permits(old)


def test_false_and_publisher_restart_revoke_the_original_session():
    lease, clock = lease_fixture()
    old = ready(lease, clock)
    clock.advance(.2)
    lease.observe(False, clock.info())
    assert not lease.permits(old)
    clock.advance(.2)
    stopped_again = ready(lease, clock)
    assert stopped_again != old
    clock.advance(.2)
    lease.observe(True, clock.info(writer=2))
    assert lease.current_session() is None
    assert not lease.permits(stopped_again)
    clock.advance(.2)
    lease.observe(True, clock.info(writer=2))
    assert lease.current_session() not in (None, old, stopped_again)


def test_delayed_old_publisher_cannot_reclaim_a_restarted_session():
    lease, clock = lease_fixture()
    ready(lease, clock)
    clock.advance(.2)
    ready(lease, clock, writer=2)
    for _ in range(3):
        clock.advance(.1)
        lease.observe(True, clock.info(writer=1))
        assert lease.current_session() is None


def test_detected_clock_expiry_cannot_revive_without_new_heartbeats():
    lease, clock = lease_fixture()
    old = ready(lease, clock)
    clock.wall += 2_000_000_000
    assert not lease.permits(old)
    clock.wall -= 2_000_000_000
    assert not lease.permits(old)


@pytest.mark.parametrize('kind', ['stale', 'future', 'duplicate', 'reversed', 'missing'])
def test_invalid_dds_evidence_cannot_extend_a_true_lease(kind):
    lease, clock = lease_fixture()
    old = ready(lease, clock)
    offsets = {'stale': -2_000_000_000, 'future': 1, 'duplicate': 0, 'reversed': -1}
    info = None if kind == 'missing' else clock.info(offset_ns=offsets[kind])
    lease.observe(True, info)
    assert not lease.permits(old)
    assert lease.current_session() is None


@pytest.mark.parametrize('which', ['wall', 'mono'])
def test_either_clock_expiry_blocks_stopped_evidence(which):
    lease, clock = lease_fixture()
    old = ready(lease, clock)
    if which == 'wall':
        clock.wall += 2_000_000_000
    else:
        clock.mono += 2
    assert not lease.permits(old)


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_heartbeat_ttl_must_be_finite_and_positive(value):
    with pytest.raises(ValueError):
        ConveyorStopLease(value)


@pytest.mark.parametrize('kind', ['action', 'unity'])
def test_both_ros_callbacks_use_metadata_for_the_lease(kind):
    lease, clock = lease_fixture()
    if kind == 'action':
        node = object.__new__(OrchestrationActionServer)
        node._conveyor_lease = lease
        node._lock = threading.Lock()
        callback = node._conveyor_callback
    else:
        node = object.__new__(UnityCalibrationServer)
        node.conveyor_lease = lease
        callback = node._conveyor
    callback(SimpleNamespace(data=True), clock.info())
    assert lease.current_session() is None
    clock.advance(.2)
    callback(SimpleNamespace(data=True), clock.info())
    assert lease.current_session() is not None


@pytest.mark.parametrize('change', ['none', 'expire', 'false', 'restart'])
def test_action_calibration_requires_the_same_live_session_after_snapshot(monkeypatch, change):
    from vision_server import orchestration_action_server as module
    lease, clock = lease_fixture()
    ready(lease, clock)
    node = object.__new__(OrchestrationActionServer)
    node._conveyor_lease = lease
    node._lock = threading.Lock()
    node.pcb_config = dict(require_conveyor_stopped=True,
        expected_product_code='board', expected_product_version='r1',
        maximum_hole_fit_rms_mm=1.5, maximum_plane_mad_mm=2., minimum_plane_inliers=200)
    node.timeout_sec = 5
    node.maximum_age_sec = 2.5
    node._latest = lambda _: (pcb_payload(), None)
    node.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=clock.wall))
    monkeypatch.setattr(module.rclpy, 'ok', lambda: True)
    def snapshot(*args, **kwargs):
        clock.advance(1.01 if change == 'expire' else .2)
        if change == 'false':
            lease.observe(False, clock.info())
        elif change == 'restart':
            ready(lease, clock, writer=2)
        return object()
    monkeypatch.setattr(module, 'pcb_snapshot', snapshot)
    completed = []
    node._complete_pcb = lambda *args: completed.append(args)
    goal = SimpleNamespace(request=SimpleNamespace(job_id='test', product_code='board', product_version='r1'),
        is_cancel_requested=False, publish_feedback=lambda _: None, abort=lambda: None)
    result = node._execute_pcb(goal)
    if change == 'none':
        assert len(completed) == 1
    else:
        assert result.error_code == 'CONVEYOR_NOT_STOPPED'
        assert not result.success
        assert completed == []
