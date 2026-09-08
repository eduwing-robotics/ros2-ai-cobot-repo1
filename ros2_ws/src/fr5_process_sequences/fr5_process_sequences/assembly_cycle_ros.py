"""ROS command, progress and measured-state bridge for the validated cycle."""
import json
import fcntl
from pathlib import Path
import time
from std_msgs.msg import String
from std_srvs.srv import Trigger
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from .assembly_cycle_api import AssemblyCycleController, SCHEMA
from .real_backend import BackendFailure


class AssemblyCycleRosBridge:
    def __init__(self, node, root):
        self.node = node
        lock_path = Path(root) / "runtime/assembly_api/server.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.instance_lock = lock_path.open("a")
        fcntl.flock(self.instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.state_pub = node.create_publisher(String, '/real/assembly/state', qos)
        self.event_pub = node.create_publisher(String, '/real/assembly/event', 50)
        self.robot_pub = node.create_publisher(String, '/real/assembly/robot_state', 5)
        self.controller = AssemblyCycleController(root, self.ready, self.publish, allow_batch_start=False)
        node.create_subscription(String, '/real/assembly/command', self.command, 10)
        node.create_service(Trigger, '/real/assembly/status', self.status)
        node.create_timer(.5, self.publish_state)
        node.create_timer(.1, self.publish_robot)

    def ready(self):
        if self.node._backend.held_part is not None:
            raise BackendFailure('GRIPPER_FAILED', 'individual API tracks a held part')
        self.node._robot_port.assert_ready()

    def publish(self, payload):
        self.event_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def publish_state(self):
        payload = self.controller.snapshot()
        payload['hardware_execution_enabled'] = self.node._robot_port._enabled
        self.state_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def publish_robot(self):
        payload = {'schema': 'fr5.assembly_robot_state/v1', 'timestamp_unix': time.time(), 'state_fresh': False}
        try:
            port = self.node._robot_port
            state = port._fresh_state()
            payload.update(state_fresh=True, joints_deg=list(port.current_joints_deg()),
                tcp_mm_deg=[float(getattr(state, 'cart_' + a + '_cur_pos')) for a in 'xyzabc'],
                robot_motion_done=int(state.robot_motion_done), gripper_position=int(state.gripper_position),
                gripper_feedback_valid=bool(state.gripper_feedback_valid))
        except BackendFailure as error:
            payload['error'] = str(error)
        self.robot_pub.publish(String(data=json.dumps(payload, allow_nan=False)))

    def command(self, message):
        data = {}
        try:
            data = json.loads(message.data)
            if not isinstance(data, dict):
                raise ValueError('command must be a JSON object')
            self.publish(self.controller.command(data))
        except Exception as error:
            self.publish(dict(schema=SCHEMA, status='request_rejected',
                job_id=data.get('job_id') if isinstance(data, dict) else None,
                operation_id=data.get('operation_id') if isinstance(data, dict) else None,
                error_code=getattr(error, 'code', 'INVALID_REQUEST'), message=str(error)))

    def status(self, request, response):
        payload = self.controller.snapshot()
        payload['hardware_execution_enabled'] = self.node._robot_port._enabled
        response.success = True
        response.message = json.dumps(payload, allow_nan=False)
        return response
