"""Supervise ROS conveyor/inspection servers and start or reuse GoPro.

Never signal or restart a pre-existing process. S22 and the teammate Endpoint
remain externally managed. No motion or inspection service calls are made.
"""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SERVICES = frozenset('/conveyor/' + name for name in (
    'move_to_assembly', 'move_to_inspection', 'stop', 'reset'))
INSPECTION_SERVICES = {
    '/vision/inspection/submit': 'vision_interfaces/srv/SubmitInspection',
    '/vision/inspection/get': 'vision_interfaces/srv/GetInspection',
    '/vision/inspection/get_image': 'vision_interfaces/srv/GetInspectionImage',
    '/vision/inspection/health': 'std_srvs/srv/Trigger',
}
CAMERA_LOCK = ROOT / 'runtime/s22_camera_control/auto_inspection_trigger.lock'
GOPRO_TOPIC = '/camera3/image_raw/compressed'
GOPRO_ALREADY_RUNNING = 73


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--monitor-only', action='store_true', help='Default: reject motion requests')
    mode.add_argument('--execute', action='store_true', help='Allow guarded remote motion requests')
    parser.add_argument('--confirm-motion', action='store_true')
    parser.add_argument('--check', action='store_true', help='Read-only preflight; start no process')
    parser.add_argument('--without-gopro', action='store_true', help='Start only the two ROS servers')
    parser.add_argument('--gopro-transport', choices=('wifi', 'usb'), default='wifi')
    parser.add_argument('--gopro-startup-timeout', type=float, default=45,
                        help='Maximum startup wait including a received GoPro frame')
    parser.add_argument('--timeout', type=float, default=300, help='Existing inspection execution timeout')
    parser.add_argument('--startup-timeout', type=float, default=20)
    args = parser.parse_args(argv)
    if args.execute != args.confirm_motion:
        parser.error('Motion requires both --execute and --confirm-motion')
    if (not 0 < args.timeout <= 3600 or not 1 <= args.startup_timeout <= 120
            or not 1 <= args.gopro_startup_timeout <= 120):
        parser.error('Invalid timeout; startup timeout must be 1..120 seconds')
    return args


def commands(args, root=ROOT, *, reuse_gopro=False):
    motion = ['--execute', '--confirm-motion'] if args.execute else ['--monitor-only']
    specs = [
        ('conveyor', [str(root/'run_conveyor_remote_server.sh'), *motion]),
        ('inspection', [str(root/'vision_assembly/run_conveyor_inspection_trigger.sh'),
                        '--timeout', str(args.timeout)]),
    ]
    if not args.without_gopro and not reuse_gopro:
        script = 'run_gopro_camera3_wifi.sh' if args.gopro_transport == 'wifi' else 'run_gopro_camera3.sh'
        specs.append(('gopro', [str(root / 'gopro_camera3' / script)]))
    return specs


def gopro_running(proc_root=Path('/proc'), root=ROOT):
    """Handle both launcher spellings and a directly launched camera node."""
    lock_path = root / 'runtime/gopro_camera3.lock'
    if lock_path.exists():
        with lock_path.open('r') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    targets = {root / 'gopro_camera3' / name for name in (
        'run_gopro_camera3.sh', 'run_gopro_camera3_wifi.sh', 'notebooks/gopro_camera3_node.py')}
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            cwd = (entry / 'cwd').resolve()
            args = (entry / 'cmdline').read_bytes().split(b'\0')
            for arg in args:
                path = Path(arg.decode(errors='replace')) if arg else None
                if path and path.name in ('run_gopro_camera3.sh', 'run_gopro_camera3_wifi.sh', 'gopro_camera3_node.py'):
                    if (path if path.is_absolute() else cwd / path).resolve() in targets:
                        return True
        except (OSError, RuntimeError):
            continue
    return False


def existing_local_servers(proc_root=Path('/proc')):
    """Exact argv basename matches; never print argv (credentials may be present)."""
    targets = {'conveyor_remote_server', 'inspection_api.py', 'inspection_ros.py', 'conveyor_inspection_trigger.py'}
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


def check_interfaces():
    try:
        from vision_interfaces.srv import SubmitInspection, GetInspection, GetInspectionImage
        # Resolve native type support too, before starting an armed controller.
        from rclpy.type_support import check_for_type_support
        for service in (SubmitInspection, GetInspection, GetInspectionImage):
            check_for_type_support(service)
    except (ImportError, AttributeError) as exc:
        raise RuntimeError('Build vision_interfaces and source ros2_ws/install/setup.bash first') from exc


