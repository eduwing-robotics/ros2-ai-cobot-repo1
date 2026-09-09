import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from geometry_msgs.msg import TwistStamped

import vision_server.conveyor_remote_server as remote_module

from vision_server.conveyor_remote_server import (
    ASSEMBLY_STOP,
    ConveyorRemoteServer,
    FAULT,
    IDLE,
    INSPECTION_STOP,
    MANUAL_STOP,
    MOVING_TO_ASSEMBLY,
    Signal,
    StartContext,
    moving_fault_reason,
    signal_is_fresh,
    validate_start_request,
)


NOW = 100.0


def context(**overrides):
    values = {
        'armed': True,
        'state': IDLE,
        'ready': Signal(True, NOW - 0.01),
        'assembly_trigger': Signal(False, NOW - 0.01),
        'inspection_trigger': Signal(False, NOW - 0.01),
        'fr5_clear': Signal(True, NOW - 0.01),
        'heartbeat_timeout': 0.15,
        'fr5_timeout': 0.25,
        'require_fr5_clear': True,
        'duplicate_cmd_publisher': False,
    }
    values.update(overrides)
    return StartContext(**values)


def test_fresh_signal_boundary():
    assert signal_is_fresh(Signal(True, NOW - 0.15), NOW, 0.15)
    assert not signal_is_fresh(Signal(True, NOW - 0.151), NOW, 0.15)
    assert not signal_is_fresh(Signal(True, 0.0), NOW, 0.15)


def test_assembly_start_requires_all_interlocks():
    assert validate_start_request('assembly', context(), NOW) == (
        True,
        'accepted',
    )
    accepted, reason = validate_start_request(
        'assembly', context(ready=Signal(False, NOW)), NOW
    )
    assert not accepted
    assert 'not ready' in reason
    accepted, reason = validate_start_request(
        'assembly', context(fr5_clear=Signal(False, NOW)), NOW
    )
    assert not accepted
    assert 'FR5' in reason


def test_remote_motion_must_be_explicitly_armed():
    accepted, reason = validate_start_request(
        'assembly', context(armed=False), NOW
    )
    assert not accepted
    assert 'disarmed' in reason


def test_active_target_trigger_blocks_start():
    accepted, reason = validate_start_request(
        'assembly', context(assembly_trigger=Signal(True, NOW)), NOW
    )
    assert not accepted
    assert 'already active' in reason


def test_inspection_requires_assembly_stop_sequence():
    accepted, reason = validate_start_request('inspection', context(), NOW)
    assert not accepted
    assert 'assembly-stop' in reason
    assert validate_start_request(
        'inspection', context(state=ASSEMBLY_STOP), NOW
    )[0]
    assert validate_start_request(
        'inspection',
        context(assembly_trigger=Signal(True, NOW)),
        NOW,
    )[0]


def test_next_assembly_is_allowed_after_inspection_stop():
    assert validate_start_request(
        'assembly', context(state=INSPECTION_STOP), NOW
    )[0]


@pytest.mark.parametrize('state', [FAULT, MANUAL_STOP, MOVING_TO_ASSEMBLY])
def test_unsafe_controller_states_reject_new_move(state):
    assert not validate_start_request('assembly', context(state=state), NOW)[0]


def test_duplicate_cmd_vel_publisher_rejects_start():
    accepted, reason = validate_start_request(
        'assembly', context(duplicate_cmd_publisher=True), NOW
    )
    assert not accepted
    assert '/cmd_vel' in reason


def test_moving_watchdog_reports_stale_vision_and_fr5():
    stale_ready = context(ready=Signal(True, NOW - 1.0))
    assert 'S22' in moving_fault_reason(stale_ready, 'assembly', NOW)
    stale_fr5 = context(fr5_clear=Signal(True, NOW - 1.0))
    assert 'FR5' in moving_fault_reason(stale_fr5, 'assembly', NOW)


