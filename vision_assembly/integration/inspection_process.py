"""Private pipe-connected inspection worker; no network or ROS endpoint."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]


class InspectionProcess:
    def __init__(self, lock_fd, command=None):
        self.lock_fd = lock_fd
        self.command = command or [str(ROOT / 'vision_assembly/.venv_patchcore/bin/python'),
                                   str(Path(__file__).resolve())]
        self.child = None
        self.lock = threading.RLock()

    def close(self):
        with self.lock:
            child, self.child = self.child, None
            if child is None:
                return
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            finally:
                # Also retire descendants if the immediate worker exited first.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=3)
                child.stdin.close()
                child.stdout.close()

    def execute(self, argv, log_path, *, timeout, stop):
        with self.lock:
            if stop.is_set():
                raise RuntimeError('shutdown_before_capture')
            token = str(uuid.uuid4())
            task = dict(token=token, argv=list(argv), log=str(Path(log_path).resolve()))
            payload = (json.dumps(task) + '\n').encode()
            # A single request fits in the pipe's atomic-write capacity. There
            # is only one outstanding task, so sending cannot fill the pipe.
            if len(payload) > 4096:
                raise ValueError('inspection_worker_request_too_large')
            if self.child is not None and self.child.poll() is not None:
                self.close()
            if self.child is None:
                env = dict(os.environ, KSMC_VISION_EXPORT='0', HF_HUB_OFFLINE='1',
                           MPLCONFIGDIR=str(ROOT / 'vision_assembly/hybrid_inspection/.matplotlib'))
                env.pop('KSMC_VISION_CONTEXT_FILE', None)
                self.child = subprocess.Popen(
                    self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True,
                    env=env, pass_fds=(self.lock_fd,) if self.lock_fd >= 0 else ())
            deadline = time.monotonic() + timeout
            try:
                if os.write(self.child.stdin.fileno(), payload) != len(payload):
                    raise RuntimeError('incomplete_worker_request')
                data = bytearray()
                while b'\n' not in data:
                    if stop.is_set() or time.monotonic() >= deadline:
                        raise TimeoutError('shutdown_or_inspection_timeout')
                    ready, _, _ = select.select([self.child.stdout], [], [], .1)
                    if not ready:
                        continue
                    part = os.read(self.child.stdout.fileno(), 4096)
                    if not part:
                        raise RuntimeError('inspection_worker_exited')
                    data.extend(part)
                    if len(data) > 4096:
                        raise RuntimeError('invalid_worker_response')
                response = json.loads(data)
                if response.get('token') != token or response.get('ok') is not True:
                    raise RuntimeError('capture_or_inspection_failed; see execution.log')
            except BaseException:
                # No timed-out task or model state can leak into the next job.
                self.close()
                raise


def main():
    # Keep the protocol on a separate descriptor; native model/capture output
    # and subprocess output go to the current inspection's execution.log.
    replies = os.fdopen(os.dup(sys.stdout.fileno()), 'w', buffering=1)
    for line in sys.stdin:
        task = json.loads(line)
        with open(task['log'], 'wb', buffering=0) as log:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            try:
                for directory in ('inspection', 'hybrid_inspection'):
                    path = str(ROOT / 'vision_assembly' / directory)
                    if path not in sys.path:
                        sys.path.insert(0, path)
                from triggered_inspection_once import parse_args, run_pipeline
                from main import inspect_pcb
                from predict_component_patchcore import enable_model_cache
                enable_model_cache()
                args = parse_args(task['argv'])
                run_pipeline(args, inspector=lambda image: inspect_pcb(
                    image, output_root=args.report.parent))
                ok = True
            except BaseException:
                import traceback
                traceback.print_exc()
                ok = False
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
        replies.write(json.dumps(dict(token=task['token'], ok=ok)) + '\n')
        if not ok:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
