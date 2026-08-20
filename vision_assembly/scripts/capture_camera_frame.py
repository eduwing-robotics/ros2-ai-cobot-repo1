#!/usr/bin/env python3
"""Save one compressed camera frame without moving the robot."""

import argparse
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class Capture(Node):
    def __init__(self, topic, output):
        super().__init__('capture_camera_frame')
        self.output = output
        self.create_subscription(CompressedImage, topic, self.cb, qos_profile_sensor_data)

    def cb(self, message):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_bytes(bytes(message.data))
        print(f'Saved {message.header.stamp.sec}.{message.header.stamp.nanosec:09d}: {self.output}')
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rclpy.init()
    node = Capture(args.topic, args.output)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
