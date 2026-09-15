#!/usr/bin/env python3
"""Capture one S22 pixel/TCP Base point pair interactively; sends no motion."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class PointCapture(Node):
    def __init__(self, args):
        super().__init__('capture_s22_plane_point')
        self.args = args
        self.frame = None
        self.selected = None
        self.robot = None
        self.robot_xyz_history = deque(maxlen=20)
        self.create_subscription(
            CompressedImage,
            args.image_topic,
            self.image_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            RobotNonrtState, args.robot_state_topic, self.robot_cb, 10
        )
        self.get_logger().info(
            'NO MOTION: place the calibrated TCP on the physical reference, '
            'click the same point in the S22 image, then press S to save'
        )

    def image_cb(self, message):
        frame = cv2.imdecode(
            np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if frame is not None:
            self.frame = frame

    def robot_cb(self, message):
        self.robot = message
        self.robot_xyz_history.append(
            [message.cart_x_cur_pos, message.cart_y_cur_pos, message.cart_z_cur_pos]
        )

    def stationary(self):
        if self.robot is None or len(self.robot_xyz_history) < 10:
            return False
        values = np.asarray(self.robot_xyz_history, dtype=float)
        span = np.max(values, axis=0) - np.min(values, axis=0)
        return bool(
            int(self.robot.robot_motion_done) == 1
            and float(np.max(span)) <= self.args.max_stationary_span_mm
        )

    def mouse_cb(self, event, x, y, _flags, _parameter):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.selected = (int(x), int(y))

    def draw(self):
        if self.frame is None:
            return None
        image = self.frame.copy()
        cv2.rectangle(image, (0, 0), (image.shape[1], 105), (18, 24, 30), -1)
        cv2.putText(
            image, f'S22 PLANE POINT: {self.args.label}', (22, 38),
            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA,
        )
        state = 'STATIONARY' if self.stationary() else 'WAIT ROBOT STILL'
        cv2.putText(
            image, f'Click reference, then S=save | Q=quit | {state}', (22, 78),
            cv2.FONT_HERSHEY_SIMPLEX, 0.62,
            (70, 235, 90) if self.stationary() else (0, 190, 255),
            2, cv2.LINE_AA,
        )
        if self.selected is not None:
            cv2.drawMarker(
                image, self.selected, (0, 0, 255), cv2.MARKER_CROSS, 34, 3
            )
        return image

    def save(self):
        if self.frame is None or self.selected is None:
            raise RuntimeError('Select an S22 image point first')
        if not self.stationary():
            raise RuntimeError('Robot TCP state is missing or not stationary')
        height, width = self.frame.shape[:2]
        x, y = self.selected
        state = self.robot
        entry = {
            'label': self.args.label,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'image_px': [x, y],
            'image_size_px': [width, height],
            'image_normalized': [x / (width - 1.0), y / (height - 1.0)],
            'base_tcp_xyz_mm': [
                float(state.cart_x_cur_pos),
                float(state.cart_y_cur_pos),
                float(state.cart_z_cur_pos),
            ],
            'tool_num': int(state.tool_num),
        }
        if self.args.points_file.exists():
            payload = json.loads(self.args.points_file.read_text(encoding='utf-8'))
        else:
            payload = {
                'schema_version': 1,
                'image_topic': self.args.image_topic,
                'robot_state_topic': self.args.robot_state_topic,
                'robot_motion_sent': False,
                'points': [],
            }
        payload['points'] = [
            item for item in payload.get('points', [])
            if item.get('label') != self.args.label
        ]
        payload['points'].append(entry)
        self.args.points_file.parent.mkdir(parents=True, exist_ok=True)
        self.args.points_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
        print('Saved S22/Base point:', json.dumps(entry, ensure_ascii=False))
        print('Total points:', len(payload['points']))
        print('File:', self.args.points_file)


def main():
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument(
        '--points-file', type=Path,
        default=project_root / 'vision_assembly/data/s22_plane_points.json',
    )
    parser.add_argument('--image-topic', default='/camera2/image_raw/compressed')
    parser.add_argument('--robot-state-topic', default='/nonrt_state_data')
    parser.add_argument('--max-stationary-span-mm', type=float, default=0.20)
    args = parser.parse_args()

    rclpy.init()
    node = PointCapture(args)
    window = 'S22 Plane Calibration - NO MOTION'
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, node.mouse_cb)
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.02)
            image = node.draw()
            if image is not None:
                cv2.imshow(window, image)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            if key in (ord('s'), 13):
                node.save()
                break
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
