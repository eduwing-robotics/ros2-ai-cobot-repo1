"""Fail-safe, service-driven conveyor controller for Main Server integration."""

from dataclasses import dataclass
import json
import math
import os
import time
import uuid

from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.executors import ExternalShutdownException
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
    bounded_speed,
    heartbeat_is_fresh,
    signed_speed,
    station_trigger_topic,
)
from .conveyor_arrival import (
    arrival_matches,
    empty_matches,
    restart_empty_matches,
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
    # Compatibility-only field retained for callers that construct the old
    # context shape.  It is not consulted by motion validation.
    heartbeat_timeout: float = 0.0
    duplicate_cmd_publisher: bool = False
    command_receiver_connected: bool = True


def signal_is_fresh(signal: Signal, now: float, timeout: float) -> bool:
    """Legacy helper retained for API compatibility; unused by motion control."""
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
    # The ready and trigger topics are ordinary current-status topics.  A
    # delayed DDS sample must not turn into a false motion fault.  An explicit
    # false status still blocks/halts motion, while the independent motion
    # deadline remains the bounded fail-safe if the camera stops publishing.
    if not context.ready.value:
        return False, 'S22 stop-line status is not ready'

    if not context.command_receiver_connected:
        return False, 'robot command receiver is not connected on /cmd_vel'

    selected = (
        context.assembly_trigger
        if station == 'assembly'
        else context.inspection_trigger
    )
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
    if not context.ready.value:
        return 'S22 stop-line status became not ready'
    if not context.command_receiver_connected:
        return 'robot command receiver disconnected from /cmd_vel'
    # A missing update is not a fault.  A received true trigger is handled by
    # _trigger_callback and is also checked in the control tick below.
    return None


class ConveyorRemoteServer(Node):
    """Own `/cmd_vel` and expose guarded station movement services."""

    def __init__(self) -> None:
        super().__init__('conveyor_remote_server')
        self.declare_parameter('allow_motion', False)
        self.declare_parameter('startup_hold', os.environ.get('KSMC_CONVEYOR_STARTUP_HOLD') == '1')
        self.declare_parameter('cmd_topic', '/cmd_vel')
        self.declare_parameter('speed', 0.10)
        self.declare_parameter('direction', 'negative_x')
        # Accepted only for old launch files; it has no effect.
        self.declare_parameter('heartbeat_timeout', 0.15)
        self.declare_parameter('arrival_evidence_max_age', 0.5)
        self.declare_parameter('motion_timeout', 30.0)

        self.armed = bool(self.get_parameter('allow_motion').value)
        self.cmd_topic = str(self.get_parameter('cmd_topic').value)
        self.speed = bounded_speed(self.get_parameter('speed').value)
        self.direction = str(self.get_parameter('direction').value)
        self.command_speed = signed_speed(self.speed, self.direction)
        # ``heartbeat_timeout`` is deliberately ignored.  Ready and trigger
        # are current boolean statuses; only explicit false/true values,
        # visual arrival evidence, and the finite motion deadline affect a
        # move.  Keep a separate age bound for arrival observations so an old
        # image can never be used to skip a new move.
        self.heartbeat_timeout = 0.0
        self._arrival_evidence_max_age = float(
            self.get_parameter('arrival_evidence_max_age').value
        )
        if (
            not math.isfinite(self._arrival_evidence_max_age)
            or self._arrival_evidence_max_age <= 0.0
        ):
            raise ValueError('arrival_evidence_max_age must be finite and > 0 seconds')
        self._command_receiver_connected = True
        self._last_command_receiver_check = -math.inf
        self.motion_timeout = float(self.get_parameter('motion_timeout').value)
        if not math.isfinite(self.motion_timeout) or self.motion_timeout <= 0.0:
            raise ValueError('motion_timeout must be finite and > 0 seconds')

        startup_hold = bool(self.get_parameter('startup_hold').value)
        self.state = MANUAL_STOP if startup_hold else IDLE
        self.target_station = ''
        self.reason = 'maintenance restart; manual stop retained' if startup_hold else 'server started'
        self.motion_started_at = 0.0
        self.server_instance_id = str(uuid.uuid4())
        self.motion_sequence = 0
        self.motion_id = None
        self.arrival = None
        self.live_arrivals = {}
        self.ready = Signal()
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
                String, f'/vision/conveyor/{station}/arrival_observation',
                lambda message, name=station: self._arrival_callback(name, message), 1)
            self.create_service(
                Trigger, f'/conveyor/check_{station}_arrival',
                lambda request, response, name=station: self._check_arrival(name, response))

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
            f'linear.x={self.command_speed:.3f}, FR5 permission removed'
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

    def _command_receiver_exists(self) -> bool:
        """Check that a compatible robot node can consume ``/cmd_vel``.

        Previously a move was accepted even when TurtleBot bringup was down,
        then the watchdog reported only ``motion timeout`` much later.  Make
        that wiring failure explicit at request time.  The plain callback
        harness used by unit tests has no ROS graph method and is treated as
        connected.
        """
        getter = getattr(self, 'get_subscriptions_info_by_topic', None)
        if getter is None:
            return True
        now = self._now()
        if now - self._last_command_receiver_check < 0.25:
            return self._command_receiver_connected
        try:
            endpoints = getter(self.command_publisher.topic_name)
        except Exception:
            self._command_receiver_connected = False
            self._last_command_receiver_check = now
            return False

        expected = 'geometry_msgs/msg/TwistStamped'
        connected = False
        for endpoint in endpoints:
            topic_type = getattr(endpoint, 'topic_type', None)
            if topic_type is None:
                connected = True
                break
            if isinstance(topic_type, (tuple, list, set)):
                connected = expected in topic_type
            else:
                connected = str(topic_type) == expected
            if connected:
                break
        self._command_receiver_connected = connected
        self._last_command_receiver_check = now
        return connected

    def _start_context(self) -> StartContext:
        return StartContext(
            armed=self.armed,
            state=self.state,
            ready=self.ready,
            assembly_trigger=self.triggers['assembly'],
            inspection_trigger=self.triggers['inspection'],
            duplicate_cmd_publisher=self._other_command_publisher_exists(),
            command_receiver_connected=self._command_receiver_exists(),
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

    def _arrival_callback(self, station: str, message: String) -> None:
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict) or payload.get('station') != station:
                raise ValueError('Wrong arrival station')
        except (ValueError, TypeError):
            self.live_arrivals.pop(station, None)
            return
        self.live_arrivals[station] = (payload, self._now())

    def _current_arrival(self, station: str) -> dict:
        payload, received_at = self.live_arrivals.get(station, ({}, 0.0))
        now = self._now()
        valid = (math.isfinite(received_at) and 0 < received_at <= now
                 and now-received_at <= self._arrival_evidence_max_age
                 and arrival_matches(payload, station, self.get_clock().now().nanoseconds,
                                     self._arrival_evidence_max_age, self.server_instance_id,
                                     self.motion_id, self.state))
        return dict(station=station, status='AT_STATION' if valid else 'UNKNOWN',
                    at_station=bool(valid), observation=payload if valid else None)

    def _check_arrival(self, station: str, response) -> Trigger.Response:
        current = self._current_arrival(station)
        response.success = current['at_station']
        response.message = json.dumps(current, separators=(',', ':'))
        return response

    def _request_move(self, station: str, response) -> Trigger.Response:
        # A previous run may have completed at a station and left its stop
        # state latched.  If the operator has since moved the PCB back to the
        # start, consume fresh short-window empty evidence before validating
        # this explicit new request.  The passive control tick still uses the
        # conservative two-second window; this path avoids making the user
        # wait for that timer after a manual reposition.
        if station in ('assembly', 'inspection'):
            self._auto_idle_if_empty(fast=True)
        now = self._now()
        context = self._start_context()
        expected_stop = {'assembly': ASSEMBLY_STOP, 'inspection': INSPECTION_STOP}.get(station)
        # A successful no-op requires current image evidence AND the original
        # controller completion. A STOP label or old latched trigger alone is
        # never sufficient. Preserve IDs; this does not create another move.
        if (expected_stop and self.state == expected_stop and not self.target_station
                and self.armed and not context.duplicate_cmd_publisher
                and context.command_receiver_connected and self.ready.value
                and self.motion_id and isinstance(self.arrival, dict)
                and self.arrival.get('station') == station
                and self.arrival.get('motion_id') == self.motion_id):
            current = self._current_arrival(station)
            if current['at_station']:
                response.success = True
                response.message = json.dumps(dict(
                    accepted=True, already_arrived=True, completed=True,
                    state=self.state, target=station, motion_id=self.motion_id,
                    observation_id=current['observation']['observation_id']), separators=(',', ':'))
                self._publish_state()
                return response
        accepted, reason = validate_start_request(station, context, now)
        if not accepted:
            # Rejected duplicate requests are not stop requests. Do not inject
            # a zero followed by a timer-driven restart into an accepted move.
            # The active move keeps its original watchdogs and deadline.
            if self.moving:
                fault = moving_fault_reason(context, self.target_station, now)
                if fault:
                    self._fault(fault)
            elif not context.duplicate_cmd_publisher:
                # Another publisher (for example an operator teleop node) owns
                # this topic.  A rejected service request must not interrupt
                # that owner with a one-shot zero command.
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

    def _auto_idle_if_empty(self, *, fast=False) -> bool:
        allowed_states = (ASSEMBLY_STOP, INSPECTION_STOP)
        if fast:
            # MANUAL_STOP is still never cleared by the passive timer. An
            # explicit new move request may recover it only with the same
            # fresh two-station empty proof used for a returned board.
            allowed_states += (MANUAL_STOP,)
        if (self.state not in allowed_states or self.target_station
                or not self.ready.value or self._other_command_publisher_exists()):
            return False
        matcher = restart_empty_matches if fast else empty_matches
        allow_manual_stop = fast and self.state == MANUAL_STOP
        for station in ('assembly', 'inspection'):
            payload, received = self.live_arrivals.get(station, ({}, 0.0))
            if (not math.isfinite(received) or not 0 < received <= self._now()
                    or self._now()-received > self._arrival_evidence_max_age
                    or not matcher(payload, station, self.get_clock().now().nanoseconds,
                                         self._arrival_evidence_max_age, self.server_instance_id,
                                         self.motion_id, self.state,
                                         allow_manual_stop=allow_manual_stop)):
                return False
        self.state = IDLE
        self.arrival = None
        self.motion_id = None
        self.target_station = ''
        self.motion_started_at = 0.0
        self.live_arrivals.clear()
        # A stop trigger belongs to the completed motion. Clear it together
        # with the stale completion so the same explicit request is not
        # rejected by a latched true status while the ROI publishes its next
        # frame. FAULT remains deliberately excluded; MANUAL_STOP is allowed
        # here only because this path is reached by an explicit new request.
        now = self._now()
        for station in self.triggers:
            self.triggers[station] = Signal(False, now)
        if fast:
            self.reason = 'both station regions visually empty for 0.4s; request-time IDLE, no motion'
        else:
            self.reason = 'both station regions visually empty for 2s; automatic IDLE, no motion'
        self._publish_state()
        return True

    def _control_tick(self) -> None:
        if not self.moving:
            self._auto_idle_if_empty()
            # IDLE is deliberately passive: repeatedly publishing zero here
            # races an operator teleop publisher on the shared /cmd_vel topic.
            # HOLD/FAULT states already publish the zero command when entered;
            # keep reinforcing that stop while the state remains latched.
            if self.state in (ASSEMBLY_STOP, INSPECTION_STOP, MANUAL_STOP, FAULT):
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
            'live_arrival': {station: self._current_arrival(station)
                             for station in ('assembly', 'inspection')},
            'reason': self.reason,
            'armed': self.armed,
            'command_linear_x_mps': self.command_speed if self.moving else 0.0,
            'vision_ready': self.ready.value,
            # Kept as a compatibility field for older Unity builds.  It is a
            # direct status alias, not an age-based liveness result.
            'vision_ready_fresh': self.ready.value,
            'command_receiver_connected': self._command_receiver_exists(),
            'assembly_trigger': self.triggers['assembly'].value,
            'inspection_trigger': self.triggers['inspection'].value,
            # Legacy status keys: false means unavailable, never robot clearance.
            'fr5_clear': False,
            'fr5_clear_fresh': False,
            'fr5_interlock_required': False,
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
    except (KeyboardInterrupt, ExternalShutdownException):
        node.get_logger().warning('Shutdown received; publishing emergency stop')
    finally:
        if rclpy.ok():
            node.emergency_stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
