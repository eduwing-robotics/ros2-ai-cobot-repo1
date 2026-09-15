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
        'heartbeat_timeout': 0.15,
        'duplicate_cmd_publisher': False,
        'command_receiver_connected': True,
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


def test_stale_status_timestamp_does_not_stop_a_move():
    stale_ready = context(ready=Signal(True, NOW - 1.0))
    assert moving_fault_reason(stale_ready, 'assembly', NOW) is None


def test_missing_status_timestamp_does_not_block_start():
    accepted, reason = validate_start_request(
        'assembly',
        context(
            ready=Signal(True, 0.0),
            assembly_trigger=Signal(False, 0.0),
        ),
        NOW,
    )
    assert accepted and reason == 'accepted'


def test_missing_robot_receiver_blocks_start_explicitly():
    accepted, reason = validate_start_request(
        'assembly', context(command_receiver_connected=False), NOW
    )
    assert not accepted
    assert 'receiver' in reason and '/cmd_vel' in reason


def test_receiver_preflight_requires_twist_stamped_compatibility(remote):
    remote._last_command_receiver_check = 0.0
    remote.get_subscriptions_info_by_topic.return_value = [
        SimpleNamespace(topic_type='geometry_msgs/msg/Twist')
    ]
    assert not remote._command_receiver_exists()
    remote._last_command_receiver_check = 0.0
    remote.get_subscriptions_info_by_topic.return_value = [
        SimpleNamespace(topic_type='geometry_msgs/msg/TwistStamped')
    ]
    assert remote._command_receiver_exists()


@pytest.mark.parametrize('station', ['assembly', 'inspection'])
def test_motion_without_fr5_permission(remote, station):
    if station == 'inspection':
        remote.state = ASSEMBLY_STOP
    assert remote._request_move(station, SimpleNamespace()).success
    # Exceed the old 250 ms FR5 deadline while keeping vision fresh.
    remote._now.return_value = NOW + 0.5
    remote.ready = Signal(True, NOW + 0.5)
    remote.triggers[station] = Signal(False, NOW + 0.5)
    remote._control_tick()
    assert remote.moving and remote.commands[-1] == -0.10
    remote._publish_state()
    payload = json.loads(remote.state_publisher.publish.call_args.args[0].data)
    assert payload['fr5_interlock_required'] is False
    assert payload['fr5_clear'] is False
    assert payload['fr5_clear_fresh'] is False
    remote._trigger_callback(station, SimpleNamespace(data=True))
    assert not remote.moving and remote.commands[-1] == 0.0


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
    _arrival_callback = ConveyorRemoteServer._arrival_callback
    _current_arrival = ConveyorRemoteServer._current_arrival
    _check_arrival = ConveyorRemoteServer._check_arrival
    _start_context = ConveyorRemoteServer._start_context
    _other_command_publisher_exists = ConveyorRemoteServer._other_command_publisher_exists
    _command_receiver_exists = ConveyorRemoteServer._command_receiver_exists
    _publish_command = ConveyorRemoteServer._publish_command
    _publish_state = ConveyorRemoteServer._publish_state
    _auto_idle_if_empty = ConveyorRemoteServer._auto_idle_if_empty
    _control_tick = ConveyorRemoteServer._control_tick
    _ready_callback = ConveyorRemoteServer._ready_callback
    _trigger_callback = ConveyorRemoteServer._trigger_callback
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
        self.live_arrivals = {}
        self.command_speed = -0.10
        self.cmd_topic = '/cmd_vel'
        self.command_publisher = SimpleNamespace(
            topic_name='/cmd_vel', publish=Mock()
        )
        self.state_publisher = SimpleNamespace(publish=Mock())
        self.moving_publisher = SimpleNamespace(publish=Mock())
        self.ready = Signal(True, NOW)
        self.triggers = {name: Signal(False, NOW) for name in ('assembly', 'inspection')}
        self.heartbeat_timeout = 0.15
        self._arrival_evidence_max_age = 0.5
        self._command_receiver_connected = True
        self._last_command_receiver_check = NOW
        self.motion_timeout = 30.0
        self._now = Mock(return_value=NOW)
        self.get_name = Mock(return_value='conveyor_remote_server')
        self.get_namespace = Mock(return_value='/')
        self.own_endpoint = SimpleNamespace(
            node_name='conveyor_remote_server', node_namespace='/'
        )
        self.get_publishers_info_by_topic = Mock(return_value=[self.own_endpoint])
        self.get_subscriptions_info_by_topic = Mock(return_value=[
            SimpleNamespace(topic_type='geometry_msgs/msg/TwistStamped')
        ])
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


