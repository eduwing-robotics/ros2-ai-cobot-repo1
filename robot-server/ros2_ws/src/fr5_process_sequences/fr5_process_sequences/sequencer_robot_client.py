"""Sequencer-side API. Transport callbacks also work with a Mock backend.

No implicit retries: a timeout means outcome unknown, never permission to send
another operation. ROS callbacks must run on a separate executor while waiting.
"""
from concurrent.futures import Future
from copy import deepcopy
import json
import math
import threading
import time
from uuid import UUID, uuid4

from .real_contract import parse_operation


class OperationFailed(RuntimeError):
    def __init__(self, event):
        self.event = event
        super().__init__(f"{event.get('error_code')}: {event.get('message')}")


class SequencerRobotClient:
    def __init__(self, *, job_id, send_command, send_pause, recipe=None, send_control=None):
        self.job_id = str(UUID(job_id))
        self._send = send_command
        self._pause = send_pause
        self._send_control = send_control
        self._controls = {}
        self._control_sequence = 0
        self._control_target = None
        self._dispatch_blocked = False
        self._pause_confirmed = False
        self.recipe = deepcopy(recipe) if recipe is not None else None
        self._lock = threading.RLock()
        self._pending = {}
        self._inflight = None
        self._steps = {}
        if recipe is not None:
            counts = {}
            orders = set()
            for step in recipe['steps']:
                part, slot, order = step['part_id'], step['slot_code'], step['order']
                if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
                    raise ValueError('step order must be a positive integer')
                if order in orders or (part, slot) in self._steps:
                    raise ValueError('duplicate recipe order or part/slot')
                orders.add(order)
                counts[part] = counts.get(part, 0) + 1
                self._steps[part, slot] = (order, counts[part])
            if [s['order'] for s in recipe['steps']] != list(range(1, len(orders)+1)):
                raise ValueError('steps must be in contiguous order starting at 1')
            if recipe.get('frame') != 'base_link':
                raise ValueError('recipe frame must be base_link')

    @classmethod
    def from_yaml(cls, path, **kwargs):
        import yaml
        with open(path, encoding='utf-8') as source:
            recipe = yaml.safe_load(source)
        return cls(recipe=recipe, **kwargs)

    def _submit(self, action, fields, operation_id=None):
        operation_id = str(UUID(operation_id)) if operation_id else str(uuid4())
        command = parse_operation(dict(job_id=self.job_id, operation_id=operation_id,
                                       action=action, **fields)).to_dict()
        encoded = json.dumps(command, sort_keys=True)
        with self._lock:
            if operation_id in self._pending:
                previous, future = self._pending[operation_id]
                if encoded != previous:
                    raise ValueError('operation_id already used with different content')
                return future
            if self._dispatch_blocked:
                raise RuntimeError('pause/control outcome blocks new operation dispatch')
            if self._inflight is not None:
                raise RuntimeError('previous operation is not terminal; do not advance Sequencer')
            future = Future()
            # Cancellation of a Future must not be mistaken for cancelling hardware.
            future.set_running_or_notify_cancel()
            self._pending[operation_id] = (encoded, future)
            self._inflight = operation_id
        try:
            self._send(command)
        except Exception as error:
            # Sending may have succeeded before the transport raised. Keep the
            # operation inflight until a correlated terminal event arrives.
            raise RuntimeError(f'command delivery unknown for {operation_id}; reconcile events') from error
        return future

    def on_event(self, event):
        if isinstance(event, str):
            event = json.loads(event)
        if event.get('job_id') != self.job_id:
            return False
        with self._lock:
            if event.get('event') in ('PAUSE_CONFIRMED','RESUME_CONFIRMED','CONTROL_FAILED','CONTROL_REJECTED'):
                return self._on_control_event(event)
            entry = self._pending.get(event.get('operation_id'))
            if entry is None:
                return False
            encoded, future = entry
            if event.get('action') != json.loads(encoded)['action']:
                return False
            if future.done():
                return False
            kind = event.get('event')
            if kind not in ('OPERATION_COMPLETED', 'OPERATION_FAILED'):
                return False
            self._inflight = None
            if kind == 'OPERATION_COMPLETED':
                future.set_result(event)
            else:
                future.set_exception(OperationFailed(event))
            return True

    def moveJoint(self, point_name, joints_deg=None, *, operation_id=None):
        if joints_deg is None:
            joints_deg = self.recipe['joint_points'][point_name]
        return self._submit('robot.move_joint', dict(point_name=point_name,
                            joint_point=list(joints_deg)), operation_id)

    def _part_fields(self, part_type, slot_code, picking, values):
        values = dict(values)
        if self.recipe is not None:
            order, index = self._steps[part_type, slot_code]
            defaults = dict(self.recipe['motion'])
            defaults.pop('assembled_pcb_drop_approach_dz_mm', None)
            defaults.update(self.recipe['gripper']['parts'][part_type])
            defaults.update(order=order, source_index=index)
            defaults.update(values)
            values = defaults
        if not picking:
            values.pop('grasp_opening_percent', None)
            values.pop('pregrasp_opening_percent', None)
        else:
            # Old recipes omit pre-open; preserve that legacy behavior explicitly.
            values.setdefault('pregrasp_opening_percent', values.get('release_opening_percent'))
        values.update(part_id=part_type, slot_code=slot_code)
        return values

    def pickItem(self, part_type, slot_code, *, operation_id=None, **values):
        return self._submit('robot.pick', self._part_fields(part_type, slot_code, True, values), operation_id)

    def placeItem(self, part_type, slot_code, *, operation_id=None, **values):
        return self._submit('robot.place', self._part_fields(part_type, slot_code, False, values), operation_id)

    def transferItem(self, object_id='assembled_pcb', *, operation_id=None, **values):
        defaults = {}
        if self.recipe is not None:
            defaults.update(self.recipe['motion'])
            defaults.update(self.recipe['gripper']['assembled_pcb'])
        defaults.update(values)
        defaults.setdefault('pregrasp_opening_percent', defaults.get('release_opening_percent'))
        return self._submit('robot.transfer', dict(object_id=object_id, **defaults), operation_id)

    def pause(self):
        """Legacy stop/cancel. Does not retain a resumable operation."""
        self._pause(True)

    def control(self, command, *, operation_id=None, control_id=None, timeout_sec=5.):
        if (command not in ('pause','resume') or isinstance(timeout_sec,bool)
                or not isinstance(timeout_sec,(int,float)) or not math.isfinite(timeout_sec) or timeout_sec <= 0):
            raise ValueError('invalid control command/timeout')
        if self._send_control is None: raise RuntimeError('retained control transport unavailable')
        with self._lock:
            target = operation_id or self._inflight or self._control_target
            if target not in self._pending: raise ValueError('control needs a known operation_id')
            cid = str(UUID(control_id)) if control_id else str(uuid4())
            if cid in self._controls:
                old = self._controls[cid]
                if old['request']['command'] != command or old['request']['operation_id'] != target:
                    raise ValueError('control_id content conflict')
                return old['future']
            if command == 'resume' and not self._pause_confirmed:
                raise RuntimeError('resume requires confirmed retained pause')
            self._control_sequence += 1
            payload=dict(command=command,control_id=cid,control_sequence=self._control_sequence,
                job_id=self.job_id,operation_id=target)
            future=Future();future.set_running_or_notify_cancel()
            self._controls[cid]=dict(request=payload,future=future,deadline=time.monotonic()+timeout_sec)
            self._control_target=target
            # Registration and local dispatch block precede publication.
            self._dispatch_blocked=True
        try:self._send_control(payload)
        except Exception as error:
            raise RuntimeError('control delivery unknown; dispatch remains blocked') from error
        return future

    def check_control_timeouts(self):
        with self._lock:
            for item in self._controls.values():
                if not item['future'].done() and time.monotonic() >= item['deadline']:
                    item['future'].set_exception(TimeoutError('control confirmation timeout; dispatch remains blocked'))

    def _on_control_event(self,event):
        try:context=json.loads(event.get('message',''))
        except (ValueError,TypeError):return False
        if not isinstance(context,dict):return False
        item=self._controls.get(context.get('control_id'))
        if item is None or item['future'].done():return False
        request=item['request']
        action=json.loads(self._pending[request['operation_id']][0])['action']
        if (event.get('operation_id')!=request['operation_id'] or
                event.get('action') not in (action,'') or
                context.get('control_sequence')!=request['control_sequence'] or
                context.get('control_action')!=request['command']):return False
        kind=event['event']
        if kind=='PAUSE_CONFIRMED' and request['command']=='pause' and context.get('stop_verified') is True:
            self._pause_confirmed=True
            item['future'].set_result(event)
        elif kind=='RESUME_CONFIRMED' and request['command']=='resume' and context.get('resume_applied') is True:
            self._dispatch_blocked=False
            self._pause_confirmed=False
            item['future'].set_result(event)
        elif kind in ('CONTROL_FAILED','CONTROL_REJECTED'):
            item['future'].set_exception(OperationFailed(event))
        else:return False
        return True

    def iterWorkflow(self):
        """Yield the supplied YAML flow without running any command."""
        flow = self.recipe['workflow']
        for action in flow['before_all']:
            yield deepcopy(action), None
        for step in self.recipe['steps']:
            for action in flow['per_step']:
                yield deepcopy(action), deepcopy(step)
        for action in flow['after_all']:
            yield deepcopy(action), None

    def runRecipe(self, external_handlers, *, timeout_sec=120):
        """Run on a Sequencer worker thread; failures/timeouts stop iteration.

        external_handlers contains conveyor.move_to, vision.resolve_targets,
        inspection.run callbacks. A callback must complete synchronously or
        return a Future. A ROS executor must be spinning independently.
        """
        if timeout_sec <= 0:
            raise ValueError('timeout_sec must be positive')
        workflow = list(self.iterWorkflow())
        supported = {'robot.move_joint', 'robot.pick', 'robot.place', 'robot.transfer'}
        for action, _ in workflow:
            if len(action) != 1:
                raise ValueError('each workflow entry must contain exactly one action')
            name = next(iter(action))
            if name not in supported and name not in external_handlers:
                raise ValueError(f'missing handler: {name}')
        results = []
        for action, step in workflow:
            name, argument = next(iter(action.items()))
            if name == 'robot.move_joint':
                result = self.moveJoint(argument)
            elif name == 'robot.pick':
                result = self.pickItem(step['part_id'], step['slot_code'])
            elif name == 'robot.place':
                result = self.placeItem(step['part_id'], step['slot_code'])
            elif name == 'robot.transfer':
                result = self.transferItem(argument)
            else:
                result = external_handlers[name](argument)
            if isinstance(result, Future):
                result = result.result(timeout=timeout_sec)
            if result is False:
                raise RuntimeError(f'external action failed: {name}')
            results.append(result)
        return results


