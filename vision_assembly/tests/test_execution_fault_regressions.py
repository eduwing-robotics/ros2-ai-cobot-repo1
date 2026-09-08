"""Failure injection only: never construct a ROS node or contact a controller."""
import json
import os
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import execute_cached_hbm_remaining as cached
import execute_full_fixed_cycle as full
import assembly_cycle_launcher as launcher
import tray_home_gate as gate
import execution_safety as contract
from test_execute_full_fixed_cycle_safety import FakeNode, gpu_item, patch_offline_runtime


def feedback(x=10.0, done=1):
    return SimpleNamespace(robot_motion_done=done, cart_x_cur_pos=x,
                           cart_y_cur_pos=20., cart_z_cur_pos=30.,
                           cart_a_cur_pos=0., cart_b_cur_pos=0., cart_c_cur_pos=0.,
                           gripper_position=18,
                           **{f'j{i}_cur_pos': 0. for i in range(1, 7)})


def bare_node(monkeypatch, mode='silent', *, done=1):
    node = object.__new__(cached.Executor)
    node.state = feedback(done=done)
    node.state_sequence = 1
    node.state_received_monotonic = 100.
    clock = SimpleNamespace(value=100., samples=0)
    monkeypatch.setattr(cached.time, 'monotonic', lambda: clock.value)
    monkeypatch.setattr(cached.rclpy, 'ok', lambda: True)
    def spin(unused, timeout_sec):
        clock.value += 0.1
        clock.samples += 1
        if mode == 'fresh':
            node.state_cb(feedback(done=done))
        elif mode == 'duplicate':
            node.state_received_monotonic = clock.value
        elif mode == 'old':
            node.state_sequence += 1
            node.state_received_monotonic = clock.value - 10
    monkeypatch.setattr(cached.rclpy, 'spin_once', spin)
    return node, clock


@pytest.mark.parametrize('mode', ['silent', 'duplicate', 'old'])
def test_precommand_matching_pose_and_repeated_sequence_never_verify(monkeypatch, mode):
    # Original review reproducer #1: matching old TCP with sequence=1.
    node, clock = bare_node(monkeypatch, mode)
    with pytest.raises(RuntimeError, match='stale|timeout'):
        node.wait_pose([10, 20, 30, 0, 0, 0], timeout_sec=1)
    assert clock.value < 101
    assert not hasattr(node, 'last_pose_verification')


@pytest.mark.parametrize('mode', ['silent', 'duplicate', 'old'])
def test_state_reads_require_both_age_and_increasing_sequence(monkeypatch, mode):
    node, _ = bare_node(monkeypatch, mode)
    with pytest.raises(RuntimeError, match='fresh FR5 state'):
        node.spin_state(timeout_sec=0.25)


def test_arrival_returns_the_exact_new_sample_it_verified(monkeypatch):
    node, _ = bare_node(monkeypatch, 'fresh')
    node.snapshot = lambda: pytest.fail('must not replace verified sample with another snapshot')
    assert node.wait_pose([10, 20, 30, 0, 0, 0], timeout_sec=1) == [10, 20, 30, 0, 0, 0]
    assert node.last_pose_verification['state_sequence'] == 2
    assert node.last_pose_verification['state_age_sec'] == 0


@pytest.mark.parametrize('command', ['MoveJ(JNT1,25,1,0)', 'MoveL(JNT1,10,1,0)',
                                    'MoveCart(1,2,3)', 'MoveGripper(1,18)'])
def test_no_motion_command_is_issued_with_stale_state(monkeypatch, command):
    node, _ = bare_node(monkeypatch)
    node.client = SimpleNamespace(call_async=lambda unused: pytest.fail('stale motion sent'))
    with pytest.raises(RuntimeError, match='fresh FR5 state'):
        node.service(command)


