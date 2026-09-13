"""Real private-pipe lifecycle tests using a fake worker, never hardware."""
import json
from pathlib import Path
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspection_process import InspectionProcess

FAKE = '''
import json, os, subprocess, sys, time
for line in sys.stdin:
    task = json.loads(line)
    mode = task['argv'][0]
    info = dict(pid=os.getpid(), task=task['argv'],
                export=os.environ.get('KSMC_VISION_EXPORT'),
                context=os.environ.get('KSMC_VISION_CONTEXT_FILE'))
    if mode == 'descendant':
        child = subprocess.Popen([sys.executable, '-c',
            'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'])
        info['descendant'] = child.pid
    with open(task['log'], 'w') as log:
        json.dump(info, log)
    if mode in ('sleep', 'descendant'):
        time.sleep(30)
    if mode == 'exit':
        sys.exit(1)
    if mode == 'oversize':
        print('x' * 5000, flush=True)
        continue
    print(json.dumps(dict(token='wrong' if mode == 'mismatch' else task['token'],
                          ok=mode != 'fail')), flush=True)
'''


@pytest.fixture
def worker():
    process = InspectionProcess(-1, [sys.executable, '-u', '-c', FAKE])
    yield process
    process.close()


def run(worker, tmp_path, mode='ok', timeout=3, stop=None):
    log = tmp_path / 'job.log'
    worker.execute([mode], log, timeout=timeout, stop=stop or threading.Event())
    return json.loads(log.read_text())


def test_reuses_process_but_not_request_or_log(worker, tmp_path, monkeypatch):
    monkeypatch.setenv('KSMC_VISION_CONTEXT_FILE', 'must-not-leak')
    monkeypatch.setenv('KSMC_VISION_EXPORT', '1')
    first = run(worker, tmp_path)
    second = run(worker, tmp_path, 'second')
    assert first['pid'] == second['pid']
    assert first['task'] == ['ok'] and second['task'] == ['second']
    assert second['export'] == '0' and second['context'] is None
    child = worker.child
    worker.close()
    worker.close()
    assert worker.child is None and child.poll() is not None


@pytest.mark.parametrize('mode', ['fail', 'exit', 'mismatch', 'oversize'])
def test_failure_retires_worker_and_next_job_starts_clean(worker, tmp_path, mode):
    old_pid = run(worker, tmp_path)['pid']
    with pytest.raises(RuntimeError):
        run(worker, tmp_path, mode)
    assert worker.child is None
    assert run(worker, tmp_path)['pid'] != old_pid


@pytest.mark.parametrize('mode', ['sleep', 'descendant'])
def test_timeout_retires_entire_group(worker, tmp_path, mode):
    run(worker, tmp_path)
    child = worker.child
    with pytest.raises(TimeoutError):
        run(worker, tmp_path, mode, timeout=.4)
    assert worker.child is None and child.poll() is not None
    info = json.loads((tmp_path / 'job.log').read_text())
    if 'descendant' in info:
        status = Path(f"/proc/{info['descendant']}/stat")
        deadline = time.monotonic() + 2
        while status.exists() and status.read_text().split(') ')[1][0] != 'Z':
            assert time.monotonic() < deadline, 'descendant still executing'
            time.sleep(.01)


def test_shutdown_interrupts_active_task(worker, tmp_path):
    run(worker, tmp_path)
    stop = threading.Event()
    timer = threading.Timer(.2, stop.set)
    timer.start()
    try:
        with pytest.raises(TimeoutError):
            run(worker, tmp_path, 'sleep', stop=stop)
    finally:
        timer.join()
    assert worker.child is None


def test_stopped_runner_never_spawns(worker, tmp_path):
    stop = threading.Event()
    stop.set()
    with pytest.raises(RuntimeError, match='shutdown_before_capture'):
        run(worker, tmp_path, stop=stop)
    assert worker.child is None


def test_oversized_task_rejected_before_spawning(worker, tmp_path):
    with pytest.raises(ValueError, match='request_too_large'):
        run(worker, tmp_path, 'x' * 5000)
    assert worker.child is None


def test_worker_inherits_camera_lock(tmp_path):
    code = 'import os; os.fstat(int(os.environ["TEST_LOCK_FD"]))\n' + FAKE
    with (tmp_path / 'lock').open('w') as lock:
        worker = InspectionProcess(lock.fileno(), [sys.executable, '-u', '-c',
            code.replace('os.environ["TEST_LOCK_FD"]', repr(str(lock.fileno())))])
        try:
            assert run(worker, tmp_path)['pid'] == worker.child.pid
        finally:
            worker.close()
