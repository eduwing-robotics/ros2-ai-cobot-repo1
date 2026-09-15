"""Exercise production Runner's result boundary; no camera or sockets."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_inspection_api import api, request


@pytest.mark.parametrize('decision', ['UNKNOWN', 'PASS', 'FAIL'])
def test_runner_packages_only_final_report(tmp_path, monkeypatch, decision):
    calls, packages = [], []
    req = request()
    final_report = tmp_path/'second_report.json'

    def execute(argv, log, **kwargs):
        calls.append((argv, log, kwargs))
        (tmp_path/'event.json').write_text(json.dumps({
            'pipeline_status': 'COMPLETED', 'final_status': decision,
            'finished_at': '2026-09-08T05:00:00Z', 'report': str(final_report),
            'attempts': [{'report': 'first_report.json'}, {'report': str(final_report)}]}))

    def package(report, directory, identity):
        packages.append((report, directory, identity))
        return {'decision': decision}, {'ready': True}

    monkeypatch.setattr(api, 'prepare_result', package)
    runner = api.Runner(300, 17)
    monkeypatch.setattr(runner.process, 'execute', execute)
    assert runner(req, tmp_path) == ({'decision': decision}, {'ready': True})
    assert packages == [(str(final_report), tmp_path, req)]
    assert len(calls) == 1  # One worker task owns both attempts.
    assert runner.process.lock_fd == 17
    assert calls[0][1] == tmp_path / 'execution.log'
    assert calls[0][2] == dict(timeout=300, stop=runner.stop)
    assert calls[0][0][-2:] == ['--source-topic', '/vision/inspection/submit']


@pytest.mark.parametrize('mode', ['child_error', 'pipeline_error', 'timeout'])
def test_runner_failure_never_packages_result(tmp_path, monkeypatch, mode):
    def execute(*args, **kwargs):
        (tmp_path/'event.json').write_text(json.dumps({'pipeline_status': 'ERROR'}))
        if mode == 'child_error':
            raise RuntimeError('worker failed')
        if mode == 'timeout':
            raise TimeoutError('worker timed out')
    monkeypatch.setattr(api, 'prepare_result', lambda *_: pytest.fail('failed run packaged'))
    runner = api.Runner(300, 17)
    monkeypatch.setattr(runner.process, 'execute', execute)
    with pytest.raises((RuntimeError, TimeoutError)):
        runner(request(), tmp_path)


def test_runner_close_sets_stop_and_releases_worker(monkeypatch):
    runner = api.Runner(300, 17)
    closed = []
    monkeypatch.setattr(runner.process, 'close', lambda: closed.append(runner.stop.is_set()))
    runner.close()
    assert closed == [True]