class RosGraph:
    """Read-only graph discovery and optional GoPro frame subscription."""
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
        # Per-node server discovery excludes service clients in a Sequencer.
        found = set()
        for node_name, expected in (
                ('conveyor_remote_server', {name: 'std_srvs/srv/Trigger' for name in SERVICES}),
                ('vision_inspection_server', INSPECTION_SERVICES)):
            try:
                entries = self.node.get_service_names_and_types_by_node(node_name, '/')
            except self.rclpy.node.NodeNameNonExistentError:
                continue
            found.update(name for name, types in entries
                         if name in expected and expected[name] in types)
        return found

    def ready(self):
        return SERVICES | set(INSPECTION_SERVICES) <= self.services()

    def gopro_publisher_exists(self):
        return any(e.topic_type == 'sensor_msgs/msg/CompressedImage'
                   for e in self.node.get_publishers_info_by_topic(GOPRO_TOPIC))

    def watch_gopro(self):
        from sensor_msgs.msg import CompressedImage
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        self.last_gopro_frame = None
        def received(message):
            # A topic in the graph alone is not evidence of a live camera.
            if len(message.data) > 4:
                self.last_gopro_frame = time.monotonic()
        self.gopro_subscription = self.node.create_subscription(
            CompressedImage, GOPRO_TOPIC, received,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.executor = SingleThreadedExecutor(context=self.context)
        self.executor.add_node(self.node)

    def gopro_ready(self):
        self.executor.spin_once(timeout_sec=0)
        return self.last_gopro_frame is not None and time.monotonic() - self.last_gopro_frame < 2

    def __exit__(self, *_):
        try:
            try:
                if getattr(self, 'executor', None) is not None:
                    self.executor.shutdown()
            finally:
                self.node.destroy_node()
        finally:
            self.context.shutdown()


def preflight(args, graph, stop, discovery_seconds=2.0):
    for _, argv in commands(args):
        if not os.access(argv[0], os.X_OK):
            raise RuntimeError(f'Missing executable: {argv[0]}')
    existing = existing_local_servers()
    if existing:
        raise RuntimeError('Existing server(s) left running; no takeover: ' + '; '.join(existing))
    check_lock(CAMERA_LOCK)
    check_interfaces()
    # rclpy's graph API reports service clients and service servers together.
    # A remote Sequencer client therefore looks like an existing server and can
    # incorrectly block startup. Local process/lock checks above are the safe
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


def supervise(specs, ready, stop, startup_timeout, popen=subprocess.Popen, interval=0.2,
              reuse_after_exit=None):
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
            for name, child in list(children):
                code = child.poll()
                if code is not None:
                    if reuse_after_exit and reuse_after_exit(name, code):
                        children.remove((name, child))
                        print(f'[CELL] {name} was started concurrently; reusing external process.', flush=True)
                        continue
                    raise RuntimeError(f'{name} exited ({code}); stopping only bundle-owned peers, no restart')
            if not announced:
                if ready():
                    print('[CELL] ROS services ready; enabled GoPro stream received. No motion authorized by this check.', flush=True)
                    print('[CELL] Arrival alone does not capture; Sequencer must call /vision/inspection/submit.', flush=True)
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
                  f'ROS services, {mode}.', flush=True)
            if args.check:
                print('[CELL] Check only: no server or camera was started.', flush=True)
                return 0
            reuse_gopro = False
            if not args.without_gopro:
                reuse_gopro = gopro_running() or graph.gopro_publisher_exists()
                graph.watch_gopro()
                print('[CELL] GoPro: ' + ('reuse existing; leave running on exit' if reuse_gopro
                      else f'start {args.gopro_transport}; owned by this bundle'), flush=True)
            timeout = args.startup_timeout if args.without_gopro else max(
                args.startup_timeout, args.gopro_startup_timeout)
            def ready():
                camera_ready = args.without_gopro or graph.gopro_ready()
                return graph.ready() and camera_ready
            def reuse_after_exit(name, code):
                return name == 'gopro' and code == GOPRO_ALREADY_RUNNING and gopro_running()
            return supervise(commands(args, reuse_gopro=reuse_gopro), ready,
                             stop, timeout, reuse_after_exit=reuse_after_exit)
    except (RuntimeError, OSError, ImportError) as exc:
        print(f'[CELL] ERROR: {exc}. Pre-existing servers were not signalled.', flush=True)
        return 2
    finally:
        if lock:
            lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
