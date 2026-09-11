"""Supervise existing conveyor/inspection entrypoints without changing their APIs.

Never adopt, signal or restart a pre-existing server. No camera launch or service
calls: station readiness and motion interlocks remain the existing servers' job.
"""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SERVICES = frozenset('/conveyor/' + name for name in (
    'move_to_assembly', 'move_to_inspection', 'stop', 'reset'))
CAMERA_LOCK = ROOT / 'runtime/s22_camera_control/auto_inspection_trigger.lock'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--monitor-only', action='store_true', help='Default: reject motion requests')
    mode.add_argument('--execute', action='store_true', help='Allow guarded remote motion requests')
    parser.add_argument('--confirm-motion', action='store_true')
    parser.add_argument('--check', action='store_true', help='Read-only preflight; do not start either server')
    parser.add_argument('--host', default='0.0.0.0', help='Trusted LAN bind address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--timeout', type=float, default=300, help='Existing inspection execution timeout')
    parser.add_argument('--startup-timeout', type=float, default=20)
    args = parser.parse_args(argv)
    if args.execute != args.confirm_motion:
        parser.error('Motion requires both --execute and --confirm-motion')
    if not 1 <= args.port <= 65535 or not 0 < args.timeout <= 3600 or not 1 <= args.startup_timeout <= 120:
        parser.error('Invalid port/timeout; startup timeout must be 1..120 seconds')
    return args


def commands(args, root=ROOT):
    motion = ['--execute', '--confirm-motion'] if args.execute else ['--monitor-only']
    return [
        ('conveyor', [str(root/'run_conveyor_remote_server.sh'), *motion]),
        ('inspection', [str(root/'vision_assembly/run_conveyor_inspection_trigger.sh'),
                        '--host', args.host, '--port', str(args.port), '--timeout', str(args.timeout)]),
    ]


def existing_local_servers(proc_root=Path('/proc')):
    """Exact argv basename matches; never print argv (credentials may be present)."""
    targets = {'conveyor_remote_server', 'inspection_api.py', 'conveyor_inspection_trigger.py'}
    found = []
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry/'cmdline').read_bytes().split(b'\0')
            names = {Path(arg.decode(errors='replace')).name for arg in argv if arg}
            matched = names & targets
            if matched:
                found.append(f'PID {entry.name}: {", ".join(sorted(matched))}')
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return found


def check_lock(path):
    # Existing API's advisory lock. Do not create/truncate a lock in --check.
    if path.exists():
        with path.open('r') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('An inspection API/arrival trigger/capture owns the camera lock') from exc


def check_port(host, port):
    try:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError as exc:
        raise RuntimeError(f'Cannot reserve HTTP bind {host}:{port}; existing server left untouched: {exc}') from exc


def port_open(host, port):
    try:
        with socket.create_connection(('127.0.0.1' if host == '0.0.0.0' else host, port), timeout=0.3):
            return True
    except OSError:
        return False


class RosGraph:
    """Only ROS graph discovery. No publisher, subscription or service client."""
    def __enter__(self):
        import rclpy
        from rclpy.context import Context
        from rclpy.signals import SignalHandlerOptions
        self.rclpy = rclpy
        self.context = Context()
        rclpy.init(context=self.context, signal_handler_options=SignalHandlerOptions.NO)
        try:
            self.node = rclpy.create_node(f'ksmc_bundle_probe_{os.getpid()}', context=self.context,
                                        enable_rosout=False, start_parameter_services=False)
        except BaseException:
            self.context.shutdown()
            raise
        return self

    def services(self):
        return {name for name, types in self.node.get_service_names_and_types()
                if 'std_srvs/srv/Trigger' in types and name in SERVICES}

    def __exit__(self, *_):
        try:
            self.node.destroy_node()
        finally:
            self.context.shutdown()


