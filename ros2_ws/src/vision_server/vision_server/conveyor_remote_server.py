"""Fail-safe, service-driven conveyor controller for Main Server integration."""

from dataclasses import dataclass
import json
import math
import time
import uuid

from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger

from .conveyor_controller import (
    bounded_heartbeat_timeout,
    bounded_speed,
    heartbeat_is_fresh,
    signed_speed,
    station_trigger_topic,
)


IDLE = 'IDLE'
MOVING_TO_ASSEMBLY = 'MOVING_TO_ASSEMBLY'
ASSEMBLY_STOP = 'ASSEMBLY_STOP'
MOVING_TO_INSPECTION = 'MOVING_TO_INSPECTION'
INSPECTION_STOP = 'INSPECTION_STOP'
MANUAL_STOP = 'MANUAL_STOP'
FAULT = 'FAULT'


@dataclass(frozen=True)
class Signal:
    value: bool = False
    received_at: float = 0.0


@dataclass(frozen=True)
class StartContext:
    armed: bool
    state: str
    ready: Signal
    assembly_trigger: Signal
    inspection_trigger: Signal
    fr5_clear: Signal
    heartbeat_timeout: float
    fr5_timeout: float
    require_fr5_clear: bool
    duplicate_cmd_publisher: bool = False


def signal_is_fresh(signal: Signal, now: float, timeout: float) -> bool:
    return heartbeat_is_fresh(signal.received_at, now, timeout)


def validate_start_request(
    station: str, context: StartContext, now: float
) -> tuple[bool, str]:
    if station not in ('assembly', 'inspection'):
        return False, f'unknown station: {station}'
    if not context.armed:
        return False, 'remote motion server is monitor-only/disarmed'
    if context.duplicate_cmd_publisher:
        return False, 'another /cmd_vel publisher is active'
    if context.state.startswith('MOVING_TO_'):
        return False, f'conveyor is already moving: {context.state}'
    if context.state == FAULT:
        return False, 'controller is in FAULT; call /conveyor/reset first'
    if context.state == MANUAL_STOP:
        return False, 'controller is manually stopped; call /conveyor/reset first'
    if not signal_is_fresh(context.ready, now, context.heartbeat_timeout):
        return False, 'S22 ready heartbeat is missing or stale'
    if not context.ready.value:
        return False, 'S22 stop-line safety is not ready'
    if context.require_fr5_clear:
        if not signal_is_fresh(context.fr5_clear, now, context.fr5_timeout):
            return False, 'FR5-clear heartbeat is missing or stale'
        if not context.fr5_clear.value:
            return False, 'FR5 is not clear of the conveyor work area'

    selected = (
        context.assembly_trigger
        if station == 'assembly'
        else context.inspection_trigger
    )
    if not signal_is_fresh(selected, now, context.heartbeat_timeout):
        return False, f'{station} trigger heartbeat is missing or stale'
    if selected.value:
        return False, f'{station} stop trigger is already active'

    if station == 'assembly':
        if context.state not in (IDLE, INSPECTION_STOP):
            return False, f'assembly move is not allowed from {context.state}'
    else:
        assembly_reached = (
            context.state == ASSEMBLY_STOP
            or (
                context.state == IDLE
                and signal_is_fresh(
                    context.assembly_trigger,
                    now,
                    context.heartbeat_timeout,
                )
                and context.assembly_trigger.value
            )
        )
        if not assembly_reached:
            return False, 'inspection move requires an assembly-stop state'

    return True, 'accepted'


def moving_fault_reason(
    context: StartContext, target_station: str, now: float
) -> str | None:
    if not context.armed:
        return 'remote motion server is monitor-only/disarmed'
    if target_station not in ('assembly', 'inspection'):
        return f'unknown target station: {target_station}'
    if context.duplicate_cmd_publisher:
        return 'another /cmd_vel publisher became active'
    if not signal_is_fresh(context.ready, now, context.heartbeat_timeout):
        return 'S22 ready heartbeat missing'
    if not context.ready.value:
        return 'S22 stop-line safety became not ready'
    selected = (
        context.assembly_trigger
        if target_station == 'assembly'
        else context.inspection_trigger
    )
    if not signal_is_fresh(selected, now, context.heartbeat_timeout):
        return f'{target_station} trigger heartbeat missing'
    if context.require_fr5_clear:
        if not signal_is_fresh(context.fr5_clear, now, context.fr5_timeout):
            return 'FR5-clear heartbeat missing'
        if not context.fr5_clear.value:
            return 'FR5 entered or may have entered the conveyor work area'
    return None