def visual_arrival(remote, station='assembly'):
    from vision_server.conveyor_arrival import LiveArrival
    observer = LiveArrival()
    now_ns = remote.get_clock().now().nanoseconds
    for delta in range(8, -1, -1):
        stamp = now_ns - delta*50_000_000
        observer.set_motor(dict(timestamp_ns=stamp, state=remote.state, moving=False,
            command_linear_x_mps=0.0, server_instance_id=remote.server_instance_id,
            motion_id=remote.motion_id), stamp)
        observer.observe(stamp, stamp, {station:[[0., 200., 300., 100., 80.]]})
    return observer.snapshot(station, now_ns)


@pytest.mark.parametrize('station', ['assembly', 'inspection'])
def test_already_arrived_request_is_no_motion_no_new_id(remote, station):
    if station == 'inspection':
        remote.state = ASSEMBLY_STOP
    assert remote._request_move(station, SimpleNamespace()).success
    remote._trigger_callback(station, SimpleNamespace(data=True))
    payload = visual_arrival(remote, station)
    remote._arrival_callback(station, SimpleNamespace(data=json.dumps(payload)))
    before = (remote.motion_id, remote.motion_sequence, remote.arrival.copy(),
              remote.motion_started_at, remote.commands[:], remote.state)
    for _ in range(3):
        response = remote._request_move(station, SimpleNamespace())
        result = json.loads(response.message)
        assert response.success and result['already_arrived'] and result['completed']
        assert result['motion_id'] == before[0]
    assert (remote.motion_id, remote.motion_sequence, remote.arrival,
            remote.motion_started_at, remote.commands, remote.state) == before


@pytest.mark.parametrize('problem', ['no_image', 'old_image', 'old_motor', 'wrong_instance',
    'wrong_motion', 'wrong_station', 'moving', 'no_arrival_record', 'not_armed', 'not_ready',
    'stale_received', 'duplicate_publisher'])
def test_stopped_label_alone_or_bad_visual_evidence_cannot_skip_move(remote, problem):
    remote._request_move('assembly', SimpleNamespace())
    remote._trigger_callback('assembly', SimpleNamespace(data=True))
    p = visual_arrival(remote)
    if problem == 'no_image': p['at_station'] = False
    if problem == 'old_image': p['source_image_timestamp_ns'] -= 1_000_000_000
    if problem == 'old_motor': p['motor_state']['timestamp_ns'] -= 1_000_000_000
    if problem == 'wrong_instance': p['motor_state']['server_instance_id'] = 'old-server'
    if problem == 'wrong_motion': p['motor_state']['motion_id'] = 'old-motion'
    if problem == 'wrong_station': p['station'] = 'inspection'
    if problem == 'moving': p['motor_state']['moving'] = True
    if problem == 'no_arrival_record': remote.arrival = None
    if problem == 'not_armed': remote.armed = False
    if problem == 'not_ready': remote.ready = Signal(False, NOW)
    if problem == 'duplicate_publisher':
        remote.get_publishers_info_by_topic.return_value = [remote.own_endpoint]*2
    remote._arrival_callback('assembly', SimpleNamespace(data=json.dumps(p)))
    if problem == 'stale_received': remote.live_arrivals['assembly'] = (p, NOW-1)
    assert not remote._request_move('assembly', SimpleNamespace()).success
    assert remote.state == ASSEMBLY_STOP and remote.commands[-1] == 0.0


