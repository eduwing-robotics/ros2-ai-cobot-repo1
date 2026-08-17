#!/usr/bin/env python3
"""Detect one small part in a ChArUco board cell without moving the robot."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage, Image

from charuco_common import detect_charuco, detector_parameters, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_DIR = PROJECT_ROOT / 'calibration'


COLOR_PROFILES = {
    # OpenCV HSV: H=0..179, S/V=0..255. The light profile intentionally
    # includes white and lightly tinted 3-D printed parts.
    'light': {'h': (0, 179), 's': (0, 105), 'v': (80, 255)},
    'orange': {'h': (4, 32), 's': (65, 255), 'v': (60, 255)},
    'brown': {'h': (3, 35), 's': (35, 255), 'v': (25, 190)},
}


def transform(rotation, translation):
    value = np.eye(4, dtype=float)
    value[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    value[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return value


class SmallPartDetector(Node):
    def __init__(self, args):
        super().__init__('detect_small_part_dry_run')
        self.args = args
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        result = json.loads(args.result_file.read_text(encoding='utf-8'))['best']
        self.euler_convention = result['euler_convention']
        handeye = result['camera_to_flange']
        self.T_flange_camera = transform(
            handeye['rotation_matrix'], handeye['translation_m']
        )
        self.K = None
        self.D = None
        self.depth = None
        self.depth_stamp = None
        self.robot = None
        self.samples = []
        self.locked_cell = None
        self.finished = False
        self.last_status = time.monotonic()
        self.last_reason = 'waiting for data'
        self.warp_square_px = int(args.square_pixels)
        self.board_width_px = int(self.config['squares_x']) * self.warp_square_px
        self.board_height_px = int(self.config['squares_y']) * self.warp_square_px

        self.create_subscription(
            CameraInfo, self.config['camera_info_topic'], self.info_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Image, args.depth_topic, self.depth_cb, qos_profile_sensor_data
        )
        self.create_subscription(
            CompressedImage, self.config['image_topic'], self.color_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            RobotNonrtState, self.config['robot_state_topic'], self.robot_cb, 10
        )
        self.create_timer(2.0, self.status_cb)
        self.get_logger().info(
            f'DRY RUN: '
            f'{"all black cells" if args.scan_all_black_cells else f"cell column={args.cell_col}, row={args.cell_row}"}, '
            f'part={args.part_length_mm:g}x{args.part_width_mm:g}x'
            f'{args.part_height_mm:g} mm; no robot motion'
        )

    @staticmethod
    def stamp(message):
        return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9

    def info_cb(self, message):
        self.K = np.asarray(message.k, dtype=float).reshape(3, 3)
        self.D = np.asarray(message.d, dtype=float)

    def robot_cb(self, message):
        self.robot = message

    def depth_cb(self, message):
        depth = self.bridge.imgmsg_to_cv2(message, 'passthrough').astype(np.float32)
        self.depth = depth * 0.001 if message.encoding in ('16UC1', 'mono16') else depth
        self.depth_stamp = self.stamp(message)

    def status_cb(self):
        if len(self.samples) < self.args.frames:
            self.get_logger().warning(
                f'Waiting: {self.last_reason}; valid frames '
                f'{len(self.samples)}/{self.args.frames}'
            )

    def color_cb(self, message):
        if self.finished:
            return
        if self.K is None or self.robot is None:
            self.last_reason = 'CameraInfo or robot state'
            return
        frame = self.bridge.compressed_imgmsg_to_cv2(message, 'bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, marker_ids, corners, corner_ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters, self.K, self.D
        )
        if corner_ids is None or len(corner_ids) < self.args.min_corners:
            self.last_reason = (
                f'ChArUco corners {0 if corner_ids is None else len(corner_ids)}'
            )
            return
        valid, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            corners, corner_ids, self.board, self.K, self.D, None, None
        )
        if not valid:
            self.last_reason = 'board pose'
            return

        square_m = float(self.config['square_length_m'])
        # Rectify from all observed sub-pixel ChArUco corners instead of four
        # PnP-projected outer corners. This reduces local XY bias, especially
        # for small parts placed diagonally or near a cell edge.
        observed_ids = np.asarray(corner_ids, dtype=np.int32).reshape(-1)
        observed_image = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
        observed_undistorted = cv2.undistortPoints(
            observed_image.reshape(-1, 1, 2), self.K, self.D, P=self.K
        ).reshape(-1, 2)
        if hasattr(self.board, 'getChessboardCorners'):
            all_chessboard_points = self.board.getChessboardCorners()
        else:
            all_chessboard_points = self.board.chessboardCorners
        chessboard_points = np.asarray(
            all_chessboard_points, dtype=np.float32
        )[observed_ids, :2]
        destination = chessboard_points * (self.warp_square_px / square_m)
        H, homography_mask = cv2.findHomography(
            observed_undistorted, destination, method=0
        )
        if H is None:
            self.last_reason = 'multi-corner board homography'
            return
        undistorted_frame = cv2.undistort(frame, self.K, self.D)
        top = cv2.warpPerspective(
            undistorted_frame, H, (self.board_width_px, self.board_height_px)
        )

        expected_area = (
            self.args.part_length_mm * self.args.part_width_mm
            * (self.warp_square_px / (square_m * 1000.0)) ** 2
        )
        if self.args.scan_all_black_cells:
            cells = [
                (col, row)
                for row in range(int(self.config['squares_y']))
                for col in range(int(self.config['squares_x']))
                if (col + row) % 2 == 0
            ]
        else:
            cells = [(self.args.cell_col, self.args.cell_row)]

        margin = max(4, int(round(self.warp_square_px * self.args.roi_margin)))
        candidates = []
        debug_cells = []
        for cell_col, cell_row in cells:
            x0_cell = cell_col * self.warp_square_px + margin
            y0_cell = cell_row * self.warp_square_px + margin
            x1_cell = (cell_col + 1) * self.warp_square_px - margin
            y1_cell = (cell_row + 1) * self.warp_square_px - margin
            roi_cell = top[y0_cell:y1_cell, x0_cell:x1_cell]
            roi_gray = cv2.cvtColor(roi_cell, cv2.COLOR_BGR2GRAY)
            roi_hsv = cv2.cvtColor(roi_cell, cv2.COLOR_BGR2HSV)
            background = float(np.percentile(roi_gray, 35))
            threshold = max(float(self.args.min_gray), background + self.args.gray_delta)
            mask_cell = (roi_gray >= threshold).astype(np.uint8) * 255
            if self.args.part_color != 'any':
                profile = COLOR_PROFILES[self.args.part_color]
                color_mask = cv2.inRange(
                    roi_hsv,
                    np.asarray([profile['h'][0], profile['s'][0], profile['v'][0]], dtype=np.uint8),
                    np.asarray([profile['h'][1], profile['s'][1], profile['v'][1]], dtype=np.uint8),
                )
                mask_cell = cv2.bitwise_and(mask_cell, color_mask)
            mask_cell = cv2.morphologyEx(
                mask_cell, cv2.MORPH_CLOSE, np.ones((5, 5), dtype=np.uint8)
            )
            mask_cell = cv2.morphologyEx(
                mask_cell, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
            )
            debug_cells.append(
                (cell_col, cell_row, roi_cell, mask_cell, threshold)
            )
            contours, _ = cv2.findContours(
                mask_cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                area = cv2.contourArea(contour)
                if not (
                    self.args.min_area_ratio * expected_area
                    <= area <= self.args.max_area_ratio * expected_area
                ):
                    continue
                rect = cv2.minAreaRect(contour)
                width, height = rect[1]
                if min(width, height) >= 2.0:
                    candidates.append((
                        abs(area - expected_area), contour, rect, area,
                        cell_col, cell_row, x0_cell, y0_cell,
                        roi_cell, mask_cell, threshold,
                    ))
        if not candidates:
            self.last_reason = (
                f'part contour in {len(cells)} black cells '
                f'(expected area={expected_area:.0f}px)'
            )
            if not self.samples:
                _, _, roi, mask, _ = debug_cells[0]
                self.save_debug(top, roi, mask, None)
            return
        candidates.sort(key=lambda value: value[0])
        if self.locked_cell is not None:
            locked_candidates = [
                value for value in candidates
                if (value[4], value[5]) == self.locked_cell
            ]
            if locked_candidates:
                candidates = locked_candidates
            else:
                self.samples.clear()
                self.locked_cell = None
                self.last_reason = 'detected cell changed; restarting stability collection'
                return
        (
            _, contour, rect, area, cell_col, cell_row, x0, y0,
            roi, mask, threshold,
        ) = candidates[0]
        if self.locked_cell is None:
            self.locked_cell = (cell_col, cell_row)
        (cx, cy), (side_a, side_b), angle = rect
        contour_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, -1)
        selected_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[contour_mask > 0]
        median_hsv = np.median(selected_hsv, axis=0) if selected_hsv.size else np.full(3, np.nan)
        if side_a < side_b:
            side_a, side_b = side_b, side_a
            angle += 90.0
        angle = (angle + 180.0) % 180.0
        board_u = x0 + cx
        board_v = y0 + cy
        x_board_m = board_u / self.board_width_px * (
            int(self.config['squares_x']) * square_m
        )
        y_board_m = board_v / self.board_height_px * (
            int(self.config['squares_y']) * square_m
        )
        part_board = np.asarray([
            x_board_m, y_board_m, -self.args.part_height_mm / 1000.0, 1.0
        ])
        R_camera_board, _ = cv2.Rodrigues(rvec)
        T_camera_board = transform(R_camera_board, np.asarray(tvec).reshape(3))
        part_camera_registered = (T_camera_board @ part_board)[:3]

        state = self.robot
        T_base_flange = transform(
            Rotation.from_euler(
                self.euler_convention,
                [state.flange_a_cur_pos, state.flange_b_cur_pos,
                 state.flange_c_cur_pos], degrees=True,
            ).as_matrix(),
            np.asarray([
                state.flange_x_cur_pos, state.flange_y_cur_pos,
                state.flange_z_cur_pos,
            ]) / 1000.0,
        )
        T_base_camera = T_base_flange @ self.T_flange_camera
        part_base_registered = (
            T_base_camera @ np.r_[part_camera_registered, 1.0]
        )[:3]
        angle_rad = np.deg2rad(angle)
        long_axis_board = np.asarray([
            np.cos(angle_rad), np.sin(angle_rad), 0.0
        ])
        long_axis_base = (
            T_base_camera[:3, :3] @ R_camera_board @ long_axis_board
        )
        long_axis_base_angle_deg = float(np.degrees(np.arctan2(
            long_axis_base[1], long_axis_base[0]
        )))

        depth_m = np.nan
        depth_camera = np.full(3, np.nan)
        raw_point, _ = cv2.projectPoints(
            np.asarray([[x_board_m, y_board_m, 0.0]], dtype=np.float32),
            rvec, tvec, self.K, self.D,
        )
        raw_u, raw_v = raw_point.reshape(2)
        if (
            self.depth is not None and self.depth_stamp is not None
            and abs(self.stamp(message) - self.depth_stamp) <= self.args.depth_sync_sec
            and self.depth.shape == frame.shape[:2]
        ):
            u = int(round(raw_u)); v = int(round(raw_v))
            radius = max(2, int(round(min(side_a, side_b) * 0.20)))
            patch = self.depth[
                max(0, v-radius):min(self.depth.shape[0], v+radius+1),
                max(0, u-radius):min(self.depth.shape[1], u+radius+1),
            ]
            values = patch[np.isfinite(patch) & (patch > 0.05) & (patch < 1.5)]
            if values.size:
                depth_m = float(np.median(values))
                depth_camera = np.asarray([
                    (raw_u-self.K[0, 2])*depth_m/self.K[0, 0],
                    (raw_v-self.K[1, 2])*depth_m/self.K[1, 1], depth_m,
                ])

        mm_per_warp_px = square_m * 1000.0 / self.warp_square_px
        sample = {
            'center_board_mm': [x_board_m*1000.0, y_board_m*1000.0],
            'cell_col': int(cell_col),
            'cell_row': int(cell_row),
            'size_mm': [side_a*mm_per_warp_px, side_b*mm_per_warp_px],
            'angle_deg': angle,
            'base_angle_deg': long_axis_base_angle_deg,
            'area_px': area,
            'median_hsv': median_hsv,
            'camera_registered_mm': part_camera_registered*1000.0,
            'base_registered_mm': part_base_registered*1000.0,
            'depth_m': depth_m,
            'camera_depth_mm': depth_camera*1000.0,
        }
        self.samples.append(sample)
        self.last_reason = 'collecting stable detections'
        self.save_debug(top, roi, mask, rect)
        count = len(self.samples)
        if count == 1 or count % 5 == 0:
            self.get_logger().info(f'Stable part frames: {count}/{self.args.frames}')
        if count >= self.args.frames:
            self.finished = True
            self.report()
            rclpy.shutdown()

    def save_debug(self, top, roi, mask, rect):
        annotated = roi.copy()
        if rect is not None:
            box = np.int32(np.round(cv2.boxPoints(rect)))
            cv2.drawContours(annotated, [box], 0, (0, 255, 0), 2)
            cv2.circle(annotated, tuple(np.int32(np.round(rect[0]))), 4, (0, 0, 255), -1)
        self.args.output_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.args.output_dir / 'small_part_board_top.jpg'), top)
        cv2.imwrite(str(self.args.output_dir / 'small_part_roi.jpg'), annotated)
        cv2.imwrite(str(self.args.output_dir / 'small_part_mask.png'), mask)

    def report(self):
        centers = np.asarray([s['center_board_mm'] for s in self.samples])
        cells = [(s['cell_col'], s['cell_row']) for s in self.samples]
        sizes = np.asarray([s['size_mm'] for s in self.samples])
        angles = np.asarray([s['angle_deg'] for s in self.samples])
        base_angles = np.asarray([s['base_angle_deg'] for s in self.samples])
        hsv_values = np.asarray([s['median_hsv'] for s in self.samples])
        cameras = np.asarray([s['camera_registered_mm'] for s in self.samples])
        bases = np.asarray([s['base_registered_mm'] for s in self.samples])
        valid_depth = np.asarray([
            s['camera_depth_mm'] for s in self.samples if np.isfinite(s['depth_m'])
        ])
        print('\nSMALL PART RGB-D DRY RUN - ROBOT DID NOT MOVE')
        unique_cells = sorted(set(cells))
        print('Detected black cell(s) [column,row]:', unique_cells)
        print('Board XY median [mm]:', np.round(np.median(centers, axis=0), 3).tolist())
        print('Contour long/short median [mm]:', np.round(np.median(sizes, axis=0), 3).tolist())
        print(f'Long-axis angle median [deg, board]: {np.median(angles):.2f}')
        base_angle_median = float(np.degrees(np.arctan2(
            np.median(np.sin(np.deg2rad(base_angles))),
            np.median(np.cos(np.deg2rad(base_angles))),
        )))
        print(f'Long-axis angle median [deg, base XY]: {base_angle_median:.2f}')
        median_hsv = np.median(hsv_values, axis=0)
        print(f'Color profile / median HSV: {self.args.part_color} / {np.round(median_hsv, 1).tolist()}')
        print('Registered Camera XYZ [mm]:', np.round(np.median(cameras, axis=0), 3).tolist())
        print('Registered Base XYZ [mm]:', np.round(np.median(bases, axis=0), 3).tolist())
        if valid_depth.size:
            print('Depth Camera XYZ median [mm]:', np.round(np.median(valid_depth, axis=0), 3).tolist())
        else:
            print('Depth Camera XYZ: invalid (RGB registered height remains available)')
        jitter = np.linalg.norm(bases - np.median(bases, axis=0), axis=1)
        print(f'Base jitter median/max [mm]: {np.median(jitter):.3f}/{np.max(jitter):.3f}')
        if float(np.max(jitter)) > self.args.max_base_jitter_mm:
            print(
                f'REJECTED: Base jitter max {np.max(jitter):.3f} mm exceeds '
                f'{self.args.max_base_jitter_mm:.3f} mm; target JSON was not updated.'
            )
            return
        result = {
            'timestamp_unix': time.time(),
            'mode': 'dry_run_no_robot_motion',
            'detected_cell_col_row': list(unique_cells[0]),
            'part_size_input_mm': [
                self.args.part_length_mm,
                self.args.part_width_mm,
                self.args.part_height_mm,
            ],
            'part_center_board_mm': np.median(centers, axis=0).tolist(),
            'part_center_camera_mm': np.median(cameras, axis=0).tolist(),
            'part_center_base_mm': np.median(bases, axis=0).tolist(),
            'contour_long_short_mm': np.median(sizes, axis=0).tolist(),
            'long_axis_angle_board_deg': float(np.median(angles)),
            'long_axis_angle_base_deg': base_angle_median,
            'part_color_profile': self.args.part_color,
            'median_hsv': median_hsv.tolist(),
            'base_jitter_median_mm': float(np.median(jitter)),
            'base_jitter_max_mm': float(np.max(jitter)),
            'frames': len(self.samples),
        }
        self.args.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.args.output_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        print(f'Latest target JSON: {self.args.output_file}')
        print(f'Debug images: {self.args.output_dir}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cell-col', type=int, default=2)
    parser.add_argument('--cell-row', type=int, default=2)
    parser.add_argument(
        '--scan-all-black-cells', action=argparse.BooleanOptionalAction,
        default=True,
        help='Search every black ChArUco square (default); use --no-scan-all-black-cells for one cell.',
    )
    parser.add_argument('--part-length-mm', type=float, default=6.0)
    parser.add_argument('--part-width-mm', type=float, default=3.5)
    parser.add_argument('--part-height-mm', type=float, default=2.5)
    parser.add_argument(
        '--part-color', choices=('light', 'orange', 'brown', 'any'),
        default='light',
        help='HSV color profile combined with size/shape detection (default: light).',
    )
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--min-corners', type=int, default=12)
    parser.add_argument('--square-pixels', type=int, default=240)
    parser.add_argument(
        '--roi-margin', type=float, default=0.03,
        help='Fraction excluded at each black-cell edge (default 0.03).',
    )
    parser.add_argument('--min-gray', type=float, default=55.0)
    parser.add_argument('--gray-delta', type=float, default=24.0)
    parser.add_argument('--min-area-ratio', type=float, default=0.20)
    parser.add_argument('--max-area-ratio', type=float, default=3.0)
    parser.add_argument('--depth-sync-sec', type=float, default=0.20)
    parser.add_argument('--max-base-jitter-mm', type=float, default=0.5)
    parser.add_argument(
        '--depth-topic', default='/camera/camera/aligned_depth_to_color/image_raw'
    )
    parser.add_argument(
        '--result-file', type=Path,
        default=CALIBRATION_DIR / 'data/handeye_result.json'
    )
    parser.add_argument(
        '--output-dir', type=Path,
        default=CALIBRATION_DIR / 'data/small_part_debug'
    )
    parser.add_argument(
        '--output-file', type=Path,
        default=CALIBRATION_DIR / 'data/small_part_last.json'
    )
    args = parser.parse_args()
    config, _, _ = load_config()
    if not 0 <= args.cell_col < int(config['squares_x']):
        parser.error('--cell-col is outside the board')
    if not 0 <= args.cell_row < int(config['squares_y']):
        parser.error('--cell-row is outside the board')
    rclpy.init()
    node = SmallPartDetector(args)
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
