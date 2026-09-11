"""Versioned one-PCB contract over the existing cycle owner.

No production database access, client motion payloads, queue or automatic replay.
Retained whole-cycle pause/resume is explicitly uncommissioned.
"""
import copy
import hashlib
import json
import time
from uuid import UUID

from .assembly_cycle_api import SCHEMA as LOCAL_SCHEMA, SLOTS, read
from .real_backend import BackendFailure

SCHEMA = 'fr5.assembly_execution/v2'
START_FIELDS = {'schema', 'action', 'execution_id', 'production_job_id', 'unit_id',
                'product_id', 'production_recipe_version', 'robot_recipe_revision',
                'scene_confirmation'}


def canonical_uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError('execution_id must be a canonical UUID')
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


class AssemblyExecutionContract:
    def __init__(self, controller, bindings=(), clock=time.time, ghost_snapshot=None):
        self.control = None
        self.controller = controller
        self.ghost_snapshot = ghost_snapshot
        self.bindings = copy.deepcopy(list(bindings))
        identities = set()
        for binding in self.bindings:
            if not isinstance(binding, dict) or set(binding) != {
                    'product_id', 'production_recipe_version', 'robot_recipe_revision', 'expected_slots'}:
                raise ValueError('invalid production recipe binding fields')
            identity = tuple(binding[k] for k in ('product_id', 'production_recipe_version', 'robot_recipe_revision'))
            if (any(not isinstance(value, str) or not value.strip() for value in identity)
                    or identity in identities or binding['expected_slots'] != SLOTS['full']):
                raise ValueError('ambiguous or incorrect production recipe binding')
            identities.add(identity)
        self.clock = clock

    def capabilities(self):
        return dict(start=bool(self.bindings) and self.controller.allow_production_start,
                    pause=bool(self.control and self.control.supported()),
                    resume=bool(self.control and self.control.supported()),
                    pause_behavior="after_dispatched_motion" if self.control and self.control.boundary_pause else "controller_retained",
                    status=True, event=True,
                    cancel=self.control is not None, recover=True, manual_stop_recovery=self.controller.reconcile_recovery is not None, final_acceptance_complete=False)

    def snapshot(self, execution_id=None):
        c = self.controller
        # An unqualified query is equipment/current state, never the latest
        # historical diagnostic result reinterpreted as production completion.
        local = c.snapshot(execution_id)
        context = local.get('execution_context')
        result = dict(schema=SCHEMA, server_instance_id=c.server_instance_id,
                      response_generated_unix=self.clock(), capabilities=self.capabilities(),
                      execution_id=execution_id, status='not_found' if execution_id else 'idle',
                      current_recipe_revision=c.revision(), resume_available=False,
                      physical_placement_verified=False, inspection_pass=None,
                      retention_policy='no_automatic_deletion; restart_never_replays',
                      ghost_snapshot_supported=self.ghost_snapshot is not None)
        if self.ghost_snapshot is not None:
            target = self.ghost_snapshot()
            result['ghost_snapshot'] = (target if target and
                (execution_id is None or target.get('execution_id') == execution_id) else None)
        if not context:
            result['equipment_busy_or_unresolved'] = local.get('status') in (
                'starting', 'running', 'stop_requested', 'recovery_required')
            result['local_execution_kind'] = local.get('execution_kind', 'unknown')
            return result
        request = context['request']
        result.update({key: request[key] for key in (
            'execution_id', 'production_job_id', 'unit_id', 'product_id',
            'production_recipe_version', 'robot_recipe_revision')})
        result.update(status=local['status'], execution_kind='production',
                      request_fingerprint=context['request_fingerprint'],
                      expected_slots=list(context['expected_slots']),
                      completed_slots=local.get('completed_slots', []),
                      state_updated_unix=local.get('updated_unix'),
                      event_sequence=local.get('event_sequence', 0),
                      event_unix=local.get('updated_unix'),
                      origin_server_instance_id=local.get('origin_server_instance_id'),
                      current_stage=local.get('step'), held_candidate=local.get('held_candidate'),
                      recovery_required=local['status'] == 'recovery_required',
                      stop_verified=False, plan_hashes={},
                      verification_level='motion_only_not_inspection_pass')
        result['resume_available'] = bool(local.get('resume_available')) and local['status']=='paused'
        if self.control is not None and local['status']=='paused':
            try:
                self.control._validate_resume()
            except Exception as error:
                result['resume_available']=False
                result['resume_unavailable_reason']=str(error)
        result['pause_feedback'] = copy.deepcopy(local.get('pause_feedback'))
        result['last_control'] = copy.deepcopy(local.get('last_control'))
        result['pause_control_id'] = local.get('pause_control_id')
        result['plan_hashes'] = copy.deepcopy(local.get('plan_hashes', {}))
        result['completion_evidence'] = copy.deepcopy(local.get('completion_evidence'))
        result['stop_verified'] = bool(local.get('stop_verified') or local.get('completion_evidence', {}).get('stop_verified'))
        result['auto_recovery'] = copy.deepcopy(local.get('auto_recovery'))
        result['retry_requires_new_execution_id'] = local['status'] in ('failed_before_motion', 'failed_recovered', 'motion_complete_awaiting_physical_verification')
        result['recovery'] = copy.deepcopy(local.get('recovery'))
        result['failure'] = copy.deepcopy(local.get('failure'))
        failure = result['failure'] or {}
        result['error_code'] = failure.get('code')
        result['error_message'] = failure.get('message')
        result['failed_stage'] = failure.get('stage')
        result['evidence_error'] = local.get('evidence_error')
        result['event'] = {'starting': 'EXECUTION_ACCEPTED', 'running': 'EXECUTION_PROGRESS',
            'pause_requested': 'PAUSE_REQUESTED', 'paused': 'PAUSE_CONFIRMED',
            'resume_requested': 'RESUME_REQUESTED', 'stop_requested': 'STOP_REQUESTED', 'recovery_required': 'EXECUTION_FAILED', 'failed_before_motion': 'EXECUTION_FAILED', 'failed_recovered': 'EXECUTION_FAILED',
            'motion_complete_awaiting_physical_verification': 'EXECUTION_COMPLETED'}.get(local['status'], 'EXECUTION_STATUS')
        if local['status'] == 'running' and not local.get('launcher_status'):
            result['event'] = 'EXECUTION_STARTED'
        result['last_robot_event'] = copy.deepcopy(local.get('last_robot_event'))
        result['attachments'] = copy.deepcopy(local.get('attachments', []))
        result['plan_complete'] = set(result['plan_hashes']) == {'non-smd', 'smd'}
        return result

    def observe_robot_event(self, event, attachment_snapshot):
        """Correlate the original event; never infer identity from array order."""
        try:
            metadata = json.loads(event.get('message', '{}'))
            if metadata.get('server_instance_id') != attachment_snapshot['server_instance_id']:
                return None
            sequence = metadata['event_sequence']
            if type(sequence) is not int or sequence < 1:
                return None
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
        c = self.controller
        with c.lock:
            state = c.state
            context = state.get('execution_context')
            if (not context or event.get('job_id') != state.get('operation_id')
                    or state.get('finished_unix') is not None
                    or event.get('event') in ('REQUEST_REJECTED', 'CONTROL_REJECTED')):
                return None
            old = state.get('last_robot_event', {})
            previous = old.get('metadata', {})
            if (previous.get('server_instance_id') == metadata['server_instance_id']
                    and sequence <= previous.get('event_sequence', 0)):
                return None
            if metadata.get('slot_code') and metadata['slot_code'] not in context['expected_slots']:
                return None
            state['last_robot_event'] = dict(original=copy.deepcopy(event), metadata=metadata)
            state['attachments'] = [copy.deepcopy(item) for item in attachment_snapshot.get('attachments', [])
                                    if item.get('job_id') == state['operation_id']]
            c._save()
            result = self.snapshot(state['operation_id'])
            result.update(event='ROBOT_EVENT', robot_event_kind=event.get('event'),
                          operation_id=event.get('operation_id'),
                          stage_id=event.get('phase'), robot_event=copy.deepcopy(event))
            return result

    def command(self, data):
        if not isinstance(data, dict) or data.get('schema') != SCHEMA:
            raise ValueError('unsupported production schema')
        action = data.get('action')
        if action == 'assembly.status':
            if set(data) not in ({'schema', 'action'}, {'schema', 'action', 'execution_id'}):
                raise ValueError('status accepts only optional execution_id')
            if 'execution_id' in data:
                canonical_uuid(data['execution_id'])
            return self.snapshot(data.get('execution_id'))
        if action == 'assembly.recover':
            if set(data) != {'schema', 'action', 'execution_id', 'scene_confirmation'}:
                raise ValueError('recover requires execution_id and scene_confirmation only')
            execution_id = canonical_uuid(data['execution_id'])
            with self.controller.lock:
                self.controller.recover(execution_id, data['scene_confirmation'])
                return dict(self.snapshot(execution_id), request_accepted=True,
                    recovery_applied=True, recovery_required=False, retry_requires_new_execution_id=True)
        if action in ('assembly.pause', 'assembly.resume', 'assembly.cancel'):
            if self.control is not None:
                return self.control.request(data)
            raise BackendFailure('UNSUPPORTED_CAPABILITY',
                'Whole-cycle retained pause/resume is not commissioned; cancellation is not pause.')
        if action != 'assembly.start' or set(data) != START_FIELDS:
            raise ValueError('unsupported action or production fields')
        execution_id = canonical_uuid(data['execution_id'])
        if type(data['unit_id']) is not int or data['unit_id'] <= 0:
            raise ValueError('unit_id must be a positive integer')
        for key in ('production_job_id', 'product_id', 'production_recipe_version', 'robot_recipe_revision'):
            if not isinstance(data[key], str) or not data[key].strip() or len(data[key]) > 256:
                raise ValueError('invalid ' + key)
        # Check durable request identity BEFORE temporal readiness or revision:
        # even an expired confirmation must return the original execution.
        with self.controller.lock:
            path = self.controller.directory / (execution_id + '.json')
            if path.exists():
                context = read(path).get('execution_context')
                if not context or context['request'] != data:
                    raise BackendFailure('EXECUTION_ID_CONFLICT', 'execution_id already has different content')
                return dict(self.snapshot(execution_id), request_accepted=True, replayed=True)
            if not self.capabilities()['start']:
                raise BackendFailure('UNSUPPORTED_CAPABILITY', 'Production start is not commissioned or recipe binding is absent')
            matches = [b for b in self.bindings if all(b.get(key) == data[key] for key in
                ('product_id', 'production_recipe_version', 'robot_recipe_revision'))]
            if len(matches) != 1 or matches[0].get('expected_slots') != SLOTS['full']:
                raise BackendFailure('RECIPE_MISMATCH', 'No unique binding to the robot full-slot recipe')
            confirmation = data['scene_confirmation']
            if not isinstance(confirmation, dict) or set(confirmation) != {
                    'operator_id', 'execution_id', 'confirmed_unix', 'scope'}:
                raise ValueError('explicit operator scene confirmation required')
            if (not isinstance(confirmation['operator_id'], str) or not confirmation['operator_id'].strip()
                    or confirmation['execution_id'] != execution_id
                    or confirmation['scope'] != 'empty_gripper_empty_pcb_full_tray_fixed_fixture'
                    or type(confirmation['confirmed_unix']) not in (int, float)
                    or not 0 <= self.clock() - confirmation['confirmed_unix'] <= 120):
                raise ValueError('scene confirmation is invalid, stale or belongs to another execution')
            context = dict(request=copy.deepcopy(data), request_fingerprint=fingerprint(data),
                           expected_slots=list(SLOTS['full']), binding=copy.deepcopy(matches[0]))
            self.controller.command(dict(schema=LOCAL_SCHEMA, action='assembly.start',
                job_id=execution_id, operation_id=execution_id,
                recipe_revision=data['robot_recipe_revision'], profile='full',
                confirm_scene_ready=True), execution_context=context)
            return dict(self.snapshot(execution_id), request_accepted=True, replayed=False)
