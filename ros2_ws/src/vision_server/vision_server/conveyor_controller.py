import argparse
import math
import time

from geometry_msgs.msg import Twist, TwistStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool


def bounded_speed(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0 or value > 0.10:
        raise ValueError('test speed must be > 0 and <= 0.10 m/s')
    return value


def bounded_heartbeat_timeout(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.10 or value > 1.0:
        raise ValueError('heartbeat timeout must be between 0.10 and 1.0 seconds')
    return value


def heartbeat_is_fresh(received_at: float, now: float, timeout: float) -> bool:
    """Missing, invalid, or future reception times never authorize motion."""
    return bool(
        all(math.isfinite(value) for value in (received_at, now, timeout))
        and received_at > 0.0
        and timeout > 0.0
        and 0.0 <= now - received_at <= timeout + 1e-9
    )


def signed_speed(speed: float, direction: str) -> float:
    speed = bounded_speed(speed)
    if direction == 'positive_x':
        return speed
    if direction == 'negative_x':
        return -speed
    raise ValueError("direction must be 'positive_x' or 'negative_x'")


def station_trigger_topic(station: str) -> str:
    if station not in ('assembly', 'inspection'):
        raise ValueError("station must be 'assembly' or 'inspection'")
    return f'/vision/conveyor/{station}/stop_trigger'


class ConveyorController(Node):
    def __init__(self, args):
        super().__init__('conveyor_controller')
        self.speed = bounded_speed(args.speed)
        self.command_speed = signed_speed(self.speed, args.direction)
        self.direction = args.direction
        self.timeout = float(args.timeout)
        if not math.isfinite(self.timeout) or self.timeout < 0.0:
            raise ValueError('timeout must be >= 0 seconds (0 disables timeout)')
        self.heartbeat_timeout = bounded_heartbeat_timeout(
            args.heartbeat_timeout
        )

        self.trigger = False
        self.ready = False
        self.last_trigger_time = 0.0
        self.last_ready_time = 0.0
        self.started_at = time.monotonic()
        self.stopped = False
        self.stop_reason = ''
        self.stop_publish_count = 0

        self.cmd_type = args.cmd_type
        self.station = args.station
        self.trigger_topic = args.trigger_topic
        message_type = TwistStamped if self.cmd_type == 'twist_stamped' else Twist
        # Keep only the newest motion command. A reliable depth-10 queue can
        # replay old speed commands before the zero command on a congested
        # network, extending belt motion after the visual trigger.
        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.publisher = self.create_publisher(
            message_type, args.cmd_topic, command_qos
        )
        self.create_subscription(
            Bool, self.trigger_topic, self.trigger_callback, 1
        )
        self.create_subscription(Bool, args.ready_topic, self.ready_callback, 1)
        self.timer = self.create_timer(0.02, self.control_tick)
        self.get_logger().warning(
            f'MOTION TEST ARMED: {args.cmd_topic} ({self.cmd_type}), '
            f'station={self.station}, trigger={self.trigger_topic}, '
            f'belt speed={self.speed:.3f} m/s, robot direction={self.direction}, '
            f'linear.x={self.command_speed:.3f} m/s, '
            f'heartbeat_timeout={self.heartbeat_timeout:.2f}s, '
            f'timeout={"disabled" if self.timeout == 0.0 else f"{self.timeout:.1f} s"}'
        )

    def trigger_callback(self, message):
        self.trigger = bool(message.data)
        self.last_trigger_time = time.monotonic()
        # Stop in the subscription callback so a visual line crossing does not
        # wait for the next 20 ms control tick.  The timer continues publishing
        # zero afterwards to make the stop command robust on the network.
        if self.trigger and not self.stopped:
            self.request_stop(f'{self.station} vision stop trigger')

    def ready_callback(self, message):
        self.ready = bool(message.data)
        self.last_ready_time = time.monotonic()
        if not self.ready and not self.stopped:
            self.request_stop('vision safety became not ready')

    def publish_speed(self, speed):
        if self.cmd_type == 'twist_stamped':
            command = TwistStamped()
            command.header.stamp = self.get_clock().now().to_msg()
            command.twist.linear.x = float(speed)
        else:
            command = Twist()
            command.linear.x = float(speed)
        self.publisher.publish(command)

    def request_stop(self, reason):
        if not self.stopped:
            self.stopped = True
            self.stop_reason = reason
            self.get_logger().warning(f'CONVEYOR STOP: {reason}')
        self.publish_speed(0.0)
        self.stop_publish_count += 1
        if self.stop_publish_count >= 10:
            self.get_logger().info('Zero speed published 10 times; test complete')
            rclpy.shutdown()

    def control_tick(self):
        now = time.monotonic()
        if self.stopped:
            self.request_stop(self.stop_reason)
            return
        if (
            not math.isfinite(now)
            or not math.isfinite(self.started_at)
            or now < self.started_at
        ):
            self.request_stop('invalid motion clock')
            return
        if self.trigger:
            self.request_stop(f'{self.station} vision stop trigger')
            return
        if self.timeout > 0.0 and now - self.started_at >= self.timeout:
            self.request_stop('safety timeout')
            return
        if self.last_ready_time == 0.0 or self.last_trigger_time == 0.0:
            self.publish_speed(0.0)
            if now - self.started_at > 3.0:
                missing = []
                if self.last_ready_time == 0.0:
                    missing.append('ready')
                if self.last_trigger_time == 0.0:
                    missing.append(f'{self.station} trigger')
                self.request_stop(
                    'vision heartbeat not received at startup: ' + ', '.join(missing)
                )
            return
        if (
            not self.ready
            or not heartbeat_is_fresh(
                self.last_ready_time, now, self.heartbeat_timeout
            )
            or not heartbeat_is_fresh(
                self.last_trigger_time, now, self.heartbeat_timeout
            )
        ):
            self.request_stop('vision heartbeat missing')
            return
        self.publish_speed(self.command_speed)

    def emergency_stop(self):
        if not rclpy.ok():
            return
        for _ in range(10):
            self.publish_speed(0.0)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Low-speed TurtleBot conveyor stop-line test'
    )
    parser.add_argument('--cmd-topic', default='/cmd_vel')
    parser.add_argument(
        '--cmd-type', choices=('twist', 'twist_stamped'), default='twist_stamped'
    )
    parser.add_argument(
        '--station',
        choices=('assembly', 'inspection'),
        default='assembly',
        help='Stop station selected for this one conveyor movement',
    )
    parser.add_argument(
        '--trigger-topic',
        default=None,
        help='Advanced override; default is derived from --station',
    )
    parser.add_argument('--ready-topic', default='/vision/conveyor/stop_line_ready')
    parser.add_argument('--speed', type=float, default=0.02)
    parser.add_argument(
        '--heartbeat-timeout',
        type=float,
        default=0.25,
        help='stop if fresh vision status is absent for this many seconds',
    )
    parser.add_argument(
        '--direction',
        choices=('positive_x', 'negative_x'),
        default='positive_x',
        help='TurtleBot linear.x direction used to move the physical belt forward',
    )
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-motion', action='store_true')
    args = parser.parse_args()
    if args.trigger_topic is None:
        args.trigger_topic = station_trigger_topic(args.station)
    return args


def main():
    args = parse_args()
    if not (args.execute and args.confirm_motion):
        raise SystemExit(
            'DRY RUN: no motion. Add --execute --confirm-motion to publish '
            'low-speed commands.'
        )
    rclpy.init()
    node = ConveyorController(args)
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
