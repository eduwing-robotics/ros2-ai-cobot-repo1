"""ROS command, progress and measured-state bridge for the validated cycle."""
import json
import fcntl
from pathlib import Path
import time
import threading
from std_msgs.msg import String
from std_srvs.srv import Trigger
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from .assembly_cycle_api import AssemblyCycleController, SCHEMA
from .real_backend import BackendFailure
from .assembly_execution import AssemblyExecutionContract, SCHEMA as PRODUCTION_SCHEMA


class AssemblyCycleRosBridge:
    def __init__(self, node, root):
        self.node = node
        self.recovery_worker = None
        self.recovery_status = None
        lock_path = Path(root) / "runtime/assembly_api/server.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.instance_lock = lock_path.open("a")
        fcntl.flock(self.instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.state_pub = node.create_publisher(String, '/real/assembly/state', qos)
        self.event_pub = node.create_publisher(String, '/real/assembly/event', 50)
        self.robot_pub = node.create_publisher(String, '/real/assembly/robot_state', 5)
        self.controller = AssemblyCycleController(root, self.ready, self.publish, allow_batch_start=False,
            allow_production_start=bool(node.get_parameter('enable_production_assembly').value),
            attachment_snapshot=node._backend.event_context.snapshot, recovery_ready=self.recovery_ready, reconcile_recovery=self.reconcile_recovery)
        binding_path = Path(root) / 'assembly_integration/config/production_recipe_bindings.json'
        bindings = json.loads(binding_path.read_text()) if binding_path.exists() else []
        self.production = AssemblyExecutionContract(self.controller, bindings,
            ghost_snapshot=node._backend._ghost.snapshot)
        from .assembly_execution_control import AssemblyExecutionControl
        control = AssemblyExecutionControl(self.controller, node._backend,
            enabled=bool(node.get_parameter('enable_whole_cycle_pause').value),
            buffered_verified=bool(node.get_parameter('buffered_pause_verified').value),
            boundary_pause=bool(node.get_parameter('whole_cycle_boundary_pause').value))
        self.production.control = control
        node._backend.whole_control = control
        node._robot_port._whole_control = control
        node._backend._ghost.context_resolver = self.ghost_context
        node.create_subscription(String, '/real/assembly/command', self.command, 10)
        node.create_subscription(String, '/real/robot/event', self.robot_event, 100)
        group = getattr(node, '_assembly_status_group', None)
        options = {'callback_group': group} if group is not None else {}
        node.create_service(Trigger, '/real/assembly/status', self.status, **options)
        node.create_timer(.5, self.publish_state)
        node.create_timer(.1, self.publish_robot)

    def recovering(self):
        return getattr(self, 'recovery_worker', None) is not None and self.recovery_worker.is_alive()

    def reconcile_recovery(self, execution_id, confirmation):
        from .manual_stop_recovery import reconcile
        reconcile(self, execution_id, confirmation)

    def robot_event(self, message):
        if self.recovering():
            return
        try:
            event = json.loads(message.data)
            result = self.production.observe_robot_event(event,
                self.node._backend.event_context.snapshot())
            if result is not None:
                self.publish(result)
        except (ValueError, TypeError, KeyError):
            return

    def ghost_context(self, job_id):
        state = self.controller.state
        context = state.get('execution_context')
        if not context or state.get('operation_id') != job_id:
            return {}
        payload = self.node._vision_port._payload or {}
        return dict(execution_id=job_id, plan_sha256=payload.get('plan_sha256')
                    if payload.get('job_id') == job_id else None)

    def recovery_ready(self):
        self.ready()
        state = self.node._robot_port._fresh_state()
        if not state.gripper_feedback_valid:
            raise BackendFailure('GRIPPER_FAILED', 'fresh valid gripper feedback required for recovery')
        control = self.production.control
        if control is not None and (control.blocked.is_set()
                or (control.worker is not None and control.worker.is_alive())):
            raise BackendFailure('RECOVERY_BLOCKED', 'retained motion control remains unresolved')

    def ready(self):
        backend = self.node._backend
        if (getattr(backend, '_active', None) is not None
                or getattr(backend, '_recovery_required', False)
                or (getattr(backend, '_paused', None) is not None and backend._paused.is_set())):
            raise BackendFailure('ROBOT_BUSY', 'individual API is active, paused or requires recovery')
        if self.node._backend.held_part is not None:
            raise BackendFailure('GRIPPER_FAILED', 'individual API tracks a held part')
        self.node._robot_port.assert_ready()
        state = self.node._robot_port._fresh_state()
        # The execute worker activates an inactive gripper under its lock.
        if int(state.gripperfaultnum) or int(state.grippererro):
            raise BackendFailure('GRIPPER_FAILED', 'gripper reports a fault')

    def publish(self, payload):
        if payload.get('execution_context'):
            envelope = {key: payload[key] for key in ('request_accepted', 'recovery_applied',
                'recovery_required', 'retry_requires_new_execution_id') if key in payload}
            payload = dict(self.production.snapshot(payload['operation_id']), **envelope)
        self.event_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def publish_state(self):
        if self.recovering():
            return
        payload = self.controller.snapshot()
        payload['hardware_execution_enabled'] = self.node._robot_port._enabled
        payload['production_contract'] = self.production.snapshot()
        payload['ghost_snapshot'] = self.node._backend._ghost.snapshot()
        self.state_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def publish_robot(self):
        payload = {'schema': 'fr5.assembly_robot_state/v1', 'timestamp_unix': time.time(), 'state_fresh': False}
        try:
            port = self.node._robot_port
            with port._lock:
                state = port._state
                age = max(0., time.monotonic() - port._state_received_at)
                sequence = port._state_sequence
            if state is None or age > port._state_max_age:
                raise BackendFailure('ROBOT_FAULT', 'measured robot feedback is stale')
            port._assert_health(state)
            payload.update(state_observed_unix=time.time() - age, state_age_sec=age,
                state_sequence=sequence, execution_id=self.ghost_context(
                    self.controller.state.get('operation_id')).get('execution_id'))
            payload.update(state_fresh=True, joints_deg=[float(getattr(state, f'j{i}_cur_pos')) for i in range(1, 7)],
                tcp_mm_deg=[float(getattr(state, 'cart_' + a + '_cur_pos')) for a in 'xyzabc'],
                robot_motion_done=int(state.robot_motion_done), gripper_position=int(state.gripper_position),
                gripper_feedback_valid=bool(state.gripper_feedback_valid))
        except BackendFailure as error:
            payload['error'] = str(error)
        self.robot_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def command(self, message):
        try:
            data = json.loads(message.data)
        except (ValueError, TypeError):
            return self._command(message)
        if not isinstance(data, dict):
            return self._command(message)
        if self.recovering():
            self.publish(dict(schema=data.get('schema', SCHEMA), status='request_rejected',
                execution_id=data.get('execution_id'), operation_id=data.get('operation_id'),
                request_accepted=False, error_code='ROBOT_BUSY', message='recovery is in progress'))
            return
        if isinstance(data, dict) and data.get('action') == 'assembly.recover':
            self.recovery_status = self.controller.snapshot()
            self.recovery_status['recovery_in_progress'] = True
            self.recovery_worker = threading.Thread(target=self._command, args=(message,), daemon=True)
            self.recovery_worker.start()
            return
        self._command(message)

    def _command(self, message):
        data = {}
        try:
            data = json.loads(message.data)
            if not isinstance(data, dict):
                raise ValueError('command must be a JSON object')
            if data.get('schema') == PRODUCTION_SCHEMA:
                self.publish(self.production.command(data))
            else:
                self.publish(self.controller.command(data))
        except Exception as error:
            self.publish(dict(schema=PRODUCTION_SCHEMA if isinstance(data, dict) and data.get('schema') == PRODUCTION_SCHEMA else SCHEMA, status='request_rejected', request_accepted=False,
                execution_id=data.get('execution_id') if isinstance(data, dict) else None,
                job_id=data.get('job_id') if isinstance(data, dict) else None,
                operation_id=data.get('operation_id') if isinstance(data, dict) else None,
                error_code=getattr(error, 'code', 'INVALID_REQUEST'), message=str(error)))

    def status(self, request, response):
        if self.recovering():
            response.success = True
            response.message = json.dumps(self.recovery_status, allow_nan=False)
            return response
        payload = self.controller.snapshot()
        payload['hardware_execution_enabled'] = self.node._robot_port._enabled
        payload['production_contract'] = self.production.snapshot()
        payload['ghost_snapshot'] = self.node._backend._ghost.snapshot()
        response.success = True
        response.message = json.dumps(payload, allow_nan=False)
        return response