def test_fr5_interlock_can_only_be_disabled_by_explicit_parameter():
    no_fr5 = context(
        require_fr5_clear=False,
        fr5_clear=Signal(False, 0.0),
    )
    assert validate_start_request('assembly', no_fr5, NOW)[0]


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('field', ['received_at', 'now', 'timeout'])
def test_nonfinite_freshness_never_authorizes_motion(field, bad):
    values = dict(received_at=NOW, now=NOW, timeout=0.15)
    values[field] = bad
    assert not signal_is_fresh(
        Signal(True, values['received_at']), values['now'], values['timeout']
    )


@pytest.mark.parametrize('timeout', [0.0, -1e-10, -1.0])
def test_nonpositive_freshness_window_is_invalid(timeout):
    assert not signal_is_fresh(Signal(True, NOW), NOW, timeout)


def test_future_heartbeat_is_not_fresh():
    assert not signal_is_fresh(Signal(True, NOW + 0.001), NOW, 0.15)


class RemoteHarness:
    """Bind callbacks to plain Python state; never create a ROS Node/context."""

    moving = ConveyorRemoteServer.moving
    _request_move = ConveyorRemoteServer._request_move
    _start_context = ConveyorRemoteServer._start_context
    _other_command_publisher_exists = ConveyorRemoteServer._other_command_publisher_exists
    _publish_command = ConveyorRemoteServer._publish_command
    _publish_state = ConveyorRemoteServer._publish_state
    _control_tick = ConveyorRemoteServer._control_tick
    _ready_callback = ConveyorRemoteServer._ready_callback
    _trigger_callback = ConveyorRemoteServer._trigger_callback
    _fr5_clear_callback = ConveyorRemoteServer._fr5_clear_callback
    _hold = ConveyorRemoteServer._hold
    _fault = ConveyorRemoteServer._fault
    _stop = ConveyorRemoteServer._stop
    _reset = ConveyorRemoteServer._reset
    emergency_stop = ConveyorRemoteServer.emergency_stop

    def __init__(self):
        self.armed = True
        self.state = IDLE
        self.target_station = ''
        self.reason = 'test'
        self.motion_started_at = 0.0
        self.server_instance_id = 'test-server'
        self.motion_sequence = 0
        self.motion_id = None
        self.arrival = None
        self.command_speed = -0.10
        self.cmd_topic = '/cmd_vel'
        self.command_publisher = SimpleNamespace(
            topic_name='/cmd_vel', publish=Mock()
        )
        self.state_publisher = SimpleNamespace(publish=Mock())
        self.moving_publisher = SimpleNamespace(publish=Mock())
        self.ready = Signal(True, NOW)
        self.fr5_clear = Signal(True, NOW)
        self.triggers = {name: Signal(False, NOW) for name in ('assembly', 'inspection')}
        self.heartbeat_timeout = 0.15
        self.fr5_timeout = 0.25
        self.require_fr5_clear = True
        self.motion_timeout = 30.0
        self._now = Mock(return_value=NOW)
        self.get_name = Mock(return_value='conveyor_remote_server')
        self.get_namespace = Mock(return_value='/')
        self.own_endpoint = SimpleNamespace(
            node_name='conveyor_remote_server', node_namespace='/'
        )
        self.get_publishers_info_by_topic = Mock(return_value=[self.own_endpoint])
        self.get_logger = Mock(return_value=Mock())
        clock_value = SimpleNamespace(
            nanoseconds=int(NOW * 1e9),
            to_msg=lambda: TwistStamped().header.stamp,
        )
        self.get_clock = Mock(return_value=SimpleNamespace(now=lambda: clock_value))

    @property
    def commands(self):
        return [
            call.args[0].twist.linear.x
            for call in self.command_publisher.publish.call_args_list
        ]


@pytest.fixture
def remote(monkeypatch):
    # A future accidental call to ROS startup must fail instead of touching DDS.
    def forbidden(*args, **kwargs):
        pytest.fail('offline conveyor tests must never initialize ROS')

    monkeypatch.setattr(remote_module.rclpy, 'init', forbidden)
    monkeypatch.setattr(remote_module.Node, '__init__', forbidden)
    return RemoteHarness()