class ConveyorRemoteServer(Node):
    """Own `/cmd_vel` and expose guarded station movement services."""

    def __init__(self) -> None:
        super().__init__('conveyor_remote_server')
        self.declare_parameter('allow_motion', False)
        self.declare_parameter('cmd_topic', '/cmd_vel')
        self.declare_parameter('speed', 0.10)
        self.declare_parameter('direction', 'negative_x')
        self.declare_parameter('heartbeat_timeout', 0.15)
        self.declare_parameter('fr5_clear_topic', '/cell/fr5_clear_for_conveyor')
        self.declare_parameter('fr5_timeout', 0.25)
        self.declare_parameter('require_fr5_clear', True)
        self.declare_parameter('motion_timeout', 30.0)

        self.armed = bool(self.get_parameter('allow_motion').value)
        self.cmd_topic = str(self.get_parameter('cmd_topic').value)
        self.speed = bounded_speed(self.get_parameter('speed').value)
        self.direction = str(self.get_parameter('direction').value)
        self.command_speed = signed_speed(self.speed, self.direction)
        self.heartbeat_timeout = bounded_heartbeat_timeout(
            self.get_parameter('heartbeat_timeout').value
        )
        self.fr5_clear_topic = str(
            self.get_parameter('fr5_clear_topic').value
        )
        self.fr5_timeout = float(self.get_parameter('fr5_timeout').value)
        if not math.isfinite(self.fr5_timeout) or not 0.10 <= self.fr5_timeout <= 1.0:
            raise ValueError('fr5_timeout must be between 0.10 and 1.0 seconds')
        self.require_fr5_clear = bool(
            self.get_parameter('require_fr5_clear').value
        )
        self.motion_timeout = float(self.get_parameter('motion_timeout').value)
        if not math.isfinite(self.motion_timeout) or self.motion_timeout <= 0.0:
            raise ValueError('motion_timeout must be finite and > 0 seconds')

        self.state = IDLE
        self.target_station = ''
        self.reason = 'server started'
        self.motion_started_at = 0.0
        self.server_instance_id = str(uuid.uuid4())
        self.motion_sequence = 0
        self.motion_id = None
        self.arrival = None
        self.ready = Signal()
        self.fr5_clear = Signal()
        self.triggers = {
            'assembly': Signal(),
            'inspection': Signal(),
        }

        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        state_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.command_publisher = self.create_publisher(
            TwistStamped, self.cmd_topic, command_qos
        )
        self.state_publisher = self.create_publisher(
            String, '/conveyor/state', state_qos
        )
        self.moving_publisher = self.create_publisher(
            Bool, '/conveyor/moving', state_qos
        )

        self.create_subscription(
            Bool,
            '/vision/conveyor/stop_line_ready',
            self._ready_callback,
            1,
        )
        for station in self.triggers:
            self.create_subscription(
                Bool,
                station_trigger_topic(station),
                lambda message, name=station: self._trigger_callback(name, message),
                1,
            )
        self.create_subscription(
            Bool, self.fr5_clear_topic, self._fr5_clear_callback, 1
        )

        self.create_service(
            Trigger, '/conveyor/move_to_assembly', self._move_to_assembly
        )
        self.create_service(
            Trigger, '/conveyor/move_to_inspection', self._move_to_inspection
        )
        self.create_service(Trigger, '/conveyor/stop', self._stop)
        self.create_service(Trigger, '/conveyor/reset', self._reset)
        self.create_timer(0.02, self._control_tick)
        self.create_timer(0.10, self._publish_state)

        mode = 'ARMED' if self.armed else 'MONITOR-ONLY'
        self.get_logger().warning(
            f'{mode} remote conveyor server: cmd={self.cmd_topic}, '
            f'linear.x={self.command_speed:.3f}, '
            f'FR5 interlock={self.require_fr5_clear} ({self.fr5_clear_topic})'
        )

    @property
    def moving(self) -> bool:
        return self.state in (MOVING_TO_ASSEMBLY, MOVING_TO_INSPECTION)

    def _now(self) -> float:
        return time.monotonic()

    def _ready_callback(self, message: Bool) -> None:
        self.ready = Signal(bool(message.data), self._now())
        if self.moving and not message.data:
            self._fault('S22 stop-line safety became not ready')

    def _trigger_callback(self, station: str, message: Bool) -> None:
        self.triggers[station] = Signal(bool(message.data), self._now())
        if self.moving and self.target_station == station and message.data:
            stop_state = (
                ASSEMBLY_STOP if station == 'assembly' else INSPECTION_STOP
            )
            self._hold(stop_state, f'{station} vision stop trigger')

    def _fr5_clear_callback(self, message: Bool) -> None:
        self.fr5_clear = Signal(bool(message.data), self._now())
        if self.moving and self.require_fr5_clear and not message.data:
            self._fault('FR5 entered or may have entered the conveyor work area')

    def _other_command_publisher_exists(self) -> bool:
        # Graph queries do not apply topic remaps. Inspect the actual publisher
        # topic, and count endpoints: ROS permits identical node names.
        endpoints = self.get_publishers_info_by_topic(
            self.command_publisher.topic_name
        )
        if len(endpoints) > 1:
            return True
        for endpoint in endpoints:
            if (
                endpoint.node_name != self.get_name()
                or endpoint.node_namespace != self.get_namespace()
            ):
                return True
        return False

    def _start_context(self) -> StartContext:
        return StartContext(
            armed=self.armed,
            state=self.state,
            ready=self.ready,
            assembly_trigger=self.triggers['assembly'],
            inspection_trigger=self.triggers['inspection'],
            fr5_clear=self.fr5_clear,
            heartbeat_timeout=self.heartbeat_timeout,
            fr5_timeout=self.fr5_timeout,
            require_fr5_clear=self.require_fr5_clear,
            duplicate_cmd_publisher=self._other_command_publisher_exists(),
        )

    def _publish_command(self, speed: float) -> None:
        command = TwistStamped()
        command.header.stamp = self.get_clock().now().to_msg()
        command.twist.linear.x = float(speed)
        self.command_publisher.publish(command)

    def _hold(self, state: str, reason: str) -> None:
        was_moving = self.moving
        completed_station = self.target_station
        self.state = state
        self.target_station = ''
        self.reason = reason
        self.motion_started_at = 0.0
        self._publish_command(0.0)
        if was_moving and state in (ASSEMBLY_STOP, INSPECTION_STOP):
            self.arrival = {
                'station': completed_station,
                'motion_id': self.motion_id,
                'timestamp_ns': self.get_clock().now().nanoseconds,
                'basis': 'VISION_TRIGGER_AND_ZERO_COMMAND_NOT_ENCODER_FEEDBACK',
            }
        if was_moving:
            self.get_logger().warning(f'CONVEYOR HOLD: {state}: {reason}')
        self._publish_state()

    def _fault(self, reason: str) -> None:
        self._hold(FAULT, reason)

    def _request_move(self, station: str, response) -> Trigger.Response:
        now = self._now()
        context = self._start_context()
        accepted, reason = validate_start_request(station, context, now)
        if not accepted:
            # Rejected duplicate requests are not stop requests. Do not inject
            # a zero followed by a timer-driven restart into an accepted move.
            # The active move keeps its original watchdogs and deadline.
            if self.moving:
                fault = moving_fault_reason(context, self.target_station, now)
                if fault:
                    self._fault(fault)
            else:
                self._publish_command(0.0)
            response.success = False
            response.message = reason
            self.get_logger().warning(f'REMOTE MOVE REJECTED: {station}: {reason}')
            return response

        self.target_station = station
        self.motion_sequence += 1
        self.motion_id = f'{self.server_instance_id}:{self.motion_sequence}'
        self.arrival = None
        self.state = (
            MOVING_TO_ASSEMBLY
            if station == 'assembly'
            else MOVING_TO_INSPECTION
        )
        self.reason = 'remote service request accepted'
        self.motion_started_at = now
        self._publish_command(self.command_speed)
        self._publish_state()
        response.success = True
        response.message = json.dumps(
            {'accepted': True, 'state': self.state, 'target': station,
             'motion_id': self.motion_id},
            separators=(',', ':'),
        )
        self.get_logger().warning(
            f'REMOTE MOVE ACCEPTED: {station}, linear.x={self.command_speed:.3f}'
        )
        return response

    def _move_to_assembly(self, _request, response) -> Trigger.Response:
        return self._request_move('assembly', response)

    def _move_to_inspection(self, _request, response) -> Trigger.Response:
        return self._request_move('inspection', response)

    def _stop(self, _request, response) -> Trigger.Response:
        self._hold(MANUAL_STOP, 'remote stop service request')
        response.success = True
        response.message = 'conveyor hold command published'
        return response

    def _reset(self, _request, response) -> Trigger.Response:
        if self.moving:
            response.success = False
            response.message = 'cannot reset while moving; call /conveyor/stop first'
            return response
        self._publish_command(0.0)
        self.state = IDLE
        self.arrival = None
        self.target_station = ''
        self.reason = 'remote reset; no motion started'
        self.motion_started_at = 0.0
        self._publish_state()
        response.success = True
        response.message = 'controller reset to IDLE; conveyor remains stopped'
        return response

    def _control_tick(self) -> None:
        if not self.moving:
            self._publish_command(0.0)
            return

        now = self._now()
        reason = moving_fault_reason(
            self._start_context(), self.target_station, now
        )
        if reason:
            self._fault(reason)
            return
        if (
            not math.isfinite(self.motion_started_at)
            or self.motion_started_at <= 0.0
            or now < self.motion_started_at
        ):
            self._fault('invalid motion clock')
            return
        if now - self.motion_started_at >= self.motion_timeout:
            self._fault('motion timeout')
            return
        if self.triggers[self.target_station].value:
            stop_state = (
                ASSEMBLY_STOP
                if self.target_station == 'assembly'
                else INSPECTION_STOP
            )
            self._hold(stop_state, f'{self.target_station} vision stop trigger')
            return
        self._publish_command(self.command_speed)

    def _publish_state(self) -> None:
        now = self._now()
        payload = {
            'schema_version': 1,
            'timestamp_ns': self.get_clock().now().nanoseconds,
            'state': self.state,
            'moving': self.moving,
            'target_station': self.target_station or None,
            'server_instance_id': self.server_instance_id,
            'motion_id': self.motion_id,
            'arrival': self.arrival if self.state in (ASSEMBLY_STOP, INSPECTION_STOP) else None,
            'completed_station': (self.arrival or {}).get('station')
                if self.state in (ASSEMBLY_STOP, INSPECTION_STOP) else None,
            'reason': self.reason,
            'armed': self.armed,
            'command_linear_x_mps': self.command_speed if self.moving else 0.0,
            'vision_ready': self.ready.value,
            'vision_ready_fresh': signal_is_fresh(
                self.ready, now, self.heartbeat_timeout
            ),
            'assembly_trigger': self.triggers['assembly'].value,
            'inspection_trigger': self.triggers['inspection'].value,
            'fr5_clear': self.fr5_clear.value,
            'fr5_clear_fresh': signal_is_fresh(
                self.fr5_clear, now, self.fr5_timeout
            ),
            'fr5_interlock_required': self.require_fr5_clear,
        }
        self.state_publisher.publish(
            String(data=json.dumps(payload, separators=(',', ':')))
        )
        self.moving_publisher.publish(Bool(data=self.moving))

    def emergency_stop(self) -> None:
        if not rclpy.ok():
            return
        for _ in range(10):
            self._publish_command(0.0)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ConveyorRemoteServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().warning('Ctrl+C received; publishing emergency stop')
    finally:
        if rclpy.ok():
            node.emergency_stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
