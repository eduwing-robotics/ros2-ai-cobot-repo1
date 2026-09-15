#!/usr/bin/env python3
"""Capture a stable board-slot Base pose published by board_view; no motion."""

import argparse
from collections import deque
import json
import time
from pathlib import Path

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node


class Collector(Node):
    def __init__(self, args):
        super().__init__('capture_board_target')
        self.args = args
        self.samples = deque(maxlen=args.frames)
        self.received = 0
        self.create_subscription(PoseStamped, args.topic, self.pose_cb, 1)
        self.get_logger().info(f'NO MOTION: collecting {args.frames} board target poses from {args.topic}')

    def pose_cb(self, message):
        self.received += 1
        if self.received <= self.args.warmup_frames:
            return
        position = np.asarray([
            message.pose.position.x, message.pose.position.y, message.pose.position.z
        ], dtype=float)
        quaternion = np.asarray([
            message.pose.orientation.x, message.pose.orientation.y,
            message.pose.orientation.z, message.pose.orientation.w,
        ], dtype=float)
        if not np.all(np.isfinite(position)) or not np.all(np.isfinite(quaternion)):
            return
        self.samples.append((position, quaternion))
        count = len(self.samples)
        if count < self.args.frames and count in (1, 5, 10, 20):
            self.get_logger().info(f'Stable target frames: {count}/{self.args.frames}')
        if count >= self.args.frames:
            positions = np.asarray([sample[0] for sample in self.samples])
            median = np.median(positions, axis=0)
            errors_mm = np.linalg.norm((positions - median) * 1000.0, axis=1)
            if float(np.max(errors_mm)) <= self.args.max_jitter_mm:
                self.get_logger().info(f'Stable target frames: {count}/{self.args.frames}')
                self.finish()
            elif self.received % 15 == 0:
                self.get_logger().warn(
                    f'Waiting for consecutive stable board poses: '
                    f'window jitter max={np.max(errors_mm):.3f} mm '
                    f'(limit {self.args.max_jitter_mm:.3f} mm)'
                )

    def finish(self):
        positions = np.asarray([sample[0] for sample in self.samples])
        median = np.median(positions, axis=0)
        errors_mm = np.linalg.norm((positions - median) * 1000.0, axis=1)
        # Select the observed quaternion nearest the median position to avoid
        # averaging quaternion signs incorrectly.
        reference_index = int(np.argmin(errors_mm))
        quaternion = self.samples[reference_index][1]
        payload = {
            'schema_version': 1,
            'timestamp_unix': time.time(),
            'frame_id': 'base',
            'target_slot': self.args.target_slot,
            'position_base_m': median.tolist(),
            'position_base_mm': (median * 1000.0).tolist(),
            'orientation_xyzw': quaternion.tolist(),
            'frames': self.args.frames,
            'jitter_median_mm': float(np.median(errors_mm)),
            'jitter_max_mm': float(np.max(errors_mm)),
            'robot_motion_sent': False,
        }
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        self.args.output.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        print('\nBOARD TARGET CAPTURED - ROBOT DID NOT MOVE')
        print('Slot:', self.args.target_slot)
        print('Base XYZ [mm]:', np.round(median * 1000.0, 3).tolist())
        print(f'Jitter median/max [mm]: {np.median(errors_mm):.3f}/{np.max(errors_mm):.3f}')
        print('Saved:', self.args.output)
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', default='/vision/board/target_pose')
    parser.add_argument('--target-slot', default='right_white_brown_01')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--warmup-frames', type=int, default=10)
    parser.add_argument('--max-jitter-mm', type=float, default=1.0)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/board_target_last.json')
    args = parser.parse_args()
    rclpy.init()
    node = Collector(args)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
