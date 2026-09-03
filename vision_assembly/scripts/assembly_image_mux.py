#!/usr/bin/env python3
"""Publish one operator image topic, selecting tray/SMD or board by robot pose."""

import argparse
import math
import time

import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage


class AssemblyImageMux(Node):
    def __init__(self, args):
        super().__init__('assembly_image_mux')
        self.args = args
        self.robot = None
        self.place_pose = None
        self.last_source = None
        self.last_frame = {'tray': None, 'board': None}
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.publisher = self.create_publisher(CompressedImage, args.output_topic, qos)
        self.create_subscription(CompressedImage, args.tray_topic, self.tray_cb, qos)
        self.create_subscription(CompressedImage, args.board_topic, self.board_cb, qos)
        self.create_subscription(RobotNonrtState, args.robot_state_topic, self.robot_cb, 10)
        self.client = self.create_client(RemoteCmdInterface, args.command_service)
        self.timer = self.create_timer(1.0 / args.publish_hz, self.publish_latest)
        self.load_place_pose()

    def load_place_pose(self):
        if not self.client.wait_for_service(timeout_sec=3.0):
            raise RuntimeError(f'command service unavailable: {self.args.command_service}')
        request = RemoteCmdInterface.Request()
        request.cmd_str = f'GetRobotTeachingPoint({self.args.place_point})'
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        if not future.done() or future.result() is None:
            raise RuntimeError(f'cannot read teaching point {self.args.place_point}')
        result = str(future.result().cmd_res)
        fields = result.split(',')
        if fields[0] != '0' or len(fields) < 7:
            raise RuntimeError(f'invalid teaching point {self.args.place_point}: {result}')
        self.place_pose = [float(value) for value in fields[1:7]]
        self.get_logger().info(
            f'{self.args.place_point} XYZ={self.place_pose[:3]}; '
            f'unified output={self.args.output_topic}'
        )

    def robot_cb(self, message):
        self.robot = message

    def tray_cb(self, message):
        self.last_frame['tray'] = (time.monotonic(), message)

    def board_cb(self, message):
        self.last_frame['board'] = (time.monotonic(), message)

    def selected_source(self):
        if self.robot is None or self.place_pose is None:
            return 'tray'
        current = [
            float(self.robot.cart_x_cur_pos),
            float(self.robot.cart_y_cur_pos),
            float(self.robot.cart_z_cur_pos),
        ]
        distance = math.dist(current, self.place_pose[:3])
        # While moving, retain the last view. Both renderers independently hide
        # overlays on robot_motion_done != 1, so the unified topic stays live-only.
        if int(self.robot.robot_motion_done) != 1:
            return self.last_source or ('board' if distance <= self.args.place_exit_mm else 'tray')
        if self.last_source == 'board':
            return 'board' if distance <= self.args.place_exit_mm else 'tray'
        return 'board' if distance <= self.args.place_enter_mm else 'tray'

    def publish_latest(self):
        source = self.selected_source()
        value = self.last_frame[source]
        if value is None or time.monotonic() - value[0] > self.args.max_frame_age_sec:
            fallback = self.last_frame['board' if source == 'tray' else 'tray']
            if fallback is None or time.monotonic() - fallback[0] > self.args.max_frame_age_sec:
                return
            value = fallback
        if source != self.last_source:
            self.get_logger().info(f'operator view -> {source.upper()}')
            self.last_source = source
        self.publisher.publish(value[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tray-topic', default='/vision/tray/detections_image/compressed')
    parser.add_argument('--board-topic', default='/vision/board/image/compressed')
    parser.add_argument('--output-topic', default='/vision/assembly/image/compressed')
    parser.add_argument('--robot-state-topic', default='/nonrt_state_data')
    parser.add_argument('--command-service', default='/fairino_remote_command_service')
    parser.add_argument('--place-point', default='PlaceCamera')
    parser.add_argument('--place-enter-mm', type=float, default=12.0)
    parser.add_argument('--place-exit-mm', type=float, default=25.0)
    parser.add_argument('--publish-hz', type=float, default=10.0)
    parser.add_argument('--max-frame-age-sec', type=float, default=1.0)
    args = parser.parse_args()
    if args.place_enter_mm <= 0 or args.place_exit_mm <= args.place_enter_mm:
        parser.error('place thresholds must satisfy 0 < enter < exit')
    rclpy.init()
    node = None
    try:
        node = AssemblyImageMux(args)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
