import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import server_bundle as bundle


def test_default_monitor_and_unchanged_entrypoints():
    args = bundle.parse_args([])
    specs = bundle.commands(args)
    assert specs[0][1][-1] == '--monitor-only'
    assert Path(specs[0][1][0]).name == 'run_conveyor_remote_server.sh'
    assert Path(specs[1][1][0]).name == 'run_conveyor_inspection_trigger.sh'
    assert specs[1][1][1:] == ['--host', '0.0.0.0', '--port', '8766', '--timeout', '300']
    assert len(specs) == 2  # no camera/legacy trigger/HTTP POST process


@pytest.mark.parametrize('argv', [
    ['--execute'], ['--confirm-motion'], ['--execute', '--monitor-only'],
    ['--legacy-arrival-trigger'], ['--port', '0'], ['--timeout', 'nan'],
    ['--startup-timeout', '0'],
])
def test_invalid_options_never_arm(argv):
    with pytest.raises(SystemExit):
        bundle.parse_args(argv)


def test_explicit_motion_keeps_legacy_safety_args():
    specs = bundle.commands(bundle.parse_args(['--execute', '--confirm-motion']))
    assert specs[0][1][1:] == ['--execute', '--confirm-motion']
    assert not any('fr5' in word for _, argv in specs for word in argv)


def test_process_discovery_exact_match_and_no_argv_leak(tmp_path):
    for pid, cmd in [('123', b'python3\0/path/inspection_api.py\0--secret\0hidden\0'),
                     ('124', b'python3\0test_inspection_api.py\0'),
                     ('125', b'ros2\0run\0vision_server\0conveyor_remote_server\0')]:
        (tmp_path/pid).mkdir()
        (tmp_path/pid/'cmdline').write_bytes(cmd)
    found = bundle.existing_local_servers(tmp_path)
    assert len(found) == 2
    assert 'hidden' not in str(found) and '124' not in str(found)


def test_camera_lock_probe_does_not_modify_or_release_owner(tmp_path):
    path = tmp_path/'camera.lock'
    path.write_text('owner')
    with path.open('r') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='owns the camera lock'):
            bundle.check_lock(path)
        with pytest.raises(RuntimeError):
            bundle.check_lock(path)
    bundle.check_lock(path)
    assert path.read_text() == 'owner'
    bundle.check_lock(tmp_path/'nonexistent')
    assert not (tmp_path/'nonexistent').exists()


class Graph:
    def __init__(self, services=()):
        self.found = set(services)

    def services(self):
        return self.found


@pytest.fixture
def preflight_env(monkeypatch):
    monkeypatch.setenv('KSMC_VISION_API_TOKEN', 'x' * 64)
    monkeypatch.setattr(bundle, 'existing_local_servers', lambda: [])
    monkeypatch.setattr(bundle, 'check_port', lambda *_: None)
    monkeypatch.setattr(bundle, 'check_lock', lambda *_: None)
    monkeypatch.setattr(bundle.os, 'access', lambda *_: True)


def test_preflight_accepts_clear_graph_without_launch(preflight_env):
    bundle.preflight(bundle.parse_args([]), Graph(), threading.Event(), discovery_seconds=0)


def test_preflight_refuses_existing_local_without_killing(preflight_env, monkeypatch):
    monkeypatch.setattr(bundle, 'existing_local_servers', lambda: ['PID 123: inspection_api.py'])
    with pytest.raises(RuntimeError, match='no takeover'):
        bundle.preflight(bundle.parse_args([]), Graph(), threading.Event(), discovery_seconds=0)


def test_preflight_allows_remote_client_names(preflight_env):
    # rclpy exposes client and server names through the same graph query;
    # remote client names must not block starting our local server.
    bundle.preflight(bundle.parse_args([]), Graph(['/conveyor/stop']), threading.Event(), discovery_seconds=0)


def test_preflight_requires_original_token(preflight_env, monkeypatch):
    monkeypatch.delenv('KSMC_VISION_API_TOKEN')
    with pytest.raises(RuntimeError, match='Missing fixed'):
        bundle.preflight(bundle.parse_args([]), Graph(), threading.Event(), discovery_seconds=0)


class Child:
    pid = 123456

    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code


def test_startup_failure_stops_owned_peer_without_restart(monkeypatch):
    cleaned = []
    spawned = []
    monkeypatch.setattr(bundle, 'cleanup', lambda children: cleaned.extend(children))

    def spawn(argv, **kwargs):
        spawned.append(argv)
        assert kwargs['start_new_session'] is True
        return Child(2 if len(spawned) == 2 else None)

    with pytest.raises(RuntimeError, match='no restart'):
        bundle.supervise([('one', ['one']), ('two', ['two'])], lambda: True,
                         threading.Event(), 2, popen=spawn)
    assert len(spawned) == len(cleaned) == 2