def test_actuator_feedback_is_refreshed_after_slow_durable_journal(monkeypatch):
    node, clock = bare_node(monkeypatch)
    node.command_event_hook = lambda *args: setattr(clock, 'value', clock.value + 1)
    node.client = SimpleNamespace(call_async=lambda unused: pytest.fail('stale motion sent after journal delay'))
    with pytest.raises(RuntimeError, match='fresh FR5 state'):
        node.service('MoveJ(JNT1,25,1,0)')


@pytest.mark.parametrize('changed_joint', [5.0, float('nan')])
def test_preflight_reference_is_checked_on_final_postjournal_sample(monkeypatch, changed_joint):
    node, clock = bare_node(monkeypatch, 'fresh')
    changed = []
    node.command_event_hook = lambda *args: changed.append(True)
    def spin(unused, timeout_sec):
        clock.value += .05
        state = feedback()
        if changed:
            state.j1_cur_pos = changed_joint
        node.state_cb(state)
    monkeypatch.setattr(cached.rclpy, 'spin_once', spin)
    sent = []
    future = SimpleNamespace(done=lambda: True, result=lambda: SimpleNamespace(cmd_res='0'))
    def send(request):
        sent.append(request.cmd_str)
        return future
    node.client = SimpleNamespace(call_async=send)
    monkeypatch.setattr(cached.rclpy, 'spin_until_future_complete', lambda *a, **kw: None)
    waypoint = full.PreflightWaypoint('HBM-01', 'pick', (10, 20, 30, 0, 0, 0), False,
                                     25, (0.,) * 6, (0.,) * 6, 20.)
    with pytest.raises(RuntimeError, match='reference drift'):
        full.move_preflighted(node, waypoint)
    assert len(sent) == 1
    assert sent[0].startswith('JNTPoint(')


def test_inspection_stops_on_lost_robot_feedback_before_reading_image(tmp_path, monkeypatch):
    node, _ = bare_node(monkeypatch)
    path = tmp_path / 'frame.json'
    path.write_text('{}')
    monkeypatch.setattr(gate, 'check_pick_removal', lambda *a: pytest.fail('image accepted without feedback'))
    with pytest.raises(RuntimeError, match='fresh FR5 state'):
        gate.wait_inventory(node, path, {}, set(), {}, picked_slot='HBM-01')


def test_stop_service_has_its_own_bounded_timeout(monkeypatch):
    node, _ = bare_node(monkeypatch)
    future = SimpleNamespace(done=lambda: False)
    calls = []
    node.client = SimpleNamespace(call_async=lambda request: future)
    monkeypatch.setattr(cached.rclpy, 'spin_until_future_complete',
                        lambda n, f, timeout_sec: calls.append(timeout_sec))
    with pytest.raises(RuntimeError, match='command timeout'):
        node.service('StopMotion()')
    assert calls == [contract.STOP_RPC_TIMEOUT_SEC]
    assert (sum(calls) + contract.STOP_FEEDBACK_TIMEOUT_SEC
            + contract.EXECUTOR_SHUTDOWN_MARGIN_SEC <= contract.LAUNCHER_INTERRUPT_GRACE_SEC)


@pytest.mark.parametrize('mode,done,expected', [('fresh', 1, True), ('fresh', 0, False),
                                              ('silent', 1, False), ('duplicate', 1, False)])
def test_stop_response_and_actual_fresh_stationary_feedback_are_separate(monkeypatch, mode, done, expected):
    node, _ = bare_node(monkeypatch, mode, done=done)
    result = node.observe_stop(after_sequence=1, timeout_sec=1)
    assert result['feedback_verified_stopped'] is expected
    if mode == 'fresh':
        assert result['latest_feedback']['state_sequence'] > 1
    else:
        assert result['latest_feedback'] is None


