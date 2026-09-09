import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('offline_checks', Path(__file__).with_name('run_offline_checks.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_plan_uses_only_tests_not_camera_or_motor_launchers():
    plan = runner.build_plan()
    assert len({r['name'] for r in plan}) == len(plan) == 8
    for row in plan:
        command = ' '.join(row['command'])
        assert any(value in command for value in ('pytest', 'test_demo_viewer.cjs', '--syntax-only'))
        assert '--execute' not in command and 'ros2 run' not in command
        assert 'config/ksmc.env' not in command
    api = next(r for r in plan if r['name'] == 'api_and_bundle')
    assert 'not http_roundtrip' in api['command'][-1]
    assert 'not port_conflict_does_not_disconnect_listener' in api['command'][-1]
    assert '-k' not in next(r for r in runner.build_plan(with_loopback=True)
                            if r['name'] == 'api_and_bundle')['command']


def test_missing_dependency_is_not_pass(tmp_path):
    result = runner.run_check(dict(name='missing', command=['no-executable'],
                                   required=[str(tmp_path/'absent')]), tmp_path, 1)
    assert result['status'] == 'UNAVAILABLE'


def test_real_inert_child_success_failure_and_timeout(tmp_path):
    for name, code, expected in [('ok', 'print("ok")', 'PASS'),
                                 ('fail', 'raise SystemExit(3)', 'FAIL'),
                                 ('timeout', 'import time; time.sleep(20)', 'TIMEOUT')]:
        result = runner.run_check(dict(name=name, command=[sys.executable, '-c', code],
                                       required=[sys.executable]), tmp_path, .1 if name == 'timeout' else 2)
        assert result['status'] == expected
    assert not runner._running


def test_list_is_read_only(tmp_path, capsys):
    output = tmp_path/'report'
    assert runner.main(['--list', '--output', str(output)]) == 0
    assert not output.exists()
    assert 'robot_and_tray' in capsys.readouterr().out


def test_cancelled_run_does_not_launch_child(tmp_path, monkeypatch):
    runner._cancelled.set()
    monkeypatch.setattr(runner.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(AssertionError('started')))
    try:
        assert runner.run_check(dict(name='cancelled', command=['never'], required=[]),
                                tmp_path, 1)['status'] == 'NOT_RUN'
    finally:
        runner._cancelled.clear()


def test_source_syntax_never_executes_source(tmp_path):
    marker = tmp_path/'must_not_exist'
    (tmp_path/'test.py').write_text(f'raise RuntimeError("do not execute")\n')
    (tmp_path/'test.sh').write_text(f'touch {marker}\n')
    assert runner.check_source_syntax(tmp_path) == 0
    assert not marker.exists()
    (tmp_path/'bad.py').write_text('if :')
    assert runner.check_source_syntax(tmp_path) == 1
