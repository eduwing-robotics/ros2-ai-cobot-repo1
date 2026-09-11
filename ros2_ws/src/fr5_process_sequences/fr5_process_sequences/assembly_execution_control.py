"""Retain the live whole-cycle worker while physically pausing the robot.

Dispatch is blocked before PauseMotion. No child signals, new operation IDs,
queue replay or gripper command implement Resume. Buffered-controller support
must be commissioned explicitly; the default does not enable physical control.
"""
from contextlib import contextmanager
import copy
import json
import math
import signal
import threading
import time
from uuid import UUID

from .real_backend import BackendFailure


class AssemblyExecutionControl:
    def __init__(self, controller, backend, *, enabled=False, buffered_verified=False, boundary_pause=False):
        self.controller = controller
        self.backend = backend
        self.robot = backend._robot
        self.boundary_pause = boundary_pause
        self.enabled = enabled
        self.buffered_verified = buffered_verified
        self.blocked = threading.Event()
        self.dispatch_lock = threading.Lock()
        self.worker = None
        self.pause_anchor = None

    def supported(self):
        return self.enabled and (self.boundary_pause or not getattr(self.backend, 'continuous_transfer_enabled', False)
                                 or self.buffered_verified)

    def applies(self):
        return bool(self.controller.state.get('execution_context'))

    def clock(self):
        state = self.controller.state
        started = state.get('pause_started_monotonic') if state.get('status') in ('pause_requested','paused','resume_requested') else None
        return time.monotonic() - state.get('paused_seconds', 0.) - (
            max(0., time.monotonic() - started) if started is not None else 0.)

    def checkpoint(self):
        while self.applies() and self.blocked.is_set():
            if self.controller.state.get('status') not in ('pause_requested', 'paused', 'resume_requested'):
                raise BackendFailure('SAFETY_STOP', 'whole execution requires recovery; no further dispatch')
            if self.backend._paused.is_set() or self.backend._recovery_required:
                raise BackendFailure('SAFETY_STOP', 'legacy cancellation or failure during retained pause')
            time.sleep(.02)

    @contextmanager
    def dispatch(self):
        while True:
            self.checkpoint()
            self.dispatch_lock.acquire()
            if not (self.applies() and self.blocked.is_set()):
                break
            self.dispatch_lock.release()
        try:
            yield  # Only the service send, never the response wait.
        finally:
            self.dispatch_lock.release()

    def _anchor(self):
        state = self.robot._fresh_state()
        self.robot._assert_health(state)
        pose = [float(getattr(state, 'cart_' + axis + '_cur_pos')) for axis in 'xyzabc']
        if (not all(math.isfinite(v) for v in pose) or int(state.robot_motion_done) != 1
                or not state.gripper_feedback_valid or int(state.gripperfaultnum)
                or int(state.grippererro) or int(state.grip_motion_done) not in (1, 2)):
            raise BackendFailure('SAFETY_STOP', 'stationary pose and settled gripper feedback required')
        return dict(pose=pose, gripper=[float(state.gripper_position), int(state.grip_motion_done)],
                    held=copy.deepcopy(self.backend.held_part))

    def _validate_resume(self):
        c = self.controller
        if self.pause_anchor is None or not self.blocked.is_set():
            raise BackendFailure('SAFETY_STOP', 'no retained live pause context')
        if c.process is None or c.process.poll() is not None or self.backend._recovery_required or self.backend._paused.is_set():
            raise BackendFailure('SAFETY_STOP', 'execution failed, cancelled or lost; cannot resume')
        if c.revision() != c.state['recipe_revision']:
            raise BackendFailure('SAFETY_STOP', 'robot recipe changed during pause')
        current = self._anchor()
        if current['gripper'] != self.pause_anchor['gripper'] or current['held'] != self.pause_anchor['held']:
            raise BackendFailure('GRIPPER_FAILED', 'held identity or gripper changed during pause')
        if current['held'] is not None and current['gripper'][1] != 1:
            raise BackendFailure('GRIPPER_FAILED', 'held candidate lacks detection')
        if (max(abs(a-b) for a,b in zip(current['pose'][:3], self.pause_anchor['pose'][:3])) > .2
                or max(abs((a-b+180)%360-180) for a,b in zip(current['pose'][3:],self.pause_anchor['pose'][3:])) > .1):
            raise BackendFailure('SAFETY_STOP', 'robot pose changed during pause')
        operation = self.backend._active
        if operation is not None:
            if operation.job_id != c.state['operation_id']:
                raise BackendFailure('ROBOT_BUSY', 'another operation owns robot')
            validator = self.backend.control.checks.get(operation.operation_id)
            if validator is None:
                raise BackendFailure('SAFETY_STOP', 'active operation has no observation/configuration validator')
            validator()  # Uses wall time: a pause does not renew observations.

    def request(self, data):
        required = {'schema', 'action', 'execution_id', 'control_id', 'control_sequence'}
        resume = data.get('action') == 'assembly.resume'
        cancel = data.get('action') == 'assembly.cancel'
        if data.get('action') not in ('assembly.pause', 'assembly.resume', 'assembly.cancel'):
            raise ValueError('unsupported whole-cycle control')
        if set(data) != required | ({'pause_control_id'} if resume else set()):
            raise ValueError('control identity, sequence and matching pause generation required')
        for key in ('execution_id', 'control_id'):
            if not isinstance(data[key], str) or str(UUID(data[key])) != data[key]:
                raise ValueError('canonical control/execution UUID required')
        if type(data['control_sequence']) is not int or data['control_sequence'] < 1:
            raise ValueError('positive control sequence required')
        c = self.controller
        with c.lock:
            if not self.applies() or data['execution_id'] != c.state.get('operation_id'):
                raise BackendFailure('EXECUTION_NOT_ACTIVE', 'control targets a different execution')
            previous = c.state.get('controls', {}).get(data['control_id'])
            if previous:
                if previous['request'] != data:
                    raise BackendFailure('CONTROL_ID_CONFLICT', 'control_id content differs')
                return copy.deepcopy(previous['response'])
            if not cancel and not self.supported():
                raise BackendFailure('UNSUPPORTED_CAPABILITY', 'whole-cycle pause/buffered queue not commissioned')
            if data['control_sequence'] <= c.state.get('control_sequence', 0):
                raise BackendFailure('STALE_CONTROL', 'late control sequence')
            if c.process is None or c.process.poll() is not None:
                raise BackendFailure('EXECUTION_NOT_ACTIVE', 'live worker is missing')
            active = self.backend._active
            if active is not None and active.job_id != data['execution_id']:
                raise BackendFailure('ROBOT_BUSY', 'another operation owns robot')
            expected = 'paused' if resume else 'running'
            valid = c.state['status'] in ('starting','running','pause_requested','paused','resume_requested') if cancel else c.state['status'] == expected
            if not valid or c.state.get('finished_unix') is not None:
                raise BackendFailure('INVALID_CONTROL_STATE', 'control is not applicable to execution state')
            if resume and data['pause_control_id'] != c.state.get('pause_control_id'):
                raise BackendFailure('STALE_CONTROL', 'resume refers to a previous pause')
            if self.worker is not None and self.worker.is_alive():
                raise BackendFailure('CONTROL_BUSY', 'another control is still applying')
            response = dict(schema=data['schema'], execution_id=data['execution_id'],
                control_id=data['control_id'], control_sequence=data['control_sequence'],
                request_accepted=True, control_applied=False, stop_verified=False,
                resume_available=False, event='CONTROL_ACCEPTED')
            c.state.setdefault('controls', {})[data['control_id']] = dict(request=copy.deepcopy(data), response=response)
            c.state.update(control_sequence=data['control_sequence'],
                status='stop_requested' if cancel else ('resume_requested' if resume else 'pause_requested'), last_control=response)
            if not resume:
                if not cancel:
                    c.state.update(pause_control_id=data['control_id'], pause_started_monotonic=time.monotonic())
                # Serialize against actuator send, not against service response.
                with self.dispatch_lock:
                    self.blocked.set()
            c._save()  # Intent before touching hardware.
            self.worker = threading.Thread(target=self._cancel if cancel else self._apply, args=(copy.deepcopy(data),), daemon=True,
                                           name='whole-cycle-control')
            self.worker.start()
            return copy.deepcopy(response)

    def _cancel(self, data):
        c = self.controller
        response = dict(c.state['controls'][data['control_id']]['response'])
        # Release checkpoint waits by failing the old execution, never by resuming it.
        self.backend._paused.set()
        self.backend._recovery_required = True
        try:
            # Persisted stop_requested + blocked barrier already prevent further dispatch.
            self.robot.stop_motion()
            if c.process is not None and c.process.poll() is None:
                try:
                    c.process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
            if self.robot.observe_stopped() != 'fresh_feedback_verified_stopped':
                raise BackendFailure('SAFETY_STOP', 'cancel stop could not be verified')
            response.update(control_applied=True, stop_verified=True,
                resume_available=False, event='CANCEL_STOP_CONFIRMED',
                recovery_required=True, message='Robot stopped; worker termination and scene recovery required')
        except Exception as error:
            # Even when stop acknowledgment fails, interrupt the launcher to prevent more work.
            if c.process is not None and c.process.poll() is None:
                try:
                    c.process.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
            response.update(event='CONTROL_FAILED', control_applied=False,
                error_code=getattr(error,'code','CONTROL_FAILED'), message=str(error),
                resume_available=False, recovery_required=True)
        with c.lock:
            c.state.update(resume_available=False, stop_verified=response['stop_verified'])
            c.state['controls'][data['control_id']]['response'] = response
            c.state['last_control'] = response
            c._save()
        try:
            c.publish(response)
        except Exception:
            pass

    def _apply(self, data):
        c = self.controller
        resume = data['action'] == 'assembly.resume'
        response = dict(c.state['controls'][data['control_id']]['response'])
        try:
            if resume:
                self._validate_resume()
                if not self.boundary_pause and self.robot.resume_motion() != 'fresh_feedback_resume_applied':
                    raise BackendFailure('SAFETY_STOP', 'controller resume not verified')
            else:
                if not self.boundary_pause:
                    self.robot.pause_motion()
                observed = self.robot.observe_stopped(timeout_sec=90) if self.boundary_pause else self.robot.observe_stopped()
                if observed != 'fresh_feedback_verified_stopped':
                    raise BackendFailure('SAFETY_STOP', 'actual stop could not be verified')
                self.pause_anchor = self._anchor()
            with c.lock:
                if c.state.get('finished_unix') is not None or c.state['status'] not in ('pause_requested','resume_requested'):
                    raise BackendFailure('SAFETY_STOP', 'execution ended while control applied')
                response.update(control_applied=True, stop_verified=not resume,
                    resume_applied=resume, resume_available=not resume,
                    event='RESUME_CONFIRMED' if resume else 'PAUSE_CONFIRMED',
                    stop_evidence=None if resume else 'fresh_feedback_verified_stopped')
                c.state.update(status='running' if resume else 'paused',
                    stop_verified=not resume, resume_available=not resume)
                if not resume:
                    active = self.backend._active
                    c.state['pause_feedback']=dict(tcp_mm_deg=self.pause_anchor['pose'],
                        gripper_position=self.pause_anchor['gripper'][0], grip_motion_done=self.pause_anchor['gripper'][1],
                        operation_id=active.operation_id if active else None,
                        stage_id=getattr(self.backend,'_phase_name',None),
                        physical_holding_verified=False, observed_unix=time.time())
                if resume:
                    c.state['paused_seconds'] = c.state.get('paused_seconds', 0.) + max(
                        0., time.monotonic() - c.state.pop('pause_started_monotonic'))
                c.state['controls'][data['control_id']]['response'] = response
                c.state['last_control'] = response
                c._save()
                try:
                    ghost = getattr(self.backend, '_ghost', None)
                    if ghost is not None:
                        target = ghost.snapshot()
                        if target is not None:
                            if resume:
                                ghost.resume_target(target['operation_id'])
                            else:
                                ghost.invalidate(target['operation_id'], 'PAUSE_CONFIRMED')
                except Exception:
                    pass  # Visualization transport never gates physical resume.
                if resume:
                    self.blocked.clear()
        except Exception as error:
            if resume and not self.boundary_pause:
                try:
                    self.robot.pause_motion()
                except Exception:
                    pass
            self.backend._recovery_required = True
            with c.lock:
                response.update(event='CONTROL_FAILED', error_code=getattr(error,'code','CONTROL_FAILED'),
                                message=str(error), control_applied=False, resume_available=False)
                c.state['controls'][data['control_id']]['response'] = response
                c.state['last_control'] = response
                if c.state.get('finished_unix') is None:
                    c.state.update(status='recovery_required', resume_available=False)
                c._save()
        try:
            c.publish(response)
        except Exception:
            pass  # Durable last_control remains queryable.