def run_setup(tmp_path, monkeypatch, labels):
    events = []
    node = FakeNode(events)
    node.state_sequence = 10
    node.state_received_monotonic = 0
    node.current_pose = [1.] * 6
    node.snapshot = lambda: list(node.current_pose)
    node.observe_stop = lambda **kw: {'feedback_verified_stopped': True,
                                    'latest_feedback': {'tcp': [9.] * 6,
                                                        'gripper_position': node.state.gripper_position}}
    patch_offline_runtime(monkeypatch, node, events)
    checked = [SimpleNamespace(slot_code='GPU-01', label=label, tcp=(float(i),) * 6)
               for i, label in enumerate(labels, 1)]
    monkeypatch.setattr(full, 'preflight_route', lambda *a, **kw: (checked,
        dict(waypoints=len(checked), maximum_joint_step_deg=1, minimum_j6_deg=0, maximum_j6_deg=1)))
    args = SimpleNamespace(resume_held=False, run_record=tmp_path/'run.json',
                           plan_file=tmp_path/'plan.json', stop_after_grasp=False)
    payload = dict(cycle_id='offline-regression', motion_profile='smooth_combined_transfer_v1',
                   transfer_z_mm=350, speeds_percent=dict(travel=25, combined_rotation=25, vertical=10))
    return node, args, payload


@pytest.mark.parametrize('error', [RuntimeError('close rejected before acknowledgement'),
                                  RuntimeError('timeout after accepted close'), KeyboardInterrupt()])
def test_close_intent_and_unknown_holding_survive_failure(tmp_path, monkeypatch, error):
    # Original review reproducer #2, plus rejection and Ctrl-C variants.
    node, args, payload = run_setup(tmp_path, monkeypatch, ['pick_final_50mm_vertical'])
    monkeypatch.setattr(full, 'move_preflighted', lambda n, w: list(w.tcp))
    def grip(position, label):
        before = json.loads(args.run_record.read_text())
        assert before['holding_state'] == 'unknown'
        assert before['held_slot'] == 'GPU-01'
        assert before['part_held_candidate'] is None
        assert before['commands'][-1]['purpose'] == 'grasp'
        node.command_event_hook('requested', f'MoveGripper(1,{position})', None)
        if 'accepted' in str(error):
            node.state.gripper_position = position
            node.command_event_hook('accepted', f'MoveGripper(1,{position})', '0')
        raise error
    node.gripper = grip
    with pytest.raises(type(error)):
        full.execute(args, payload, [gpu_item()], 'a'*64)
    record = json.loads(args.run_record.read_text())
    assert record['part_held_candidate'] is None
    assert record['held_slot'] == 'GPU-01'
    assert record['holding_state'] == 'unknown'
    assert record['commands'][-1]['status'] == ('accepted' if 'accepted' in str(error) else 'requested')
    assert record['motion_completed_slots'] == []
    if 'accepted' in str(error):
        assert record['last_gripper_position'] == gpu_item()['grip_position']


def test_release_timeout_preserves_unknown_part_and_blocks_following_lift(tmp_path, monkeypatch):
    node, args, payload = run_setup(tmp_path, monkeypatch,
        ['pick_final_50mm_vertical', 'place_final_50mm_vertical', 'post_release_lift_100mm_vertical'])
    movements = []
    def move(n, w):
        movements.append(w.label)
        return list(w.tcp)
    monkeypatch.setattr(full, 'move_preflighted', move)
    monkeypatch.setattr(full, 'read_gripper_current_percent', lambda n: 10)
    def grip(position, label):
        if label.endswith('release'):
            raise RuntimeError('release feedback lost')
    node.gripper = grip
    with pytest.raises(RuntimeError, match='release feedback lost'):
        full.execute(args, payload, [gpu_item()], 'a'*64)
    record = json.loads(args.run_record.read_text())
    assert record['part_held_candidate'] is None
    assert record['held_slot'] == 'GPU-01'
    assert record['holding_evidence'] == 'release_requested'
    assert record['motion_completed_slots'] == []
    assert movements == ['pick_final_50mm_vertical', 'place_final_50mm_vertical']