class RosSequencerRobotClient(SequencerRobotClient):
    """ROS transport for a caller-owned node. Topic overrides support Mock."""
    def __init__(self, node, *, job_id, recipe=None,
                 command_topic='/real/robot/command', event_topic='/real/robot/event',
                 pause_topic='/real/robot/pause', control_topic='/real/robot/control'):
        from std_msgs.msg import String, Bool
        self._real_transport = command_topic == '/real/robot/command'
        self._command_publisher = node.create_publisher(String, command_topic, 10)
        self._pause_publisher = node.create_publisher(Bool, pause_topic, 10)
        self._control_publisher = node.create_publisher(String, control_topic, 10)
        def send(command):
            self._command_publisher.publish(String(data=json.dumps(command)))
        def pause(value):
            self._pause_publisher.publish(Bool(data=value))
        super().__init__(job_id=job_id, recipe=recipe, send_command=send, send_pause=pause,
            send_control=lambda command:self._control_publisher.publish(String(data=json.dumps(command))))
        self._control_timer=node.create_timer(.1,self.check_control_timeouts)
        self._subscription = node.create_subscription(String, event_topic,
                                                     lambda msg: self.on_event(msg.data), 100)

    def runRecipe(self, external_handlers, *, timeout_sec=600):
        if self._real_transport and self.recipe.get('real_execution_ready') is not True:
            raise ValueError('Real recipe is not commissioned; ready points and PCB transfer must be resolved')
        return super().runRecipe(external_handlers, timeout_sec=timeout_sec)
