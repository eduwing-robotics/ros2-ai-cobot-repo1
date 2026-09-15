#!/usr/bin/env python3
"""Run allowlisted software regression suites, never device launchers.

Uses mock/synthetic tests only, no capture/inference/training or ROS equipment
nodes. This is software regression evidence, not a hardware readiness certificate.
"""
import argparse
import ast
import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
_running = set()
_lock = threading.Lock()
_cancelled = threading.Event()


def build_plan(root=ROOT, with_loopback=False):
    ml = root / 'vision_assembly/.venv_patchcore/bin/python'
    system = '/usr/bin/python3'
    pytest = ['-m', 'pytest', '-q']
    ros_paths = [Path('/opt/ros/jazzy/setup.bash'), root/'robot_ws/install/setup.bash',
                 root/'ros2_ws/install/setup.bash']

    def ros_command(paths):
        setup = '\n'.join('source ' + shlex.quote(str(p)) for p in ros_paths)
        return ['bash', '--noprofile', '--norc', '-c', 'set -e\n' + setup +
                '\nexec ' + shlex.join([system, *pytest, *paths])]

    camera_tests = sorted(str(p.relative_to(root)) for directory in
                          ('camera2_scrcpy', 'gopro_camera3')
                          for p in (root/directory).glob('test_*.py'))
    api = [str(ml), *pytest, 'vision_assembly/integration']
    if not with_loopback:
        api += ['-k', 'not http_roundtrip and not http_countermeasure_roundtrip and not port_conflict_does_not_disconnect_listener']
    return [
        dict(name='hybrid', command=[str(ml), *pytest, 'vision_assembly/hybrid_inspection'],
             required=[str(ml)]),
        dict(name='api_and_bundle', command=api, required=[str(ml)]),
        dict(name='camera', command=[system, *pytest, *camera_tests],
             required=[system, *[str(root/p) for p in camera_tests]], empty=not camera_tests),
        dict(name='ros_conveyor', command=ros_command(['ros2_ws/src/vision_server/test']),
             required=[system, *map(str, ros_paths)]),
        dict(name='robot_and_tray', command=ros_command(['calibration/tests', 'vision_assembly/tests']),
             required=[system, *map(str, ros_paths)]),
        dict(name='viewer', command=['node', 'vision_assembly/integration/test_demo_viewer.cjs'],
             required=['node']),
        dict(name='runner', command=[str(ml), *pytest, 'scripts/test_offline_checks.py',
                                    'scripts/test_remote_camera_view.py'],
             required=[str(ml)]),
        dict(name='source_syntax', command=[system, 'scripts/run_offline_checks.py', '--syntax-only'],
             required=[system, 'bash']),
    ]


def check_source_syntax(root=ROOT):
    directories = ('', 'scripts', 'calibration/scripts', 'camera2_scrcpy',
                   'gopro_camera3', 'gopro_camera3/notebooks',
                   'ros2_ws/src/vision_server/vision_server', 'vision_assembly',
                   'vision_assembly/hybrid_inspection', 'vision_assembly/integration',
                   'vision_assembly/slot_classifier', 'vision_assembly/scripts',
                   'calibration', 'robot_ws', 'ros2_ws')
    failures, python_count, shell_count = [], 0, 0
    env = dict(os.environ)
    env.pop('BASH_ENV', None)
    for directory in directories:
        for path in sorted((root/directory).glob('*.py')):
            try:
                ast.parse(path.read_bytes(), filename=str(path))
                python_count += 1
            except (SyntaxError, ValueError, OSError) as exc:
                failures.append(f'{path}: {exc}')
        for path in sorted((root/directory).glob('*.sh')):
            try:
                result = subprocess.run(['bash', '--noprofile', '--norc', '-n', str(path)],
                                        capture_output=True, text=True, timeout=5, env=env)
                shell_count += 1
                if result.returncode:
                    failures.append(f'{path}: {result.stderr.strip()}')
            except (OSError, subprocess.TimeoutExpired) as exc:
                failures.append(f'{path}: {exc}')
    print(json.dumps(dict(python_files=python_count, shell_files=shell_count,
                          errors=failures, code_executed=False), indent=2))
    return 1 if failures else 0