@pytest.mark.parametrize('stop_observation_lost', [False, True])
def test_latest_verified_waypoint_survives_later_fault_and_stop_pose(tmp_path, monkeypatch, stop_observation_lost):
    # Original review reproducer #3: later [2,...] waypoint was lost after fault.
    node, args, payload = run_setup(tmp_path, monkeypatch,
        ['post_release_lift_100mm_vertical', 'post_grasp_lift_50mm_vertical', 'later_fault'])
    def move(n, w):
        if w.label == 'later_fault':
            node.snapshot = lambda: (_ for _ in ()).throw(RuntimeError('snapshot unavailable'))
            raise RuntimeError('injected motion fault')
        return list(w.tcp)
    monkeypatch.setattr(full, 'move_preflighted', move)
    if stop_observation_lost:
        node.observe_stop = lambda **kw: (_ for _ in ()).throw(RuntimeError('feedback unavailable'))
    with pytest.raises(RuntimeError, match='injected motion fault'):
        full.execute(args, payload, [gpu_item()], 'a'*64)
    record = json.loads(args.run_record.read_text())
    assert record['last_verified_tcp'] == [2.] * 6
    assert record['last_verified_waypoint']['waypoint'] == 'post_grasp_lift_50mm_vertical'
    assert record['commands'][-1]['waypoint'] == 'later_fault'
    assert record['commands'][-1]['status'] == 'preparing'
    if stop_observation_lost:
        assert 'feedback unavailable' in record['stop_observation']['error']
    else:
        assert record['stop_observation']['latest_feedback']['tcp'] == [9.] * 6


@pytest.mark.parametrize('stop_error', [RuntimeError('delayed stop timeout'), KeyboardInterrupt()])
def test_fault_is_durable_before_delayed_or_interrupted_stop(tmp_path, monkeypatch, stop_error):
    node, args, payload = run_setup(tmp_path, monkeypatch, ['failing_move'])
    monkeypatch.setattr(full, 'move_preflighted',
                        lambda n, w: (_ for _ in ()).throw(RuntimeError('original motion fault')))
    def service(command):
        if command == 'StopMotion()':
            disk = json.loads(args.run_record.read_text())
            assert disk['status'] == 'stopped_on_error'
            assert disk['error'] == 'RuntimeError: original motion fault'
            assert disk['stop_motion_on_error']['status'] == 'requested'
            assert disk['stop_motion_on_error']['succeeded'] is None
            raise stop_error
        return '0'
    node.service = service
    with pytest.raises(RuntimeError, match='original motion fault'):
        full.execute(args, payload, [gpu_item()], 'a'*64)
    record = json.loads(args.run_record.read_text())
    assert record['stop_motion_on_error']['succeeded'] is False
    assert record['stop_motion_on_error']['feedback_verified_stopped'] is True
    assert type(stop_error).__name__ in record['stop_motion_on_error']['error']


def test_failed_fault_record_write_still_attempts_stop(tmp_path, monkeypatch):
    calls = []
    node = SimpleNamespace(service=lambda command: calls.append(command) or '0', state_sequence=1,
                           observe_stop=lambda **kw: {'feedback_verified_stopped': False})
    monkeypatch.setattr(full, 'atomic_write', lambda *args: (_ for _ in ()).throw(OSError('disk full')))
    record = {}
    full.record_fault_and_stop(node, record, tmp_path/'run.json', RuntimeError('motion failed'))
    assert calls == ['StopMotion()']
    assert record['fault_record_write_errors']
    assert record['stop_motion_on_error']['status'] == 'acknowledged'


