"""Ordered event metadata; presentation evidence never grants motion permission."""
from copy import deepcopy
import json
import threading
from uuid import uuid4


class RobotEventContext:
    def __init__(self):
        self.server_id = str(uuid4())
        self.sequence = 0
        self.lock = threading.RLock()
        self.bindings = {}
        self.attachments = {}
        self.last_event = None
        self.terminals = {}
        self.observed_sequences = set()

    def bind(self, operation, payload, row):
        context = {k: row.get(k) for k in
                   ('source_id', 'tray_registration_id', 'source_observation_id')}
        context.update(source_cycle_id=payload.get('source_cycle_id'),
                       plan_sha256=payload.get('plan_sha256'))
        for key in ('production_job_id', 'unit_id', 'display_board_id'):
            if key in payload.get('execution_context', {}):
                context[key] = payload['execution_context'][key]
        peers = [p for p in payload.get('parts', []) if p.get('source_id') == context.get('source_id')
                 and p.get('tray_registration_id') == context.get('tray_registration_id')]
        if len(peers) > 1:
            context.update(source_id=None, binding_error='ambiguous source identity')
        with self.lock:
            self.bindings[operation.operation_id] = context

    def message(self, operation, phase, event, message='', feedback=None):
        with self.lock:
            context = deepcopy(self.bindings.get(operation.operation_id, {}))
            if message:
                try:
                    value = json.loads(message)
                except (ValueError, TypeError):
                    value = None
                if isinstance(value, dict):
                    context.update(value)  # preserve existing completion message fields
                else:
                    context['reason'] = message
            context.update(schema='fr5.robot_event_context/v1',
                part_id=operation.part_id, source_index=operation.source_index,
                slot_code=operation.slot_code, order=operation.order)
            context['attachment_binding_valid'] = all(isinstance(context.get(k), str)
                and bool(context[k]) for k in ('source_id','tray_registration_id','source_observation_id'))
            if feedback is not None:
                context['feedback'] = deepcopy(feedback)
            self.sequence += 1
            context.update(server_instance_id=self.server_id, event_sequence=self.sequence)
            return json.dumps(context, ensure_ascii=False, allow_nan=False)

    def observe(self, event):
        try:
            context = json.loads(event.message)
        except (ValueError, TypeError):
            return
        if not isinstance(context, dict): return
        with self.lock:
            # Journal replay retains its original epoch/sequence and must never
            # overwrite a newer live snapshot or reattach a placed object.
            if context.get('server_instance_id') != self.server_id: return
            sequence = context['event_sequence']
            if sequence in self.observed_sequences: return
            self.observed_sequences.add(sequence)
            terminal = event.event.value in ('OPERATION_COMPLETED','OPERATION_FAILED')
            if terminal:
                if event.operation_id in self.terminals: return
                self.terminals[event.operation_id] = event.to_dict()
            older = self.last_event and context['event_sequence'] <= self.last_event['event_sequence']
            if not older:
                self.last_event = dict(event.to_dict(), event_sequence=context['event_sequence'])
            if not context.get('attachment_binding_valid'): return
            key = (event.job_id, context['tray_registration_id'], context['source_id'])
            old = self.attachments.get(key)
            state = old.get('state') if old else None
            kind = event.event.value
            if event.action == 'robot.pick' and kind == 'PHASE_STARTED' and state is None:
                state = 'reserved'
            if kind == 'PHASE_COMPLETED' and event.phase in ('GRASP', 'RELEASE'):
                feedback = context.get('feedback', {})
                if feedback.get('continuous_feedback_verified') is not True: return
                if event.action == 'robot.pick' and event.phase == 'GRASP' and state == 'reserved':
                    state = 'attached'
                elif event.action == 'robot.place' and event.phase == 'RELEASE' and state == 'attached':
                    state = 'placed'
                else: return
            if state is None: return
            self.attachments[key] = dict(context, job_id=event.job_id,
                operation_id=event.operation_id, action=event.action, state=state,
                uncertain=(kind in ('OPERATION_FAILED','CONTROL_FAILED') or bool(old and old.get('uncertain'))),
                physical_holding_verified=False, precision_placement_verified=False)

    def snapshot(self):
        with self.lock:
            return deepcopy(dict(server_instance_id=self.server_id,
                event_sequence=self.sequence, last_event=self.last_event,
                attachments=list(self.attachments.values()), terminal_operations=list(self.terminals.values())))