def preflight(args, graph, stop, discovery_seconds=2.0):
    if len(os.environ.get('KSMC_VISION_API_TOKEN', '')) < 32:
        raise RuntimeError('Missing fixed Vision API token; do not rotate the teammate token')
    for _, argv in commands(args):
        if not os.access(argv[0], os.X_OK):
            raise RuntimeError(f'Missing executable: {argv[0]}')
    existing = existing_local_servers()
    if existing:
        raise RuntimeError('Existing server(s) left running; no takeover: ' + '; '.join(existing))
    check_lock(CAMERA_LOCK)
    check_port(args.host, args.port)
    # rclpy's graph API reports service clients and service servers together.
    # A remote Sequencer client therefore looks like an existing server and can
    # incorrectly block startup. Local process/port checks above are the safe
    # duplicate guards; service names are readiness hints only.
    if discovery_seconds > 0:
        stop.wait(min(discovery_seconds, 2.0))


def group_alive(child):
    child.poll()  # reap the leader, if already exited
    try:
        os.killpg(child.pid, 0)
        return True
    except ProcessLookupError:
        return False


def signal_owned(child, sig):
    try:
        os.killpg(child.pid, sig)
    except ProcessLookupError:
        pass


def cleanup(children, grace=8.0):
    # Each child was started in its own session; never use pkill or process-name kills.
    for sig, wait_seconds in ((signal.SIGINT, grace), (signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
        for _, child in children:
            if group_alive(child):
                signal_owned(child, sig)
        deadline = time.monotonic() + wait_seconds
        while any(group_alive(child) for _, child in children) and time.monotonic() < deadline:
            time.sleep(0.05)
    for _, child in children:
        child.wait(timeout=1)


def supervise(specs, ready, stop, startup_timeout, popen=subprocess.Popen, interval=0.2):
    children = []
    try:
        for name, argv in specs:
            if stop.is_set():
                return 130
            child = popen(argv, cwd=ROOT, start_new_session=True)
            children.append((name, child))
            print(f'[CELL] Started {name} PID {child.pid}', flush=True)
        deadline = time.monotonic() + startup_timeout
        announced = False
        while not stop.is_set():
            for name, child in children:
                code = child.poll()
                if code is not None:
                    raise RuntimeError(f'{name} exited ({code}); stopping only bundle-owned peers, no restart')
            if not announced:
                if ready():
                    print('[CELL] Servers listening. Not a camera/FR5 readiness or motion authorization check.', flush=True)
                    print('[CELL] Arrival alone does not capture; Sequencer must POST inspection request.', flush=True)
                    announced = True
                elif time.monotonic() >= deadline:
                    raise RuntimeError('Server startup timed out; no automatic restart')
            stop.wait(interval)
        return 130
    finally:
        cleanup(children)


def main(argv=None):
    args = parse_args(argv)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    lock = None
    try:
        if not args.check:
            path = ROOT/'runtime/server_bundle/servers.lock'
            path.parent.mkdir(parents=True, exist_ok=True)
            lock = path.open('a+')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('Another bundle is running; it was not interrupted') from exc
        with RosGraph() as graph:
            preflight(args, graph, stop)
            if stop.is_set():
                return 130
            mode = 'ARMED (S22 interlocks retained; FR5 permission removed)' if args.execute else 'MONITOR-ONLY'
            print(f'[CELL] Preflight clear: domain={os.environ.get("ROS_DOMAIN_ID", "5")}, '
                  f'HTTP={args.host}:{args.port}, {mode}; token not displayed.', flush=True)
            if args.check:
                print('[CELL] Check only: neither server was started.', flush=True)
                return 0
            return supervise(commands(args), lambda: port_open(args.host, args.port)
                             and bool(existing_local_servers()),
                             stop, args.startup_timeout)
    except (RuntimeError, OSError, ImportError) as exc:
        print(f'[CELL] ERROR: {exc}. Pre-existing servers were not signalled.', flush=True)
        return 2
    finally:
        if lock:
            lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