@pytest.mark.parametrize('escalations', [0, 1, 2])
def test_launcher_records_shutdown_escalation_without_claiming_robot_stop(tmp_path, monkeypatch, escalations):
    record_path = tmp_path/'child.shutdown.json'
    process = SimpleNamespace(pid=123, returncode=None, waits=[])
    process.poll = lambda: process.returncode
    def wait(timeout):
        process.waits.append(timeout)
        if len(process.waits) <= escalations:
            raise launcher.subprocess.TimeoutExpired('fake-child', timeout)
        process.returncode = -2 if escalations == 0 else -15 if escalations == 1 else -9
    process.wait = wait
    sent = []
    def killpg(pid, signum):
        disk = json.loads(record_path.read_text())
        assert disk['status'] == 'shutdown_requested'
        assert disk['signals'][-1]['signal'] == signum.name
        sent.append(signum)
    monkeypatch.setattr(launcher.os, 'killpg', killpg)
    launcher.stop_child(process, record_path, RuntimeError('timed out'))
    record = json.loads(record_path.read_text())
    assert sent == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL][:escalations + 1]
    assert record['forced_termination'] is (escalations > 0)
    assert record['forced_kill'] is (escalations == 2)
    assert record['physical_stop_verified'] is False
    assert record['returncode'] == process.returncode


