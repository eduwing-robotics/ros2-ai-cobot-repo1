"""Durable API adapter around the existing fresh-observation cycle launcher.

Never accepts TCPs, recipe paths, arbitrary shell commands or cached plans.
Motion completion is deliberately distinct from physical placement acceptance.
"""
from contextlib import contextmanager, ExitStack
import copy
import fcntl
import json
import hashlib
import os
import re
from pathlib import Path
import signal
import subprocess
import threading
import time
from uuid import UUID, uuid4

from .real_backend import BackendFailure

SCHEMA = 'fr5.assembly_cycle/v1'
ACTIVE = {'starting', 'running', 'pause_requested', 'paused', 'resume_requested', 'stop_requested', 'recovery_required'}
SLOTS = {
    'GPU': ['GPU-01'], 'HBM': [f'HBM-{i:02}' for i in range(1, 9)],
    'PM': [f'PM-{i:02}' for i in range(1, 5)],
    'VRM': [f'VRM-{i:02}' for i in range(1, 6)],
    'IND': ['IND-01', 'IND-02'], 'SMD': [f'CAP-{i:02}' for i in range(1, 6)],
}
SLOTS['full'] = [slot for slots in SLOTS.values() for slot in slots]



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
    delegated = delegated_owner()  # stale leases also block after lock loss
    for record_path in (Path(root) / 'runtime/assembly_api').glob('*.json'):
        record = read(record_path)
        if (record.get('execution_context') and record.get('status') in ACTIVE
                and not (delegated and job_id == record.get('operation_id'))):
            raise BackendFailure('ROBOT_BUSY', 'unresolved production execution owns robot')
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
    def __init__(self, root, ready, publish, popen=subprocess.Popen, allow_batch_start=True, allow_production_start=False, attachment_snapshot=None, recovery_ready=None, reconcile_recovery=None):
        self.reconcile_recovery = reconcile_recovery
        self.recovery_ready = recovery_ready or ready
        self.attachment_snapshot = attachment_snapshot
        self.allow_batch_start = allow_batch_start
        self.allow_production_start = allow_production_start
        self.server_instance_id = str(uuid4())
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

    def _recover_before_motion(self):
        """Release only a proven pre-motion failure; never replay or clear faults."""
        if self.state.get('status') != 'recovery_required':
            return False
        if self.process is not None and self.process.poll() is None:
            return False
        # On restart, a surviving launcher must never be treated as a failure.
        if self.process is None and Path('/proc', str(self.state.get('pid', -1))).exists():
            return False
        directory = self.root/'runtime/assembly_cycles'/self.state['operation_id']
        runtime = directory.parent
        try:
            with ExitStack() as stack:
                for name in ('launcher.lock', 'step_operation.lock'):
                    stream = stack.enter_context((runtime/name).open('a'))
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                evidence = read(directory/'startup_safety.json')
                if (evidence.get('execution_id') != self.state['operation_id']
                        or evidence.get('assembly_motion_started') is not False
                        or evidence.get('activation_outcome_unknown') is not False
                        or (runtime/'step_api_owner.json').exists()
                        or (directory/'cycle.json').exists()
                        or self.state.get('completed_slots') or self.state.get('attachments')
                        or self.state.get('last_robot_event')):
                    return False
                self.ready()  # Fresh stationary/healthy state; no held part or backend recovery.
                self.state.update(status='failed_before_motion', resume_available=False,
                    auto_recovery=dict(recovered_unix=time.time(), reason='verified_no_assembly_motion',
                        previous_status='recovery_required', evidence=evidence,
                        retry_requires_new_execution_id=True))
                self._save()
                return True
        except (OSError, ValueError, KeyError, BackendFailure):
            return False

    def recover(self, operation_id, confirmation):
        """Acknowledge a cleared test scene, retaining results; never move hardware."""
        if str(UUID(operation_id)) != operation_id:
            raise ValueError('operation_id must be a canonical UUID')
        if (not isinstance(confirmation, dict) or set(confirmation) !=
                {'operator_id', 'execution_id', 'confirmed_unix', 'scope'}
                or not isinstance(confirmation['operator_id'], str)
                or not confirmation['operator_id'].strip()
                or confirmation['execution_id'] != operation_id
                or confirmation['scope'] != 'empty_gripper_empty_pcb_full_tray_fixed_fixture'
                or type(confirmation['confirmed_unix']) not in (int, float)
                or not 0 <= time.time() - confirmation['confirmed_unix'] <= 120):
            raise ValueError('fresh operator scene confirmation for this execution is required')
        with self.lock:
            if operation_id != self.state.get('operation_id'):
                raise BackendFailure('EXECUTION_ID_CONFLICT', 'recover must identify the current execution')
            if self.state['status'] not in {'recovery_required', 'failed_before_motion',
                    'failed_recovered', 'check_failed', 'check_completed',
                    'motion_complete_awaiting_physical_verification'}:
                raise BackendFailure('ROBOT_BUSY', 'execution must end before recovery')
            if ((self.process is not None and self.process.poll() is None)
                    or (self.thread is not None and self.thread.is_alive())
                    or (self.process is None and Path('/proc', str(self.state.get('pid', -1))).exists())):
                raise BackendFailure('ROBOT_BUSY', 'execution worker is still alive')
            runtime = self.root/'runtime/assembly_cycles'
            runtime.mkdir(parents=True, exist_ok=True)
            try:
                with ExitStack() as stack:
                    for name in ('launcher.lock', 'step_operation.lock'):
                        stream = stack.enter_context((runtime/name).open('a'))
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if self.reconcile_recovery is None and (runtime/'step_api_owner.json').exists():
                        raise BackendFailure('RECOVERY_BLOCKED',
                            'step operation ownership remains; reconcile held part and step journal first')
                    for path in self.directory.glob('*.json'):
                        other = read(path)
                        if other.get('operation_id') != operation_id and other.get('status') in ACTIVE:
                            raise BackendFailure('RECOVERY_BLOCKED', 'another unresolved execution remains')
                    if self.reconcile_recovery is not None:
                        self.reconcile_recovery(operation_id, confirmation)
                    # Verify the reconciled backend before releasing the whole execution.
                    self.recovery_ready()
                    previous = self.state['status']
                    failure = self._failure_details(self.state)
                    if previous == 'recovery_required':
                        self.state['status'] = 'failed_recovered'
                    if failure is not None:
                        self.state['failure'] = failure
                    self.state.update(resume_available=False, recovery=dict(
                        recovered_unix=time.time(), previous_status=previous,
                        scene_confirmation=copy.deepcopy(confirmation),
                        reason='operator_reset_test_scene_and_robot_ready',
                        motion_sent=False, retry_requires_new_execution_id=True))
                    self._save()
            except BlockingIOError as error:
                raise BackendFailure('ROBOT_BUSY', 'an actuator worker still owns execution') from error
            return dict(self.snapshot(), request_accepted=True, recovery_applied=True,
                        recovery_required=False, retry_requires_new_execution_id=True)

    def _failure_details(self, state):
        """Bounded diagnostic summary for terminal failures, including old runs."""
        if state.get('status') not in ('recovery_required', 'failed_before_motion', 'failed_recovered', 'check_failed'):
            return None
        if isinstance(state.get('failure'), dict):
            return copy.deepcopy(state['failure'])
        operation_id = state.get('operation_id')
        if not operation_id:
            return None
        directory = self.root/'runtime/assembly_cycles'/operation_id
        stage = state.get('step') or 'startup'
        message = state.get('evidence_error') or state.get('message') or 'Execution process failed; detailed log unavailable'
        try:
            cycle = read(directory/'cycle.json')
            message = cycle.get('error') or message
            if cycle.get('steps'):
                stage = cycle['steps'][-1]['name']
        except (OSError, ValueError, KeyError, TypeError):
            pass
        log = self.directory/(operation_id+'.log')
        if isinstance(stage, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', stage):
            step_log = directory/(stage+'.log')
            if step_log.is_file():
                log = step_log
        error_type = None
        try:
            with log.open('rb') as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(max(0, size-16384))
                tail = stream.read(16384).decode('utf-8', errors='replace')
            # Return only the exception summary, never an entire traceback or
            # arbitrary stdout containing camera data, request bodies, etc.
            errors = re.findall(r'^([\w.]*(?:Error|Exception|Interrupt)):\s*(.+)$', tail, re.MULTILINE)
            if errors:
                error_type, message = errors[-1]
            else:
                stopped = re.findall(r'^중단:\s*(.+)$', tail, re.MULTILINE)
                if stopped:
                    message = stopped[-1]
        except OSError:
            pass
        message = str(message)[:2048]
        code = ('MOTION_PLAN_REJECTED' if 'motion plan rejected:' in message
                or error_type == 'full_cycle_motion.MotionPlanError' else 'EXECUTION_PROCESS_FAILED')
        return dict(code=code, stage=stage, message=message, error_type=error_type,
                    returncode=state.get('returncode'), log_path=str(log.relative_to(self.root)))

    def revision(self):
        return read(self.root / 'vision_assembly/config/assembly_launcher_revision.json')['revision']

    def snapshot(self, operation_id=None):
        """Read a retained execution without changing the current execution."""
        with self.lock:
            if operation_id is None:
                result = copy.deepcopy(self.state)
            else:
                if str(UUID(operation_id)) != operation_id:
                    raise ValueError('operation_id must be a canonical UUID')
                path = self.directory / (operation_id + '.json')
                result = read(path) if path.exists() else dict(
                    schema=SCHEMA, status='not_found', operation_id=operation_id)
        result['failure'] = self._failure_details(result)
        result['server_instance_id'] = self.server_instance_id
        result['response_generated_unix'] = time.time()
        result['current_recipe_revision'] = self.revision()
        result.setdefault('recipe_revision', result.get('request', {}).get('recipe_revision', result['current_recipe_revision']))
        result['capabilities'] = dict(start=self.allow_batch_start, pause=False,
                                    resume=False, status=True, event=True,
                                    query_execution=True, recover=True, manual_stop_recovery=self.reconcile_recovery is not None)
        result['resume_available'] = bool(result.get('resume_available')) and result['status']=='paused'
        result['record_retention'] = 'no_automatic_deletion; unresolved_execution_blocks_replay'
        result['supported_actions'] = (['assembly.start'] if self.allow_batch_start else []) + ['assembly.check', 'assembly.stop', 'assembly.status', 'assembly.recover']
        result['scope'] = 'local_diagnostics_only_not_sequencer_production' if not self.allow_batch_start else 'validated_launcher_and_named_group_tests'
        result['profiles'] = ['full','GPU','HBM','PM','VRM','IND','SMD']
        result['external_stages_included'] = False
        return result

    def command(self, raw, *, execution_context=None):
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if data.get('schema') == SCHEMA and data.get('action') == 'assembly.recover':
            if set(data) != {'schema', 'action', 'operation_id', 'scene_confirmation'}:
                raise ValueError('recover requires operation_id and scene_confirmation only')
            return self.recover(data['operation_id'], data['scene_confirmation'])
        allowed = {'schema', 'action', 'job_id', 'operation_id', 'recipe_revision', 'confirm_scene_ready', 'profile'}
        if set(data) - allowed or data.get('schema') != SCHEMA:
            raise ValueError('invalid schema or unsupported fields')
        if data.get('action') == 'assembly.status':
            if set(data) != {'schema', 'action', 'operation_id'}:
                raise ValueError('status requires only schema, action, operation_id')
            return self.snapshot(data['operation_id'])
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
                if record['request'] != data or record.get('execution_context') != execution_context:
                    raise ValueError('operation_id already used with different content')
                return record  # Durable same-request replay, never another launch.
            self._recover_before_motion()
            if self.state['status'] in ACTIVE:
                raise BackendFailure('ROBOT_BUSY', 'assembly cycle is active or unresolved')
            checking = data['action'] == 'assembly.check'
            if not checking and not (self.allow_batch_start or
                    (execution_context is not None and self.allow_production_start)):
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
                completed_slots=[], expected_slots=list(SLOTS[profile]),
                recipe_revision=data['recipe_revision'],
                origin_server_instance_id=self.server_instance_id,
                server_pid=os.getpid(), server_process_start=Path(f'/proc/{os.getpid()}/stat').read_text().split()[21],
                execution_kind='production' if execution_context is not None else ('diagnostic' if checking else 'local_assembly'),
                execution_context=copy.deepcopy(execution_context),
                physical_placement_verified=False, profile=profile)
            self._save()  # Durable intent before starting any child.
            try:
                log = (self.directory / (run_id + '.log')).open('ab')
                try:
                    env = dict(os.environ, FASTDDS_BUILTIN_TRANSPORTS='UDPv4')
                    if execution_context is not None:
                        env.update(FR5_ASSEMBLY_CONTROL_RECORD=str(path), FR5_ASSEMBLY_EXECUTION_ID=run_id)
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
        self.state['event_sequence'] = self.state.get('event_sequence', 0) + 1
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
        if self.state.get('execution_context'):
            result['plan_hashes'] = dict(self.state.get('plan_hashes', {}))
            for phase in ('non-smd', 'smd'):
                plan = directory / (phase + '_plan.json')
                if plan.exists():
                    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
                    previous = result['plan_hashes'].setdefault(phase, digest)
                    if previous != digest:
                        result['evidence_error'] = 'frozen plan changed: ' + phase
        return result

    def _production_completion(self):
        directory = Path(self.state['run_directory'])
        try:
            if self.state.get('evidence_error'):
                raise ValueError(self.state['evidence_error'])
            hashes = self.state.get('plan_hashes', {})
            if set(hashes) != {'non-smd', 'smd'}:
                raise ValueError('both phase plans must be pinned')
            for phase, expected in (('non-smd', SLOTS['full'][:-5]), ('smd', SLOTS['SMD'])):
                run = read(directory / (phase + '_run.json'))
                if (run.get('job_id') != self.state['operation_id']
                        or run.get('plan_sha256') != hashes[phase]
                        or run.get('selected_slots') != expected
                        or run.get('status') != 'motion_complete_awaiting_physical_verification'
                        or run.get('part_held_candidate') is not False):
                    raise ValueError('phase completion identity/evidence mismatch: ' + phase)
            release = read(directory / 'api_release_check.json')
            if release.get('returncode') != 0:
                raise ValueError('final API readiness check failed')
            feedback = json.loads(release['stdout'])
            if (feedback.get('state_fresh') is not True
                    or feedback.get('robot_health_clear') is not True
                    or feedback.get('robot_motion_done') != 1
                    or feedback.get('gripper_feedback_valid') is not True
                    or feedback.get('active_operation') is not None
                    or feedback.get('held_candidate') is not None
                    or feedback.get('recovery_required') is not False
                    or not self.state['started_unix'] <= feedback.get('observed_unix', 0) <= time.time()):
                raise ValueError('final stationary/empty/fresh evidence missing')
            photo = read(directory / 'after/PlaceCamera_camera_stage.json')
            if (photo.get('status') != 'captured' or photo.get('execution_backend') != 'single_step_api'
                    or not self.state['started_unix'] <= photo.get('finished_unix', 0) <= feedback['observed_unix']):
                raise ValueError('final PlaceCamera capture evidence missing')
            if self.attachment_snapshot is None:
                raise ValueError('authoritative attachment snapshot unavailable')
            attachment_state = self.attachment_snapshot()
            attachments = [item for item in attachment_state['attachments']
                           if item.get('job_id') == self.state['operation_id']]
            self.state['attachments'] = copy.deepcopy(attachments)
            if (len(attachments) != len(SLOTS['full'])
                    or {item.get('slot_code') for item in attachments} != set(SLOTS['full'])
                    or any(item.get('state') != 'placed' or item.get('uncertain')
                           or item.get('attachment_binding_valid') is not True for item in attachments)):
                raise ValueError('authoritative placed bindings are incomplete or uncertain')
            self.state['completion_evidence'] = dict(
                stop_verified=True, feedback=feedback, end_location='PlaceCamera',
                target_tcp_mm_deg=photo.get('target'), plan_hashes=hashes,
                verification_level='motion_complete_not_physical_placement_or_inspection')
            return True
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.state['evidence_error'] = str(error)
            return False

    def _monitor(self):
        while True:
            try:
                with self.lock:
                    if self.state.get('finished_unix') is not None:
                        return  # A late poll cannot replace a committed terminal.
                    progress = self._progress()
                    if any(self.state.get(key) != value for key, value in progress.items()):
                        self.state.update(progress)
                        self._save()
                    code = self.process.poll()
                    if code is not None:
                        complete = (code == 0 and self.state.get('launcher_status') ==
                            'motion_complete_awaiting_physical_verification' and
                            set(self.state['completed_slots']) == set(SLOTS[self.state['profile']]) and
                            len(self.state['completed_slots']) == len(SLOTS[self.state['profile']]))
                        if complete and self.state.get('execution_context'):
                            complete = self._production_completion()
                        checking = self.state['request']['action'] == 'assembly.check'
                        final_status = ('check_completed' if code == 0 else 'check_failed') if checking else ('motion_complete_awaiting_physical_verification' if complete else 'recovery_required')
                        self.state.update(status=final_status,
                                          returncode=code, finished_unix=time.time())
                        self.state['failure'] = self._failure_details(self.state)
                        self._save()
                    if code is not None:
                        self._recover_before_motion()
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
                        if self.state.get('finished_unix') is None:
                            self.state.update(status='recovery_required', finished_unix=time.time(),
                                              returncode=self.process.poll())
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