def test_second_spawn_error_cleans_first(monkeypatch):
    cleaned = []
    calls = []
    monkeypatch.setattr(bundle, 'cleanup', lambda children: cleaned.extend(children))

    def spawn(*_, **__):
        calls.append(1)
        if len(calls) == 2:
            raise OSError('mock executable unavailable')
        return Child()

    with pytest.raises(OSError):
        bundle.supervise([('one', ['one']), ('two', ['two'])], lambda: False,
                         threading.Event(), 2, popen=spawn)
    assert len(cleaned) == 1


def test_startup_timeout_is_not_false_ready(monkeypatch):
    cleaned = []
    monkeypatch.setattr(bundle, 'cleanup', lambda children: cleaned.extend(children))
    with pytest.raises(RuntimeError, match='timed out'):
        bundle.supervise([('one', ['one'])], lambda: False, threading.Event(),
                         0, popen=lambda *a, **k: Child())
    assert len(cleaned) == 1


def test_stop_before_start_launches_nothing():
    stop = threading.Event()
    stop.set()
    def forbidden(*_, **__):
        pytest.fail('spawn after stop')
    assert bundle.supervise([('one', ['one'])], lambda: True, stop, 2, popen=forbidden) == 130


def test_real_mock_worker_shutdown_leaves_external_process_alive():
    # Only inert Python sleep workers, never ROS/camera/conveyor entrypoints.
    argv = [sys.executable, '-c', 'import time; time.sleep(60)']
    external = subprocess.Popen(argv, start_new_session=True)
    children = []
    stop = threading.Event()

    def spawn(*a, **kw):
        child = subprocess.Popen(*a, **kw)
        children.append(child)
        return child

    timer = threading.Timer(0.3, stop.set)
    timer.start()
    try:
        assert bundle.supervise([('mock1', argv), ('mock2', argv)], lambda: True,
                                stop, 2, popen=spawn, interval=0.01) == 130
        assert len(children) == 2 and all(child.poll() is not None for child in children)
        assert external.poll() is None
    finally:
        timer.cancel()
        os.killpg(external.pid, signal.SIGTERM)
        external.wait(timeout=3)
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)


def test_check_mode_does_not_start_servers(preflight_env, monkeypatch):
    class FakeGraph(Graph):
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
    monkeypatch.setattr(bundle, 'RosGraph', FakeGraph)
    monkeypatch.setattr(bundle, 'preflight', lambda *a: None)
    monkeypatch.setattr(bundle.signal, 'signal', lambda *a: None)
    monkeypatch.setattr(bundle, 'supervise', lambda *a: pytest.fail('started in check mode'))
    assert bundle.main(['--check']) == 0


def test_port_conflict_does_not_disconnect_listener():
    # Optional socket test; run outside restricted network sandbox.
    import socket
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        server.listen()
        port = server.getsockname()[1]
        with pytest.raises(RuntimeError, match='left untouched'):
            bundle.check_port('0.0.0.0', port)
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            connection, _ = server.accept()
            connection.close()


def test_stopping_bundle_does_not_need_camera_or_api_requests():
    # Contract check: the supervisor only builds the unchanged two entrypoints.
    assert bundle.SERVICES == {'/conveyor/move_to_assembly', '/conveyor/move_to_inspection',
                               '/conveyor/stop', '/conveyor/reset'}
    assert all('legacy' not in str(argv) and 's22_conveyor' not in str(argv)
               for _, argv in bundle.commands(bundle.parse_args([])))


def test_ros_graph_failed_enter_releases_initialized_context(monkeypatch):
    from types import ModuleType, SimpleNamespace
    calls = []
    context = SimpleNamespace(shutdown=lambda: calls.append('shutdown'))
    rclpy = ModuleType('rclpy')
    rclpy.init = lambda **_: calls.append('init')
    def fail_create(*_, **__):
        raise RuntimeError('mock node creation failure')
    rclpy.create_node = fail_create
    monkeypatch.setitem(sys.modules, 'rclpy', rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.context', SimpleNamespace(Context=lambda: context))
    monkeypatch.setitem(sys.modules, 'rclpy.signals', SimpleNamespace(
        SignalHandlerOptions=SimpleNamespace(NO=0)))
    with pytest.raises(RuntimeError, match='node creation'):
        bundle.RosGraph().__enter__()
    assert calls == ['init', 'shutdown']


def test_ros_graph_destroy_failure_still_shuts_down_context():
    from types import SimpleNamespace
    calls = []
    def fail_destroy():
        raise RuntimeError('mock node destruction failure')
    graph = bundle.RosGraph()
    graph.node = SimpleNamespace(destroy_node=fail_destroy)
    graph.context = SimpleNamespace(shutdown=lambda: calls.append('shutdown'))
    with pytest.raises(RuntimeError, match='destruction'):
        graph.__exit__()
    assert calls == ['shutdown']
