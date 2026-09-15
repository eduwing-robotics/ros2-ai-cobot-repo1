#!/usr/bin/env python3
"""Save one compressed ROS color frame without requiring a fiducial."""

import argparse
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class CaptureColorFrame(Node):
    def __init__(self, topic, output):
        super().__init__('capture_color_frame')
        self.output = output
        self.create_subscription(CompressedImage, topic, self.on_image, qos_profile_sensor_data)
        self.get_logger().info(f'Waiting for one color frame on {topic}')

    def on_image(self, message):
        frame = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        self.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(self.output), frame):
            raise RuntimeError(f'Failed to save {self.output}')
        print(f'Saved {frame.shape[1]}x{frame.shape[0]} frame: {self.output}', flush=True)
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--output', type=Path, default=Path('/tmp/ksmc_color_frame.jpg'))
    args = parser.parse_args()
    rclpy.init()
    node = CaptureColorFrame(args.topic, args.output)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