@pytest.mark.parametrize('duplicate_station', ['assembly', 'inspection', 'invalid'])
def test_rejected_move_does_not_stop_restart_or_extend_active_move(remote, duplicate_station):
    assert remote._request_move('assembly', SimpleNamespace()).success
    before = (remote.state, remote.target_station, remote.motion_started_at, remote.reason)
    remote._now.return_value = NOW + 0.05
    response = remote._request_move(duplicate_station, SimpleNamespace())
    assert not response.success
    assert (remote.state, remote.target_station, remote.motion_started_at, remote.reason) == before
    assert remote.commands == [-0.10]
    remote._control_tick()
    assert remote.commands == [-0.10, -0.10]


@pytest.mark.parametrize('event', ['ready', 'fr5', 'assembly'])
def test_callback_stop_is_immediate_and_never_auto_resumes(remote, event):
    remote._request_move('assembly', SimpleNamespace())
    if event == 'ready':
        remote._ready_callback(SimpleNamespace(data=False))
        remote._ready_callback(SimpleNamespace(data=True))
    elif event == 'fr5':
        remote._fr5_clear_callback(SimpleNamespace(data=False))
        remote._fr5_clear_callback(SimpleNamespace(data=True))
    else:
        remote._trigger_callback('assembly', SimpleNamespace(data=True))
        remote._trigger_callback('assembly', SimpleNamespace(data=False))
    assert remote.commands == [-0.10, 0.0]
    assert remote.state == (ASSEMBLY_STOP if event == 'assembly' else FAULT)
    remote._control_tick()
    assert remote.commands[-1] == 0.0
    assert not remote.moving


@pytest.mark.parametrize('station', ['assembly','inspection'])
def test_arrival_persists_and_matches_accepted_motion(remote,station):
    if station=='inspection': remote.state=ASSEMBLY_STOP
    response=remote._request_move(station,SimpleNamespace())
    motion=json.loads(response.message)['motion_id']
    remote._trigger_callback(station,SimpleNamespace(data=True))
    remote._trigger_callback(station,SimpleNamespace(data=False))
    remote._publish_state()
    payload=json.loads(remote.state_publisher.publish.call_args.args[0].data)
    assert payload['completed_station']==station
    assert payload['arrival']['motion_id']==motion
    assert payload['moving'] is False and payload['target_station'] is None
    arrival=payload['arrival']
    remote._publish_state()
    assert json.loads(remote.state_publisher.publish.call_args.args[0].data)['arrival']==arrival
    remote._reset(None,SimpleNamespace())
    assert json.loads(remote.state_publisher.publish.call_args.args[0].data)['arrival'] is None


def test_fault_and_unrequested_trigger_never_claim_arrival(remote):
    remote._trigger_callback('assembly',SimpleNamespace(data=True))
    remote._publish_state()
    assert json.loads(remote.state_publisher.publish.call_args.args[0].data)['arrival'] is None
    remote._trigger_callback('assembly',SimpleNamespace(data=False))
    remote._request_move('assembly',SimpleNamespace())
    remote._ready_callback(SimpleNamespace(data=False))
    assert json.loads(remote.state_publisher.publish.call_args.args[0].data)['arrival'] is None


def test_stop_reset_never_restart_and_reset_during_move_is_rejected(remote):
    remote._request_move('assembly', SimpleNamespace())
    assert not remote._reset(None, SimpleNamespace()).success
    assert remote.moving
    assert remote._stop(None, SimpleNamespace()).success
    assert remote.state == MANUAL_STOP
    assert remote.target_station == '' and remote.motion_started_at == 0.0
    assert not remote._request_move('assembly', SimpleNamespace()).success
    assert remote._reset(None, SimpleNamespace()).success
    remote._control_tick()
    assert remote.state == IDLE
    assert remote.commands[0] == -0.10
    assert all(command == 0.0 for command in remote.commands[1:])
    # Reset clears controller state, not the underlying heartbeat interlocks.
    remote._now.return_value = NOW + 1.0
    assert not remote._request_move('assembly', SimpleNamespace()).success


