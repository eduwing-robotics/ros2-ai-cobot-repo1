import argparse
import math
import time

import rclpy
from geometry_msgs.msg import Twist, TwistStamped
from rclpy.node import Node
from std_msgs.msg import Bool


def bounded_speed(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0 or value > 0.10:
        raise ValueError('test speed must be > 0 and <= 0.10 m/s')
    return value


class ConveyorController(Node):
    def __init__(self, args):
        super().__init__('conveyor_controller')
        self.speed = bounded_speed(args.speed)
        self.timeout = float(args.timeout)
        if not math.isfinite(self.timeout) or self.timeout < 0.0:
            raise ValueError('timeout must be >= 0 seconds (0 disables timeout)')

        self.trigger = False
        self.ready = False
        self.last_ready_time = 0.0
        self.started_at = time.monotonic()
        self.stopped = False
        self.stop_reason = ''
        self.stop_publish_count = 0

        self.cmd_type = args.cmd_type
        message_type = TwistStamped if self.cmd_type == 'twist_stamped' else Twist
        self.publisher = self.create_publisher(message_type, args.cmd_topic, 10)
        self.create_subscription(
            Bool, args.trigger_topic, self.trigger_callback, 10
        )
        self.create_subscription(Bool, args.ready_topic, self.ready_callback, 10)
        self.timer = self.create_timer(0.05, self.control_tick)
        self.get_logger().warning(
            f'MOTION TEST ARMED: {args.cmd_topic} ({self.cmd_type}), '
            f'speed={self.speed:.3f} m/s, '
            f'timeout={"disabled" if self.timeout == 0.0 else f"{self.timeout:.1f} s"}'
        )

    def trigger_callback(self, message):
        self.trigger = bool(message.data)

    def ready_callback(self, message):
        self.ready = bool(message.data)
        self.last_ready_time = time.monotonic()

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
        if self.trigger:
            self.request_stop('vision stop trigger')
            return
        if self.timeout > 0.0 and now - self.started_at >= self.timeout:
            self.request_stop('safety timeout')
            return
        if self.last_ready_time == 0.0:
            self.publish_speed(0.0)
            if now - self.started_at > 3.0:
                self.request_stop('vision heartbeat not received at startup')
            return
        if not self.ready or now - self.last_ready_time > 1.0:
            self.request_stop('vision heartbeat missing')
            return
        self.publish_speed(self.speed)

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
    parser.add_argument('--trigger-topic', default='/vision/conveyor/stop_trigger')
    parser.add_argument('--ready-topic', default='/vision/conveyor/stop_line_ready')
    parser.add_argument('--speed', type=float, default=0.02)
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm-motion', action='store_true')
    return parser.parse_args()


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