def test_arrival_query_is_read_only_and_expires(remote):
    remote._request_move('assembly', SimpleNamespace())
    remote._trigger_callback('assembly', SimpleNamespace(data=True))
    remote._arrival_callback('assembly', SimpleNamespace(data=json.dumps(visual_arrival(remote))))
    before = (remote.commands[:], remote.state, remote.motion_id)
    assert remote._check_arrival('assembly', SimpleNamespace()).success
    remote._now.return_value = NOW+1
    assert not remote._check_arrival('assembly', SimpleNamespace()).success
    assert (remote.commands, remote.state, remote.motion_id) == before


@pytest.mark.parametrize('event', ['ready', 'assembly'])
def test_callback_stop_is_immediate_and_never_auto_resumes(remote, event):
    remote._request_move('assembly', SimpleNamespace())
    if event == 'ready':
        remote._ready_callback(SimpleNamespace(data=False))
        remote._ready_callback(SimpleNamespace(data=True))
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
    # Reset clears controller state; delayed status timestamps are irrelevant.
    remote._now.return_value = NOW + 1.0
    assert remote._request_move('assembly', SimpleNamespace()).success
    assert remote.moving
    remote._stop(None, SimpleNamespace())


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


def test_idle_control_tick_is_passive_for_manual_teleop(remote):
    # An operator publisher must be able to own /cmd_vel while the remote
    # state machine is idle.  The remote server still emits zero on an
    # explicit hold/fault, but must not stream zero at 50 Hz from IDLE.
    remote._control_tick()
    assert remote.commands == []


def test_rejected_move_does_not_interrupt_another_cmd_vel_owner(remote):
    remote.get_publishers_info_by_topic.return_value = [
        remote.own_endpoint,
        SimpleNamespace(node_name='teleop_keyboard', node_namespace='/'),
    ]
    response = remote._request_move('assembly', SimpleNamespace())
    assert not response.success
    assert 'another /cmd_vel publisher' in response.message
    assert remote.commands == []


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


@pytest.mark.parametrize('fault', ['disarmed', 'bad_target', 'duplicate', 'receiver_missing'])
def test_moving_safety_faults_latch_and_hold(remote, fault):
    remote._request_move('assembly', SimpleNamespace())
    if fault == 'disarmed':
        remote.armed = False
    elif fault == 'bad_target':
        remote.target_station = 'typo'
    elif fault == 'receiver_missing':
        remote.get_subscriptions_info_by_topic.return_value = []
        remote._last_command_receiver_check = 0.0
    else:
        remote.get_publishers_info_by_topic.return_value *= 2
    remote._control_tick()
    assert remote.state == FAULT
    assert remote.commands[-1] == 0.0


def test_stale_status_does_not_latch_fault_while_moving(remote):
    remote._request_move('assembly', SimpleNamespace())
    remote.ready = Signal(True, NOW - 100.0)
    remote.triggers['assembly'] = Signal(False, NOW - 100.0)
    remote._control_tick()
    assert remote.state == MOVING_TO_ASSEMBLY
    assert remote.commands[-1] == -0.10


def test_duplicate_publisher_with_identical_node_identity_blocks_start(remote):
    remote.get_publishers_info_by_topic.return_value *= 2
    assert not remote._request_move('assembly', SimpleNamespace()).success
    assert remote.state == IDLE and remote.commands == []


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


def empty_evidence(remote):
    now = remote.get_clock().now().nanoseconds
    for station in ('assembly', 'inspection'):
        payload = dict(station=station, regions_empty=True, at_station=False,
                       empty_frames=41, empty_since_ns=now-2_000_000_000,
                       timestamp_ns=now, source_image_timestamp_ns=now,
                       motor_state=dict(timestamp_ns=now, state=remote.state,
                                        moving=False, command_linear_x_mps=0,
                                        server_instance_id=remote.server_instance_id,
                                        motion_id=remote.motion_id))
        remote.live_arrivals[station] = (payload, NOW)


