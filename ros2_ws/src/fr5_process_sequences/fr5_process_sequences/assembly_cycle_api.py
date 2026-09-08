"""Durable API adapter around the existing fresh-observation cycle launcher.

Never accepts TCPs, recipe paths, arbitrary shell commands or cached plans.
Motion completion is deliberately distinct from physical placement acceptance.
"""
from contextlib import contextmanager
import copy
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from uuid import UUID

from .real_backend import BackendFailure

SCHEMA = 'fr5.assembly_cycle/v1'
ACTIVE = {'starting', 'running', 'stop_requested', 'recovery_required'}


@contextmanager
def robot_execution_guard(root, job_id=None):
    path = Path(root) / 'runtime/assembly_cycles/launcher.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    lease_path = path.parent / 'step_api_owner.json'
    def delegated_owner():
        if not lease_path.exists():return False
        lease = read(lease_path)
        pid = int(lease['pid'])
        process = Path('/proc')/str(pid)/'stat'
        live = process.exists() and process.read_text().split()[21] == lease['process_start']
        if not live or job_id != lease['job_id']:
            raise BackendFailure('ROBOT_BUSY', 'step API cycle owns robot or requires recovery')
        return True
    delegated_owner()  # stale leases also block when the original lock has disappeared
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            if not delegated_owner():
                raise BackendFailure('ROBOT_BUSY', 'cycle launcher owns robot execution') from error
        with (path.parent/'step_operation.lock').open('a') as operation_lock:
            try:fcntl.flock(operation_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise BackendFailure('ROBOT_BUSY', 'another step actuator operation is active') from error
            yield


def read(path):
    return json.loads(Path(path).read_text())


def persist(path, payload):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class AssemblyCycleController:
    def __init__(self, root, ready, publish, popen=subprocess.Popen, allow_batch_start=True):
        self.allow_batch_start = allow_batch_start
        self.root = Path(root).resolve()
        self.ready, self.publish, self.popen = ready, publish, popen
        self.directory = self.root / 'runtime/assembly_api'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.process = None
        self.thread = None
        self.state = {'schema': SCHEMA, 'status': 'idle', 'physical_placement_verified': False}
        # Never restart an interrupted physical operation, even after API restart.
        records = sorted(self.directory.glob('*.json'), key=lambda p: p.stat().st_mtime)
        for path in records:
            record = read(path)
            if record['status'] in ACTIVE:
                record['status'] = 'recovery_required'
                record['message'] = 'API restarted with unresolved cycle; inspect robot and execution logs. No automatic replay.'
                persist(path, record)
                self.state = record
                break
        else:
            if records:
                self.state = read(records[-1])

    def revision(self):
        return read(self.root / 'vision_assembly/config/assembly_launcher_revision.json')['revision']

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.state)
        result['recipe_revision'] = self.revision()
        result['supported_actions'] = (['assembly.start'] if self.allow_batch_start else []) + ['assembly.check', 'assembly.stop']
        result['scope'] = 'local_diagnostics_only_not_sequencer_production' if not self.allow_batch_start else 'validated_launcher_and_named_group_tests'
        result['profiles'] = ['full','GPU','HBM','PM','VRM','IND','SMD']
        result['external_stages_included'] = False
        return result

    def command(self, raw):
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        allowed = {'schema', 'action', 'job_id', 'operation_id', 'recipe_revision', 'confirm_scene_ready', 'profile'}
        if set(data) - allowed or data.get('schema') != SCHEMA:
            raise ValueError('invalid schema or unsupported fields')
        for key in ('job_id', 'operation_id'):
            if str(UUID(data[key])) != data[key]:
                raise ValueError('IDs must be canonical UUIDs')
        with self.lock:
            if data.get('action') == 'assembly.stop':
                if (data['job_id'], data['operation_id']) != (self.state.get('job_id'), self.state.get('operation_id')):
                    raise ValueError('stop must identify the current cycle')
                if self.process is not None and self.process.poll() is None:
                    self.state['status'] = 'stop_requested'
                    self._save()
                    # The launcher forwards interruption to its current executor,
                    # which performs the existing bounded controller StopMotion.
                    try:
                        self.process.send_signal(signal.SIGINT)
                    except ProcessLookupError:
                        pass
                return self.snapshot()
            if data.get('action') not in ('assembly.start', 'assembly.check'):
                raise ValueError('unsupported assembly action')
            path = self.directory / (data['operation_id'] + '.json')
            if path.exists():
                record = read(path)
                if record['request'] != data:
                    raise ValueError('operation_id already used with different content')
                return record  # Durable same-request replay, never another launch.
            if self.state['status'] in ACTIVE:
                raise BackendFailure('ROBOT_BUSY', 'assembly cycle is active or unresolved')
            checking = data['action'] == 'assembly.check'
            if not checking and not self.allow_batch_start:
                raise BackendFailure('SAFETY_STOP', 'Batch execution is retired from production integration. Sequencer owns ordering via /real/robot/command.')
            profile = data.get('profile', 'full')
            if profile not in ('full','GPU','HBM','PM','VRM','IND','SMD') or (checking and profile != 'full'):
                raise ValueError('unsupported test profile')
            if (not checking and data.get('confirm_scene_ready') is not True) or data.get('recipe_revision') != self.revision():
                raise ValueError('current recipe revision and explicit scene-ready confirmation required')
            if not checking:
                self.ready()
            # Readiness probe only; the child launcher owns the execution lock.
            # If a local operation wins the race afterwards, the child fails closed.
            with robot_execution_guard(self.root):
                pass
            run_id = data['operation_id']
            self.state = dict(schema=SCHEMA, status='starting', job_id=data['job_id'],
                operation_id=run_id, request=data, started_unix=time.time(),
                run_directory=str(self.root / 'runtime/assembly_cycles' / run_id),
                completed_slots=[], physical_placement_verified=False, profile=profile)
            self._save()  # Durable intent before starting any child.
            try:
                log = (self.directory / (run_id + '.log')).open('ab')
                try:
                    env = dict(os.environ, FASTDDS_BUILTIN_TRANSPORTS='UDPv4')
                    self.process = self.popen(['bash', str(self.root / 'scripts/run_assembly_cycle_worker.sh'),
                        '--expected-revision', data['recipe_revision'], '--profile', profile,
                        '--check' if checking else '--execute', '--run-id', run_id], cwd=self.root,
                        env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                finally:
                    log.close()
                self.state.update(status='running', pid=self.process.pid)
                self._save()
                self.thread = threading.Thread(target=self._monitor, daemon=True, name='assembly-cycle-monitor')
                self.thread.start()
            except Exception as error:
                self.state.update(status='recovery_required', message=str(error))
                self._save()
                raise
            return self.snapshot()

    def _save(self):
        self.state['updated_unix'] = time.time()
        persist(self.directory / (self.state['operation_id'] + '.json'), self.state)

    def _progress(self):
        directory = Path(self.state['run_directory'])
        result = {'completed_slots': []}
        cycle = directory / 'cycle.json'
        if cycle.exists():
            record = read(cycle)
            result['launcher_status'] = record['status']
            if record.get('steps'):
                result['step'] = record['steps'][-1]['name']
        for phase in ('non-smd', 'smd'):
            path = directory / (phase + '_run.json')
            if not path.exists():
                continue
            record = read(path)
            result['completed_slots'] += record.get('motion_completed_slots', [])
            waypoint = record.get('last_verified_waypoint')
            if waypoint:
                result['last_verified_waypoint'] = {k: waypoint.get(k) for k in ('command_id', 'slot', 'waypoint', 'status')}
            result['held_candidate'] = record.get('part_held_candidate')
        return result

    def _monitor(self):
        while True:
            try:
                with self.lock:
                    self.state.update(self._progress())
                    code = self.process.poll()
                    if code is not None:
                        complete = (code == 0 and self.state.get('launcher_status') ==
                            'motion_complete_awaiting_physical_verification' and
                            len(set(self.state['completed_slots'])) == {'full':25,'GPU':1,'HBM':8,'PM':4,'VRM':5,'IND':2,'SMD':5}[self.state['profile']])
                        checking = self.state['request']['action'] == 'assembly.check'
                        final_status = ('check_completed' if code == 0 else 'check_failed') if checking else ('motion_complete_awaiting_physical_verification' if complete else 'recovery_required')
                        self.state.update(status=final_status,
                                          returncode=code, finished_unix=time.time())
                        self._save()
                    snapshot = self.snapshot()
                self.publish(snapshot)
                if code is not None:
                    return
            except Exception as error:
                # Do not abandon supervision because of a temporary read/publish error.
                with self.lock:
                    self.state['monitor_error'] = str(error)
                if self.process.poll() is not None:
                    with self.lock:
                        self.state['status'] = 'recovery_required'
                        self._save()
                    return
            time.sleep(.5)

    def close(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.state['status'] = 'stop_requested'
                self._save()
                self.process.send_signal(signal.SIGINT)
        if self.thread is not None:
            self.thread.join(timeout=25)
