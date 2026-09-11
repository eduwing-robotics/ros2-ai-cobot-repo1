"""Exercise production Runner with fake child processes; no camera or sockets."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_inspection_api import api, request


@pytest.mark.parametrize('decision', ['UNKNOWN', 'PASS', 'FAIL'])
def test_runner_packages_only_final_report(tmp_path, monkeypatch, decision):
    calls, signals, packages = [], [], []
    req = request()
    final_report = tmp_path/'second_report.json'

    def launch(command, **kwargs):
        calls.append((command, kwargs))
        (tmp_path/'event.json').write_text(json.dumps({
            'pipeline_status': 'COMPLETED', 'final_status': decision,
            'finished_at': '2026-09-08T05:00:00Z', 'report': str(final_report),
            'attempts': [{'report': 'first_report.json'}, {'report': str(final_report)}]}))
        return SimpleNamespace(pid=123456, returncode=0, poll=lambda: 0, wait=lambda **_: 0)

    def package(report, directory, identity):
        packages.append((report, directory, identity))
        return {'decision': decision}, {'ready': True}

    monkeypatch.setattr(api.subprocess, 'Popen', launch)
    monkeypatch.setattr(api.os, 'killpg', lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(api, 'prepare_result', package)
    monkeypatch.setenv('KSMC_VISION_CONTEXT_FILE', '/unrelated/context.json')
    assert api.Runner(300, 17)(req, tmp_path) == ({'decision': decision}, {'ready': True})
    assert packages == [(str(final_report), tmp_path, req)]
    assert len(calls) == 1  # The child owns both attempts, not two Runner launches.
    assert calls[0][1]['env']['KSMC_VISION_EXPORT'] == '0'
    assert 'KSMC_VISION_CONTEXT_FILE' not in calls[0][1]['env']
    assert calls[0][1]['start_new_session'] is True
    assert calls[0][1]['pass_fds'] == (17,)
    assert calls[0][0][-2:] == ['--source-topic', '/vision/inspection/submit']
    assert signals == [(123456, api.signal.SIGTERM), (123456, api.signal.SIGKILL)]


@pytest.mark.parametrize('mode', ['child_error', 'pipeline_error', 'timeout'])
def test_runner_failure_never_packages_result(tmp_path, monkeypatch, mode):
    signals = []
    def launch(*args, **kwargs):
        (tmp_path/'event.json').write_text(json.dumps({'pipeline_status': 'ERROR'}))
        code = 1 if mode == 'child_error' else 0
        return SimpleNamespace(pid=123456, returncode=code,
            poll=lambda: None if mode == 'timeout' else code, wait=lambda **_: 0)
    monkeypatch.setattr(api.subprocess, 'Popen', launch)
    monkeypatch.setattr(api.os, 'killpg', lambda pid, sig: signals.append((pid, sig)))
    monkeypatch.setattr(api, 'prepare_result', lambda *_: pytest.fail('failed run packaged'))
    runner = api.Runner(300, 17)
    if mode == 'timeout':
        ticks = iter([0, 301])
        monkeypatch.setattr(api.time, 'monotonic', lambda: next(ticks))
        runner.stop = SimpleNamespace(is_set=lambda: False, wait=lambda _: False)
    with pytest.raises((RuntimeError, TimeoutError)):
        runner(request(), tmp_path)
    assert signals == [(123456, api.signal.SIGTERM), (123456, api.signal.SIGKILL)]
