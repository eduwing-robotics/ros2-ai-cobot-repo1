#!/usr/bin/env python3
"""Detect the empty 139x110 mm board and report its camera/base pose; no motion."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage


def transform(rotation, translation):
    value = np.eye(4)
    value[:3, :3] = rotation
    value[:3, 3] = translation
    return value


def ordered_box(points):
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    result = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    result[0] = points[np.argmin(sums)]       # top-left
    result[2] = points[np.argmax(sums)]       # bottom-right
    result[1] = points[np.argmin(differences)] # top-right
    result[3] = points[np.argmax(differences)] # bottom-left
    return result


class BoardDetector(Node):
    def __init__(self, args):
        super().__init__('detect_board_pose')
        self.args = args
        self.camera_matrix = None
        self.distortion = None
        self.robot = None
        self.samples = []
        self.last_debug = None
        handeye_payload = json.loads(args.handeye_file.read_text(encoding='utf-8'))
        handeye = handeye_payload.get('camera_to_flange')
        if handeye is None:
            handeye = handeye_payload['best']['camera_to_flange']
        self.T_flange_camera = transform(
            np.asarray(handeye['rotation_matrix'], dtype=float),
            np.asarray(handeye['translation_m'], dtype=float),
        )
        self.create_subscription(CameraInfo, args.camera_info_topic, self.info_cb, qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState, args.robot_state_topic, self.robot_cb, 10)
        self.create_subscription(CompressedImage, args.image_topic, self.image_cb, qos_profile_sensor_data)
        self.get_logger().info('DRY RUN: detecting physical board 139x110 mm; no robot motion')

    def info_cb(self, message):
        self.camera_matrix = np.asarray(message.k, dtype=float).reshape(3, 3)
        self.distortion = np.asarray(message.d, dtype=float)

    def robot_cb(self, message):
        self.robot = message

    def image_cb(self, message):
        if self.camera_matrix is None or self.robot is None or len(self.samples) >= self.args.frames:
            return
        frame = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(gray, self.args.dark_threshold, 255, cv2.THRESH_BINARY_INV)[1]
        kernel = np.ones((self.args.close_kernel, self.args.close_kernel), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = frame.shape[0] * frame.shape[1]
        candidates = [c for c in contours if cv2.contourArea(c) >= image_area * self.args.min_area_fraction]
        if not candidates:
            return
        contour = max(candidates, key=cv2.contourArea)
        rect = cv2.minAreaRect(contour)
        width_px, height_px = rect[1]
        if min(width_px, height_px) <= 0:
            return
        ratio = max(width_px, height_px) / min(width_px, height_px)
        expected_ratio = self.args.board_width_mm / self.args.board_height_mm
        if abs(ratio - expected_ratio) > self.args.ratio_tolerance:
            return
        image_points = ordered_box(cv2.boxPoints(rect))
        half_x = self.args.board_width_mm / 2000.0
        half_y = self.args.board_height_mm / 2000.0
        object_points = np.asarray([
            [-half_x, -half_y, 0.0], [half_x, -half_y, 0.0],
            [half_x, half_y, 0.0], [-half_x, half_y, 0.0],
        ], dtype=np.float32)
        ok, rvec, tvec = cv2.solvePnP(
            object_points, image_points, self.camera_matrix, self.distortion,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok or float(np.asarray(tvec).reshape(3)[2]) <= 0:
            return
        projected, _ = cv2.projectPoints(object_points, rvec, tvec, self.camera_matrix, self.distortion)
        reprojection = float(np.sqrt(np.mean(np.sum((projected.reshape(-1, 2) - image_points) ** 2, axis=1))))
        if reprojection > self.args.max_reprojection_px:
            return
        R_camera_board, _ = cv2.Rodrigues(rvec)
        T_camera_board = transform(R_camera_board, np.asarray(tvec).reshape(3))
        state = self.robot
        R_base_flange = Rotation.from_euler(
            'xyz', [state.flange_a_cur_pos, state.flange_b_cur_pos, state.flange_c_cur_pos], degrees=True
        ).as_matrix()
        T_base_flange = transform(R_base_flange, np.asarray([
            state.flange_x_cur_pos, state.flange_y_cur_pos, state.flange_z_cur_pos
        ], dtype=float) / 1000.0)
        T_base_board = T_base_flange @ self.T_flange_camera @ T_camera_board
        self.samples.append({
            'camera_xyz_m': T_camera_board[:3, 3].copy(),
            'base_xyz_m': T_base_board[:3, 3].copy(),
            'T_camera_board': T_camera_board.copy(),
            'T_base_board': T_base_board.copy(),
            'reprojection_px': reprojection,
            'image_points': image_points.copy(),
        })
        annotated = frame.copy()
        cv2.polylines(annotated, [image_points.astype(int)], True, (0, 255, 0), 4)
        center = np.mean(image_points, axis=0).astype(int)
        cv2.drawMarker(annotated, tuple(center), (0, 0, 255), cv2.MARKER_CROSS, 30, 3)
        cv2.putText(annotated, f'board {len(self.samples)}/{self.args.frames} reproj={reprojection:.2f}px',
                    (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        self.last_debug = annotated
        if len(self.samples) in (1, 5, 10, 20, self.args.frames):
            self.get_logger().info(f'Stable board frames: {len(self.samples)}/{self.args.frames}')
        if len(self.samples) >= self.args.frames:
            self.finish()

    def finish(self):
        camera = np.asarray([sample['camera_xyz_m'] for sample in self.samples])
        base = np.asarray([sample['base_xyz_m'] for sample in self.samples])
        reprojection = np.asarray([sample['reprojection_px'] for sample in self.samples])
        reference = self.samples[len(self.samples) // 2]
        result = {
            'schema_version': 1,
            'timestamp_unix': time.time(),
            'dry_run': True,
            'robot_motion_sent': False,
            'board_size_mm': [self.args.board_width_mm, self.args.board_height_mm],
            'orientation_status': 'provisional; outer rectangle has a 180-degree ambiguity',
            'camera_center_mm_median': (np.median(camera, axis=0) * 1000.0).tolist(),
            'base_center_mm_median': (np.median(base, axis=0) * 1000.0).tolist(),
            'base_center_std_mm': (np.std(base, axis=0) * 1000.0).tolist(),
            'reprojection_px_median': float(np.median(reprojection)),
            'T_camera_board_reference': reference['T_camera_board'].tolist(),
            'T_base_board_reference': reference['T_base_board'].tolist(),
            'transform_chain': 'T_base_board=T_base_flange@T_flange_camera@T_camera_board',
        }
        self.args.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.args.output_file.write_text(json.dumps(result, indent=2), encoding='utf-8')
        self.args.debug_image.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.args.debug_image), self.last_debug)
        print('\nEMPTY BOARD POSE DRY RUN - ROBOT DID NOT MOVE')
        print('Board size [mm]:', [self.args.board_width_mm, self.args.board_height_mm])
        print('Board center in Camera [mm]:', np.round(np.median(camera, axis=0) * 1000.0, 3).tolist())
        print('Board center in Base [mm]:', np.round(np.median(base, axis=0) * 1000.0, 3).tolist())
        print('Frame repeatability std [mm]:', np.round(np.std(base, axis=0) * 1000.0, 3).tolist())
        print(f'Reprojection median [px]: {np.median(reprojection):.3f}')
        print('WARNING: board orientation is provisional until asymmetric gold-pad direction is validated.')
        print('Output:', self.args.output_file)
        print('Debug:', self.args.debug_image)
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--board-width-mm', type=float, default=139.0)
    parser.add_argument('--board-height-mm', type=float, default=110.0)
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--dark-threshold', type=int, default=70)
    parser.add_argument('--close-kernel', type=int, default=11)
    parser.add_argument('--min-area-fraction', type=float, default=0.15)
    parser.add_argument('--ratio-tolerance', type=float, default=0.12)
    parser.add_argument('--max-reprojection-px', type=float, default=5.0)
    parser.add_argument('--image-topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--camera-info-topic', default='/camera/camera/color/camera_info')
    parser.add_argument('--robot-state-topic', default='/nonrt_state_data')
    project_root = Path(__file__).resolve().parents[2]
    parser.add_argument('--handeye-file', type=Path, default=project_root / 'calibration/data/handeye_result.json')
    parser.add_argument('--output-file', type=Path, default=project_root / 'vision_assembly/data/board_pose_last.json')
    parser.add_argument('--debug-image', type=Path, default=project_root / 'vision_assembly/data/board_pose_debug.jpg')
    args = parser.parse_args()
    if args.frames < 5:
        parser.error('--frames must be at least 5')
    rclpy.init()
    node = BoardDetector(args)
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
