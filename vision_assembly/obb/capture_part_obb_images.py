#!/usr/bin/env python3
"""Capture sharp D435 frames for the real multi-class OBB dataset; no motion."""
import argparse
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


PARTS = ('gpu', 'hbm', 'power_module', 'vrm', 'inductor', 'smd_capacitor')


class Capture(Node):
    def __init__(self, args):
        super().__init__('capture_part_obb_images')
        self.args = args
        self.saved = 0
        self.last_saved_at = 0.0
        args.output.mkdir(parents=True, exist_ok=True)
        self.create_subscription(
            CompressedImage, args.topic, self.callback, qos_profile_sensor_data
        )
        self.get_logger().info(
            f'NO MOTION: {args.part_type}, saving {args.count} sharp frame(s) '
            f'from {args.topic}'
        )

    def callback(self, message):
        now = time.monotonic()
        if now - self.last_saved_at < self.args.interval_sec:
            return
        image = cv2.imdecode(
            np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR
        )
        if image is None:
            return
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if sharpness < self.args.min_sharpness:
            return
        stamp = time.strftime('%Y%m%d_%H%M%S') + f'_{message.header.stamp.nanosec:09d}'
        path = self.args.output / f'{self.args.part_type}_{stamp}.jpg'
        if not cv2.imwrite(
            str(path), image, [cv2.IMWRITE_JPEG_QUALITY, self.args.jpeg_quality]
        ):
            self.get_logger().error(f'Failed to save {path}')
            return
        self.saved += 1
        self.last_saved_at = now
        self.get_logger().info(
            f'Saved {self.saved}/{self.args.count}: {path.name}, '
            f'sharpness={sharpness:.1f}'
        )
        if self.saved >= self.args.count:
            rclpy.shutdown()


def main():
    root = Path(__file__).parent / 'real_multiclass'
    parser = argparse.ArgumentParser()
    parser.add_argument('--part-type', choices=PARTS, required=True)
    parser.add_argument('--topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--output', type=Path, default=root / 'images/unlabeled')
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--interval-sec', type=float, default=0.8)
    parser.add_argument('--min-sharpness', type=float, default=20.0)
    parser.add_argument('--jpeg-quality', type=int, default=98)
    args = parser.parse_args()
    if args.count < 1 or args.interval_sec <= 0.0:
        parser.error('invalid count/interval')
    if not 80 <= args.jpeg_quality <= 100:
        parser.error('--jpeg-quality must be between 80 and 100')
    rclpy.init()
    node = Capture(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