def _stop_owned(process):
    # Only fresh session groups created by this runner; no pkill/process matching.
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    except ProcessLookupError:
        pass


def run_check(check, output, timeout, root=ROOT):
    start = time.monotonic()
    result = dict(name=check['name'], command=check['command'], status='NOT_RUN')
    if _cancelled.is_set():
        return result
    missing = [value for value in check['required'] if
               not (Path(value).exists() if '/' in value else shutil.which(value))]
    if missing or check.get('empty'):
        return dict(result, status='UNAVAILABLE', missing=missing,
                    note='Missing environment/tests is not a successful check')
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               CUDA_VISIBLE_DEVICES='', ROS_LOG_DIR=str(output/'ros_logs'))
    # Never let an ambient startup file run commands before the allowlisted tests.
    env.pop('BASH_ENV', None)
    log = output / (check['name'] + '.log')
    process = None
    try:
        with log.open('x') as stream:
            with _lock:
                if _cancelled.is_set():
                    return result
                process = subprocess.Popen(check['command'], cwd=root, env=env,
                                           stdin=subprocess.DEVNULL, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                _running.add(process)
            try:
                code = process.wait(timeout=timeout)
                result.update(status='PASS' if code == 0 else 'FAIL', returncode=code)
            except subprocess.TimeoutExpired:
                _stop_owned(process)
                result.update(status='TIMEOUT', note='Only owned test process group terminated')
    except OSError as exc:
        result.update(status='ERROR', error=str(exc))
    finally:
        if process is not None:
            _stop_owned(process)
            with _lock:
                _running.discard(process)
    result.update(seconds=round(time.monotonic()-start, 3), log=str(log))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='Show plan without running/writing')
    parser.add_argument('--syntax-only', action='store_true', help='Parse allowlisted source without executing it')
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--timeout', type=int, default=120, help='Per-suite seconds (1..600)')
    parser.add_argument('--with-loopback', action='store_true',
                        help='Include temporary local mock HTTP test; never contact equipment')
    parser.add_argument('--output', type=Path, help='New report directory; existing paths refused')
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 600:
        parser.error('--timeout must be between 1 and 600 seconds')
    if args.syntax_only:
        return check_source_syntax()
    plan = build_plan(with_loopback=args.with_loopback)
    if args.list:
        print(json.dumps(plan, indent=2))
        return 0
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = (args.output or ROOT/'runtime/software_checks'/f'{stamp}_{uuid.uuid4().hex[:8]}').resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    _cancelled.clear()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs)
    futures = []
    interrupted = False
    try:
        futures = [executor.submit(run_check, item, output, args.timeout) for item in plan]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"{result['status']:11s} {result['name']}", flush=True)
    except KeyboardInterrupt:
        interrupted = True
        _cancelled.set()
        for future in futures:
            future.cancel()
        with _lock:
            running = list(_running)
        for process in running:
            _stop_owned(process)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    for item, future in zip(plan, futures):
        if not any(row['name'] == item['name'] for row in results):
            results.append(future.result() if future.done() and not future.cancelled() else
                           dict(name=item['name'], status='NOT_RUN'))
    status = 'PASS' if not interrupted and all(row['status'] == 'PASS' for row in results) else 'INCOMPLETE_OR_FAILED'
    report = dict(status=status, interrupted=interrupted, checks=results,
                  software_only=True, hardware_verified=False, camera_capture=False,
                  model_training=False, equipment_commands=False,
                  mock_loopback_included=args.with_loopback, created_at=stamp)
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'REPORT={output / "report.json"}', flush=True)
    return 130 if interrupted else (0 if status == 'PASS' else 1)


if __name__ == '__main__':
    sys.exit(main())
