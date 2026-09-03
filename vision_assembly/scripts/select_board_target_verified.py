#!/usr/bin/env python3
"""Select a board slot and require status acknowledgement; never moves the robot."""

import argparse
import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class VerifiedSelector(Node):
    def __init__(self, target_slot: str, selection_topic: str, status_topic: str):
        super().__init__('select_board_target_verified')
        self.target_slot = target_slot.strip().upper().replace('_', '-')
        self.publisher = self.create_publisher(String, selection_topic, 10)
        self.create_subscription(String, status_topic, self.status_cb, 10)
        self.timer = self.create_timer(0.25, self.publish_selection)
        self.match_count = 0
        self.last_selected = None

    def publish_selection(self):
        self.publisher.publish(String(data=self.target_slot))

    def status_cb(self, message):
        try:
            payload = json.loads(message.data)
        except (TypeError, ValueError):
            return
        selected = str(payload.get('selected_slot', '')).strip().upper().replace('_', '-')
        self.last_selected = selected or None
        if bool(payload.get('valid')) and selected == self.target_slot:
            self.match_count += 1
        else:
            self.match_count = 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-slot', required=True)
    parser.add_argument('--selection-topic', default='/vision/board/selected_target')
    parser.add_argument('--status-topic', default='/vision/board/pose_3d/status')
    parser.add_argument('--required-matches', type=int, default=3)
    parser.add_argument('--timeout-sec', type=float, default=12.0)
    args = parser.parse_args()
    if args.required_matches < 1:
        parser.error('--required-matches must be positive')

    rclpy.init()
    node = VerifiedSelector(args.target_slot, args.selection_topic, args.status_topic)
    try:
        deadline = time.monotonic() + args.timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.match_count >= args.required_matches:
                print(
                    f'VERIFIED selected_slot={node.target_slot} '
                    f'for {node.match_count} consecutive status messages'
                )
                return
        raise RuntimeError(
            f'board target selection was not acknowledged: requested={node.target_slot}, '
            f'last_selected={node.last_selected}'
        )
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
