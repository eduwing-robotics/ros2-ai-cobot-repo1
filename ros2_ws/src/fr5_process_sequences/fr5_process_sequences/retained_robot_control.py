"""Correlated pause/resume of a live operation; never starts/replays a command."""
import json
import threading
import time
from uuid import UUID
from .real_contract import Event, OperationEvent


class RetainedRobotControl:
    def __init__(self, backend, *, enabled=False):
        self.backend = backend
        self.enabled = enabled
        self.lock = threading.RLock()
        self.blocked = threading.Event()
        self.state = 'RUNNING'
        self.operation = None
        self.pause_started = None
        self.paused_seconds = 0.
        self.results = {}
        self.last_sequence = {}
        self.last_result = None
        self.pause_gripper = None
        self.checks = {}

    def clock(self):
        with self.lock:
            now = time.monotonic()
            return now - self.paused_seconds - (now-self.pause_started if self.pause_started is not None else 0.)

    def register(self, operation, validator):
        self.checks[operation.operation_id] = validator

    def checkpoint(self):
        from .real_backend import BackendFailure
        while self.blocked.is_set():
            if self.backend._paused.is_set():
                raise BackendFailure('SAFETY_STOP', 'legacy stop/cancel requested during retained pause')
            operation = self.operation
            check = self.checks.get(operation.operation_id) if operation else None
            if check is not None: check()  # real wall time; never renew a vision plan
            time.sleep(.02)

    def status(self):
        with self.lock:
            op = self.operation
            return dict(supported=self.enabled, state=self.state, dispatch_blocked=self.blocked.is_set(),
                operation_id=op.operation_id if op else None,
                job_id=op.job_id if op else None,
                resume_supported=self.enabled,
                resume_available=not bool(self.reason()),
                resume_unavailable_reason=self.reason(), last_control=self.last_result)

    def reason(self):
        if not self.enabled: return 'retained_resume_not_commissioned'
        if self.backend._recovery_required: return 'recovery_required'
        if self.state != 'PAUSED': return 'no_confirmed_retained_pause'
        if self.operation is None: return 'missing retained operation'
        completed = self.backend._completed.get(self.operation.operation_id)
        if completed and completed[1].event is not Event.OPERATION_COMPLETED: return 'operation already failed'
        check = self.checks.get(self.operation.operation_id)
        if check is None: return 'execution context has no resume validator'
        try:
            check()
            self.backend._robot.assert_ready()
            state = self.backend._robot._fresh_state()
            if (not bool(state.gripper_feedback_valid) or int(state.gripperfaultnum)
                    or int(state.grippererro) or self.pause_gripper !=
                    (float(state.gripper_position), int(state.grip_motion_done))
                    or int(state.grip_motion_done) not in (1,2)):
                return 'gripper changed/unsettled during pause'
            if self.backend.held_part is not None and int(state.grip_motion_done) != 1:
                return 'held candidate lacks controller detection; recovery required'
        except Exception as error: return str(error)
        return ''

    def _reply(self, request, operation, event, reason='', **details):
        context = dict(control_id=request.get('control_id'),
            control_sequence=request.get('control_sequence'), control_action=request.get('command'),
            stop_verified=event is Event.PAUSE_CONFIRMED,
            resume_applied=event is Event.RESUME_CONFIRMED,
            robot_scope='robot_arm', reason=reason, **details)
        if operation is None:
            result = OperationEvent(str(request.get('job_id','')), str(request.get('operation_id','')),
                '', 'CONTROL', event, 'INVALID_REQUEST', json.dumps(context))
        else:
            result = self.backend._event(operation, phase=getattr(self.backend,'_phase_name','CONTROL'),
                event=event, error_code='' if event in (Event.PAUSE_CONFIRMED,Event.RESUME_CONFIRMED) else 'SAFETY_STOP',
                message=json.dumps(context))
        self.last_result = result.to_dict()
        self.backend._emit(result)
        return result

    def request(self, payload):
        from .real_backend import BackendFailure
        with self.lock:
            try:
                request = json.loads(payload) if isinstance(payload,str) else dict(payload)
                if set(request) != {'command','control_id','control_sequence','job_id','operation_id'}:
                    raise ValueError('control requires command, control_id, control_sequence, job_id, operation_id')
                for key in ('control_id','job_id','operation_id'):
                    if str(UUID(request[key])) != request[key]: raise ValueError('noncanonical '+key)
                if request['command'] not in ('pause','resume'): raise ValueError('unsupported control')
                if type(request['control_sequence']) is not int or request['control_sequence'] < 1:
                    raise ValueError('control_sequence must be positive integer')
            except (TypeError, ValueError, AttributeError) as error:
                return self._reply({}, None, Event.CONTROL_REJECTED, str(error))
            fingerprint = json.dumps(request, sort_keys=True)
            previous = self.results.get(request['control_id'])
            if previous:
                if previous[0] != fingerprint:
                    return self._reply(request,None,Event.CONTROL_REJECTED,'control_id content conflict')
                self.backend._emit(previous[1]); return previous[1]
            with self.backend._state_lock:
                active = self.backend._active
                completed = self.backend._completed.get(request['operation_id'])
            operation = active if active and active.operation_id == request['operation_id'] else self.operation
            reason = ''
            if not self.enabled: reason = 'retained_resume_not_commissioned; legacy stop remains available'
            elif operation is None or (operation.job_id,operation.operation_id) != (request['job_id'],request['operation_id']):
                reason = 'no matching retained operation; restart or new command cannot resume'
            elif active is not None and active.operation_id != operation.operation_id: reason = 'another operation is active'
            elif self.backend._recovery_required: reason = 'recovery_required'
            elif completed and completed[1].event is not Event.OPERATION_COMPLETED: reason = 'operation already failed'
            elif request['control_sequence'] <= self.last_sequence.get(request['job_id'],0): reason = 'stale control_sequence'
            if reason:
                result = self._reply(request,operation if operation and (operation.job_id, operation.operation_id) == (request['job_id'], request['operation_id']) else None,Event.CONTROL_REJECTED,reason)
            else:
                self.last_sequence[request['job_id']] = request['control_sequence']
                try:
                    if request['command'] == 'pause':
                        if self.blocked.is_set():
                            raise BackendFailure('SAFETY_STOP','pause already pending/confirmed; use original control_id')
                        self.operation = operation
                        self.blocked.set(); self.state = 'PAUSE_REQUESTED'
                        self.backend._robot.pause_motion()
                        observed = self.backend._robot.observe_stopped()
                        if observed != 'fresh_feedback_verified_stopped':
                            raise BackendFailure('SAFETY_STOP',observed)
                        state = self.backend._robot._fresh_state()
                        self.pause_gripper = (float(state.gripper_position), int(state.grip_motion_done))
                        self.state='PAUSED';self.pause_started=time.monotonic()
                        result=self._reply(request,operation,Event.PAUSE_CONFIRMED,
                            'fresh feedback verified robot arm stopped for 0.5 s', resume_available=not bool(self.reason()))
                    else:
                        if self.state != 'PAUSED' or not self.blocked.is_set():
                            raise BackendFailure('SAFETY_STOP','no confirmed retained pause')
                        check=self.checks.get(operation.operation_id)
                        if check is None: raise BackendFailure('SAFETY_STOP','execution context has no resume validator')
                        check()
                        self.backend._robot.assert_ready()
                        state = self.backend._robot._fresh_state()
                        if (not bool(state.gripper_feedback_valid) or int(state.gripperfaultnum)
                                or int(state.grippererro) or self.pause_gripper !=
                                (float(state.gripper_position), int(state.grip_motion_done))
                                or int(state.grip_motion_done) not in (1,2)):
                            raise BackendFailure('GRIPPER_FAILED','gripper changed/unsettled during pause')
                        if self.backend.held_part is not None and int(state.grip_motion_done) != 1:
                            raise BackendFailure('GRIPPER_FAILED','held candidate lacks controller detection; recovery required')
                        result_text=self.backend._robot.resume_motion()
                        if result_text != 'fresh_feedback_resume_applied':
                            raise BackendFailure('SAFETY_STOP','resume application not verified: '+str(result_text))
                        check()  # source may expire during controller confirmation
                        result=self._reply(request,operation,Event.RESUME_CONFIRMED,
                            'same operation context released after controller acknowledgment and fresh feedback',
                            resume_available=False)
                        if self.pause_started is not None:
                            self.paused_seconds += time.monotonic()-self.pause_started
                        self.pause_started=None;self.state='RUNNING';self.blocked.clear()
                except Exception as error:
                    # Failure never opens the dispatch barrier. In particular a
                    # failed resume must not leave a controller moving silently.
                    if request['command']=='resume' and self.blocked.is_set():
                        try:self.backend._robot.pause_motion()
                        except Exception:pass
                    result=self._reply(request,operation,Event.CONTROL_FAILED,str(error),resume_available=False)
            self.results[request['control_id']] = (fingerprint,result)
            return result