def test_launcher_still_interrupts_child_if_shutdown_disk_write_fails(tmp_path, monkeypatch):
    process = SimpleNamespace(pid=123, returncode=None)
    process.poll = lambda: process.returncode
    process.wait = lambda timeout: setattr(process, 'returncode', -2)
    sent = []
    monkeypatch.setattr(launcher, 'write', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    monkeypatch.setattr(launcher.os, 'killpg', lambda pid, sig: sent.append(sig))
    launcher.stop_child(process, tmp_path/'shutdown.json', RuntimeError('failed'))
    assert sent == [signal.SIGINT]
    assert process.returncode == -2


def test_real_offline_child_preserves_early_fault_record_during_delayed_stop(tmp_path, monkeypatch):
    # This is a local Python child with no ROS import, network, or hardware.
    # Its delayed shutdown models a stop RPC long enough to require grace.
    fault_path = tmp_path/'fault.json'
    child = tmp_path/'child.py'
    child.write_text('''import json, os, signal, sys, time
from pathlib import Path
path = Path(sys.argv[1])
def stop(signum, frame):
    with path.open('w') as out:
        json.dump({'status': 'stopped_on_error', 'stop_status': 'requested'}, out)
        out.flush()
        os.fsync(out.fileno())
    time.sleep(0.25)
    sys.exit(2)
signal.signal(signal.SIGINT, stop)
print('ready', flush=True)
time.sleep(30)
''')
    monkeypatch.setattr(launcher, 'LAUNCHER_INTERRUPT_GRACE_SEC', 2)
    with pytest.raises(launcher.subprocess.TimeoutExpired):
        launcher.run_step([sys.executable, str(child), str(fault_path)], tmp_path/'child.log', timeout=.3)
    assert json.loads(fault_path.read_text())['stop_status'] == 'requested'
    shutdown = json.loads((tmp_path/'child.shutdown.json').read_text())
    assert shutdown['forced_termination'] is False
    assert shutdown['returncode'] == 2


def test_real_ros_context_survives_sigint_until_offline_stop_cleanup(tmp_path):
    # ROS context only: no Node, publisher, subscriber, client, or service.
    # The StopMotion method below is a Python fake, never a hardware RPC.
    program = '''import json, os, signal, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import rclpy
from rclpy.signals import SignalHandlerOptions, get_current_signal_handlers_options
from execute_full_fixed_cycle import init_executor_ros, record_fault_and_stop
init_executor_ros()
assert get_current_signal_handlers_options() == SignalHandlerOptions.NO
assert signal.getsignal(signal.SIGINT) == signal.default_int_handler
def camera_term(signum, frame):
    raise KeyboardInterrupt('camera SIGTERM')
signal.signal(signal.SIGTERM, camera_term)
calls = []
def fake_service(command):
    assert rclpy.ok(), 'ROS context was shut down before stop cleanup'
    assert signal.getsignal(signal.SIGTERM) == signal.SIG_DFL
    os.kill(os.getpid(), signal.SIGINT)  # repeated interrupt must not cancel stop
    calls.append(command)
    return '0'
node = SimpleNamespace(service=fake_service, state_sequence=1,
    observe_stop=lambda **kw: {'feedback_verified_stopped': True})
record = {}
try:
    try:
        os.kill(os.getpid(), signal.SIGINT)
    except KeyboardInterrupt as error:
        record_fault_and_stop(node, record, Path(sys.argv[2]), error)
    assert calls == ['StopMotion()']
    assert rclpy.ok()
    assert signal.getsignal(signal.SIGINT) == signal.default_int_handler
    assert signal.getsignal(signal.SIGTERM) == camera_term
finally:
    rclpy.shutdown()
assert not rclpy.ok()
print(json.dumps(record))
'''
    result = launcher.subprocess.run(
        [sys.executable, '-B', '-c', program, str(Path(cached.__file__).parent), str(tmp_path/'signal.json')],
        env=dict(os.environ, ROS_DOMAIN_ID='231', PYTHONDONTWRITEBYTECODE='1'),
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    record = json.loads((tmp_path/'signal.json').read_text())
    assert record['error'].startswith('KeyboardInterrupt:')
    assert record['stop_motion_on_error']['status'] == 'acknowledged'
    assert record['stop_motion_on_error']['feedback_verified_stopped'] is True


def test_camera_motion_interrupt_uses_live_ros_policy_and_durable_stop(tmp_path, monkeypatch):
    import cycle_camera_stage as camera
    from rclpy.signals import SignalHandlerOptions
    events = []
    node = FakeNode(events)
    node.state_sequence = 1
    node.state_received_monotonic = 0
    node.response_values = cached.Executor.response_values
    def subscribe(kind, topic, callback, qos):
        if topic.endswith('camera_info'):
            callback(SimpleNamespace(width=1280, height=720, k=[1.] * 9))
        else:
            stamp = int(cached.time.time())
            callback(SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=stamp, nanosec=0))))
    node.create_subscription = subscribe
    path = tmp_path/'PlaceCamera_camera_stage.json'
    def service(command):
        if command == 'StopMotion()':
            assert json.loads(path.read_text())['stop_motion_on_error']['status'] == 'requested'
            events.append(command)
        if command.startswith('GetTCPOffset'):
            return '0,' + ','.join(['0'] * 6)
        if command.startswith('GetRobotTeachingPoint'):
            return '0,' + ','.join(['0'] * 12 + ['1', '0'])
        return '0'
    node.service = service
    node.observe_stop = lambda **kw: {'feedback_verified_stopped': True}
    monkeypatch.setattr(full, 'Executor', lambda: node)
    init_options = []
    monkeypatch.setattr(cached.rclpy, 'init', lambda **kw: init_options.append(kw))
    monkeypatch.setattr(cached.rclpy, 'ok', lambda: False)
    monkeypatch.setattr(cached.rclpy, 'spin_once',
                        lambda n, **kw: setattr(n, 'state_sequence', n.state_sequence + 1))
    monkeypatch.setattr(full, 'validate_start_state', lambda n: n.state)
    baseline = dict(active_tcp_offset=[0.] * 6,
                    teaching_points={name: [0.] * 6 for name in ['PlaceCamera', 'TrayHome']},
                    camera=dict(width=1280, height=720, k=[1.] * 9))
    monkeypatch.setattr(camera, 'read', lambda path: baseline if path.name == 'runtime.json'
                        else {'reference_tcp_base': [0.] * 6})
    monkeypatch.setattr(full, 'preflight_route', lambda *a, **kw: ([object()], {}))
    monkeypatch.setattr(full, 'move_preflighted', lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    args = SimpleNamespace(point='PlaceCamera', directory=tmp_path, execute=True, capture_only=False)
    with pytest.raises(KeyboardInterrupt):
        camera.run(args)
    assert init_options == [{'signal_handler_options': SignalHandlerOptions.NO}]
    assert events == ['StopMotion()']
    record = json.loads(path.read_text())
    assert record['status'] == 'stopped_on_error'
    assert record['stop_motion_response'] == '0'
    assert record['stop_motion_on_error']['feedback_verified_stopped'] is True