def fast_empty_evidence(remote):
    """Fresh short-window evidence after an operator returns the board upstream."""
    now = remote.get_clock().now().nanoseconds
    for station in ('assembly', 'inspection'):
        payload = dict(
            station=station,
            regions_empty=False,
            restart_regions_empty=True,
            at_station=False,
            empty_frames=1,
            empty_since_ns=now,
            restart_empty_frames=5,
            restart_empty_since_ns=now-400_000_000,
            timestamp_ns=now,
            source_image_timestamp_ns=now,
            motor_state=dict(
                timestamp_ns=now,
                state=remote.state,
                moving=False,
                command_linear_x_mps=0,
                server_instance_id=remote.server_instance_id,
                motion_id=remote.motion_id,
            ),
        )
        remote.live_arrivals[station] = (payload, NOW)


@pytest.mark.parametrize('state', [ASSEMBLY_STOP, INSPECTION_STOP])
def test_empty_stations_clear_old_completion_then_allow_new_assembly(remote, state):
    remote.state = state
    remote.motion_id = 'old'
    remote.arrival = {'motion_id': 'old'}
    remote.motion_sequence = 4
    empty_evidence(remote)
    remote._control_tick()
    assert remote.state == IDLE and remote.arrival is None and remote.motion_id is None
    assert remote.commands == []
    assert remote.motion_sequence == 4
    assert remote._request_move('assembly', SimpleNamespace()).success
    assert remote.motion_id == 'test-server:5'


def test_new_assembly_request_clears_stale_stop_after_short_empty_window(remote):
    remote.state = ASSEMBLY_STOP
    remote.motion_id = 'old'
    remote.arrival = {'station': 'assembly', 'motion_id': 'old'}
    remote.motion_sequence = 4
    remote.triggers['assembly'] = Signal(True, NOW)
    remote.triggers['inspection'] = Signal(True, NOW)
    fast_empty_evidence(remote)

    response = remote._request_move('assembly', SimpleNamespace())

    assert response.success
    assert remote.state == MOVING_TO_ASSEMBLY
    assert remote.motion_id == 'test-server:5'
    assert remote.commands == [-0.10]
    assert remote.triggers['assembly'] == Signal(False, NOW)
    assert remote.triggers['inspection'] == Signal(False, NOW)


def test_explicit_retry_can_recover_manual_stop_but_not_fault(remote):
    remote.state = MANUAL_STOP
    remote.motion_id = 'old'
    remote.arrival = None
    remote.motion_sequence = 4
    fast_empty_evidence(remote)

    response = remote._request_move('assembly', SimpleNamespace())

    assert response.success
    assert remote.state == MOVING_TO_ASSEMBLY
    assert remote.motion_id == 'test-server:5'

    remote._stop(None, SimpleNamespace())
    remote.state = FAULT
    remote.motion_id = 'faulted'
    fast_empty_evidence(remote)
    response = remote._request_move('assembly', SimpleNamespace())
    assert not response.success
    assert remote.state == FAULT


@pytest.mark.parametrize('bad', ['manual', 'fault', 'moving', 'missing', 'stale',
                                'wrong_server', 'wrong_motion', 'unknown', 'not_ready', 'publisher'])
def test_empty_auto_idle_does_not_bypass_invalid_evidence_or_stops(remote, bad):
    remote.state = ASSEMBLY_STOP
    remote.motion_id = 'old'
    if bad == 'manual': remote.state = MANUAL_STOP
    if bad == 'fault': remote.state = FAULT
    if bad == 'moving': remote.target_station = 'assembly'
    empty_evidence(remote)
    payload = remote.live_arrivals['assembly'][0]
    if bad == 'missing': remote.live_arrivals.pop('inspection')
    if bad == 'stale': payload['source_image_timestamp_ns'] -= 1_000_000_000
    if bad == 'wrong_server': payload['motor_state']['server_instance_id'] = 'other'
    if bad == 'wrong_motion': payload['motor_state']['motion_id'] = 'other'
    if bad == 'unknown': payload['regions_empty'] = False
    if bad == 'not_ready': remote.ready = Signal(False, NOW)
    if bad == 'publisher': remote.get_publishers_info_by_topic.return_value *= 2
    before = remote.state
    assert not remote._auto_idle_if_empty()
    assert remote.state == before and remote.motion_id == 'old'