def test_monitor_mode_only_publishes_holds_including_stop_reset_and_shutdown(remote, monkeypatch):
    remote.armed = False
    for station in ('assembly', 'inspection'):
        assert not remote._request_move(station, SimpleNamespace()).success
    remote._control_tick()
    assert remote._stop(None, SimpleNamespace()).success
    assert remote._reset(None, SimpleNamespace()).success
    monkeypatch.setattr(remote_module.rclpy, 'ok', lambda: True)
    remote.emergency_stop()
    assert remote.commands and set(remote.commands) == {0.0}
    payload = json.loads(remote.state_publisher.publish.call_args.args[0].data)
    assert payload['armed'] is False and payload['moving'] is False
    assert payload['command_linear_x_mps'] == 0.0


@pytest.mark.parametrize('bad_start', [0.0, NOW + 1.0, float('nan'), float('inf')])
def test_invalid_motion_start_time_latches_fault(remote, bad_start):
    remote._request_move('assembly', SimpleNamespace())
    remote.motion_started_at = bad_start
    remote._control_tick()
    assert remote.state == FAULT
    assert 'clock' in remote.reason
    assert remote.commands[-1] == 0.0


def test_motion_timeout_is_not_extended_by_duplicate_request(remote):
    remote._request_move('assembly', SimpleNamespace())
    # An exactly representable duration tests the boundary, not float rounding.
    remote.motion_timeout = 0.125
    remote._now.return_value = NOW + 0.125
    assert not remote._request_move('assembly', SimpleNamespace()).success
    remote._control_tick()
    assert remote.state == FAULT and remote.reason == 'motion timeout'
    assert remote.commands[-1] == 0.0


@pytest.mark.parametrize('fault', ['disarmed', 'bad_target', 'ready_stale', 'trigger_stale', 'fr5_stale', 'duplicate'])
def test_moving_watchdogs_latch_fault_and_hold(remote, fault):
    remote._request_move('assembly', SimpleNamespace())
    if fault == 'disarmed':
        remote.armed = False
    elif fault == 'bad_target':
        remote.target_station = 'typo'
    elif fault == 'ready_stale':
        remote.ready = Signal(True, NOW - 1.0)
    elif fault == 'trigger_stale':
        remote.triggers['assembly'] = Signal(False, NOW - 1.0)
    elif fault == 'fr5_stale':
        remote.fr5_clear = Signal(True, NOW - 1.0)
    else:
        remote.get_publishers_info_by_topic.return_value *= 2
    remote._control_tick()
    assert remote.state == FAULT
    assert remote.commands[-1] == 0.0
    remote._control_tick()
    assert remote.commands[-1] == 0.0


def test_duplicate_publisher_with_identical_node_identity_blocks_start(remote):
    remote.get_publishers_info_by_topic.return_value *= 2
    assert not remote._request_move('assembly', SimpleNamespace()).success
    assert remote.state == IDLE and remote.commands == [0.0]


def test_duplicate_publisher_query_uses_resolved_remapped_topic(remote):
    remote.command_publisher.topic_name = '/remapped/conveyor_cmd'
    remote._other_command_publisher_exists()
    remote.get_publishers_info_by_topic.assert_called_once_with('/remapped/conveyor_cmd')


def test_rejected_duplicate_still_faults_immediately_if_interlock_is_lost(remote):
    remote._request_move('assembly', SimpleNamespace())
    remote.get_publishers_info_by_topic.return_value *= 2
    assert not remote._request_move('assembly', SimpleNamespace()).success
    assert remote.state == FAULT
    assert remote.commands == [-0.10, 0.0]
