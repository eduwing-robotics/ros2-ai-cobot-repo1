#!/usr/bin/env python3
"""Detect one profile-sized part in the gripper camera without ChArUco."""

import argparse
import hashlib
import json
import math
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_DIR = PROJECT_ROOT / 'calibration'


COLOR_PROFILES = {
    'light': {'h': (0, 179), 's': (0, 105), 'v': (80, 255)},
    'orange': {'h': (4, 32), 's': (65, 255), 'v': (60, 255)},
    'brown': {'h': (3, 35), 's': (35, 255), 'v': (25, 190)},
}


def transform(rotation, translation):
    value = np.eye(4, dtype=float)
    value[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    value[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return value


def stamp(message):
    return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9


def signed_angle_xy_deg(dx, dy):
    return math.degrees(math.atan2(dy, dx))


def axis_angle_mean_deg(values):
    """Mean of an unoriented axis whose period is 180 degrees."""
    angles = np.deg2rad(np.asarray(values, dtype=float) * 2.0)
    value = 0.5 * math.degrees(math.atan2(np.mean(np.sin(angles)), np.mean(np.cos(angles))))
    return (value + 90.0) % 180.0 - 90.0


def axis_angle_delta_deg(value, reference):
    return (float(value) - float(reference) + 90.0) % 180.0 - 90.0


class SmallPartDetector(Node):
    def __init__(self, args):
        super().__init__('detect_small_part_dry_run')
        self.args = args
        self.bridge = CvBridge()
        result_bytes = args.result_file.read_bytes()
        result_payload = json.loads(result_bytes.decode('utf-8'))
        result = result_payload['best']
        self.handeye_warning = str(result_payload.get('warning', '')).strip()
        self.handeye_sha256 = hashlib.sha256(result_bytes).hexdigest()
        self.euler_convention = result['euler_convention']
        handeye = result['camera_to_flange']
        self.T_flange_camera = transform(
            handeye['rotation_matrix'], handeye['translation_m']
        )

        self.K = None
        self.camera_info_size = None
        self.depth = None
        self.depth_stamp = None
        self.robot = None
        self.robot_received_monotonic = None
        self.samples = []
        self.locked_cell = None
        self.locked_center_px = None
        self.finished = False
        self.target_written = False
        self.last_status = 'waiting for data'
        self.track_base_target_mm = None
        if args.track_base_target_file is not None:
            track_payload = json.loads(
                args.track_base_target_file.read_text(encoding='utf-8')
            )
            track_age = time.time() - float(track_payload['timestamp_unix'])
            if track_age < -5.0 or track_age > args.max_tracking_target_age_sec:
                raise RuntimeError(
                    f'tracking target is stale ({track_age:.1f} s)'
                )
            self.track_base_target_mm = np.asarray(
                track_payload['part_center_base_mm'], dtype=float
            ).reshape(3)
        if args.square_pixels is not None:
            self.get_logger().warning(
                '--square-pixels is kept for compatibility but is ignored in markerless mode.'
            )

        self.create_subscription(
            CameraInfo, args.camera_info_topic, self.info_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Image, args.depth_topic, self.depth_cb, qos_profile_sensor_data
        )
        self.create_subscription(
            CompressedImage, args.color_topic, self.color_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            RobotNonrtState, args.robot_state_topic, self.robot_cb, 10
        )
        self.create_timer(2.0, self.status_cb)

        self.get_logger().info(
            f'DRY RUN: {"scan whole image (markerless)" if args.scan_all_black_cells else f"fallback cell ({args.cell_col},{args.cell_row})"}'
            f', part={args.part_length_mm:g}x{args.part_width_mm:g}x'
            f'{args.part_height_mm:g} mm, shape={args.part_shape}, '
            f'segmentation={args.segmentation_mode}, '
            f'orientation={args.orientation_mode}, no robot motion'
        )

    def info_cb(self, message):
        self.K = np.asarray(message.k, dtype=float).reshape(3, 3)
        self.camera_info_size = (int(message.width), int(message.height))

    def robot_cb(self, message):
        self.robot = message
        self.robot_received_monotonic = time.monotonic()

    def depth_cb(self, message):
        depth = self.bridge.imgmsg_to_cv2(message, 'passthrough')
        if depth.dtype == np.uint16:
            self.depth = depth.astype(np.float32) * 0.001
        else:
            self.depth = depth.astype(np.float32)
        self.depth_stamp = stamp(message)

    def status_cb(self):
        if len(self.samples) < self.args.frames:
            self.get_logger().warning(
                f'Waiting: {self.last_status}; valid frames '
                f'{len(self.samples)}/{self.args.frames}'
            )

    @staticmethod
    def _depth_patch(depth, u, v, radius):
        u0 = int(round(u))
        v0 = int(round(v))
        r = int(max(1, radius))
        h, w = depth.shape
        x0 = max(0, u0 - r)
        y0 = max(0, v0 - r)
        x1 = min(w, u0 + r + 1)
        y1 = min(h, v0 + r + 1)
        return depth[y0:y1, x0:x1]

    @staticmethod
    def _valid_depth(depth):
        return np.isfinite(depth) & (depth > 0.05) & (depth < 1.5)

    def _sample_depth_geometry(
        self, contour, foreground_mask, x0, y0, x1, y1, cx, cy,
        base_t_camera,
    ):
        """Measure the component top and fit its surrounding support plane."""
        depth_roi = self.depth[y0:y1, x0:x1]
        if depth_roi.shape != foreground_mask.shape:
            return None

        object_mask = np.zeros(foreground_mask.shape, dtype=np.uint8)
        cv2.drawContours(object_mask, [contour], -1, 255, -1)
        core = cv2.erode(object_mask, np.ones((3, 3), np.uint8), iterations=1)
        if cv2.countNonZero(core) < self.args.min_depth_pixels:
            core = object_mask
        valid = self._valid_depth(depth_roi)
        top_values = depth_roi[(core > 0) & valid]
        core_pixels = max(cv2.countNonZero(core), 1)
        top_valid_fraction = float(top_values.size / core_pixels)
        if (
            top_values.size < self.args.min_depth_pixels
            or top_valid_fraction < self.args.min_depth_valid_fraction
        ):
            return None

        top_depth_m = float(np.median(top_values))
        top_mad_mm = float(
            np.median(np.abs(top_values - top_depth_m)) * 1000.0
        )
        if top_mad_mm > self.args.max_depth_mad_mm:
            return None

        outer_kernel = np.ones(
            (2 * self.args.support_ring_outer_px + 1,) * 2, np.uint8
        )
        inner_kernel = np.ones(
            (2 * self.args.support_ring_inner_px + 1,) * 2, np.uint8
        )
        outer = cv2.dilate(object_mask, outer_kernel, iterations=1)
        inner = cv2.dilate(object_mask, inner_kernel, iterations=1)
        ring = (outer > 0) & (inner == 0) & (foreground_mask == 0) & valid
        ys, xs = np.nonzero(ring)
        if xs.size < self.args.min_support_depth_pixels:
            return None
        support_values = depth_roi[ys, xs].astype(float)
        design = np.column_stack([
            xs.astype(float) - (cx - x0),
            ys.astype(float) - (cy - y0),
            np.ones(xs.size, dtype=float),
        ])
        keep = np.ones(xs.size, dtype=bool)
        coeff = None
        for _ in range(3):
            if np.count_nonzero(keep) < self.args.min_support_depth_pixels:
                return None
            coeff, _, _, _ = np.linalg.lstsq(
                design[keep], support_values[keep], rcond=None
            )
            residual = support_values - design @ coeff
            residual_median = float(np.median(residual[keep]))
            residual_mad = float(
                np.median(np.abs(residual[keep] - residual_median))
            )
            threshold_m = max(0.0015, 3.5 * residual_mad)
            keep = np.abs(residual - residual_median) <= threshold_m
        if np.count_nonzero(keep) < self.args.min_support_depth_pixels:
            return None
        coeff, _, _, _ = np.linalg.lstsq(
            design[keep], support_values[keep], rcond=None
        )
        support_depth_m = float(coeff[2])
        support_residual = support_values[keep] - design[keep] @ coeff
        support_mad_mm = float(
            np.median(np.abs(support_residual - np.median(support_residual)))
            * 1000.0
        )
        if support_mad_mm > self.args.max_support_plane_mad_mm:
            return None

        top_camera = self._pixel_to_camera(cx, cy, top_depth_m)
        support_camera = self._pixel_to_camera(cx, cy, support_depth_m)
        top_base = (base_t_camera @ np.r_[top_camera, 1.0])[:3] * 1000.0
        support_base = (
            base_t_camera @ np.r_[support_camera, 1.0]
        )[:3] * 1000.0
        observed_height_mm = float(top_base[2] - support_base[2])
        if (
            observed_height_mm < self.args.min_observed_height_mm
            or abs(observed_height_mm - self.args.part_height_mm)
            > self.args.height_tolerance_mm
        ):
            return None
        return {
            'top_depth_m': top_depth_m,
            'top_valid_fraction': top_valid_fraction,
            'top_mad_mm': top_mad_mm,
            'support_depth_m': support_depth_m,
            'support_plane_mad_mm': support_mad_mm,
            'support_depth_pixels': int(np.count_nonzero(keep)),
            'observed_height_mm': observed_height_mm,
            'top_camera_mm': (top_camera * 1000.0).tolist(),
            'top_base_mm': top_base.tolist(),
            'support_base_z_mm': float(support_base[2]),
        }

    @staticmethod
    def _expected_area_px(length_mm, width_mm, depth_m, fx, fy, shape='rectangle'):
        expected_area_mm2 = float(length_mm) * float(width_mm)
        if shape == 'circle':
            expected_area_mm2 *= math.pi / 4.0
        return expected_area_mm2 * fx * fy / (depth_m ** 2 * 1_000_000.0)

    def _camera_pose_base(self):
        state = self.robot
        if state is None:
            return None
        base_r_flange = Rotation.from_euler(
            self.euler_convention,
            [state.flange_a_cur_pos, state.flange_b_cur_pos, state.flange_c_cur_pos],
            degrees=True,
        ).as_matrix()
        base_t_flange = transform(
            base_r_flange,
            np.asarray([
                state.flange_x_cur_pos,
                state.flange_y_cur_pos,
                state.flange_z_cur_pos,
            ], dtype=float) / 1000.0,
        )
        return base_t_flange @ self.T_flange_camera

    def _build_depth_mask(self, depth):
        """Segment surfaces raised from a robust image-space support plane."""
        valid = self._valid_depth(depth)
        ys, xs = np.nonzero(valid)
        minimum_samples = max(200, self.args.min_support_depth_pixels * 4)
        if xs.size < minimum_samples:
            return np.zeros(depth.shape, dtype=np.uint8)

        # Keep the fit bounded on full-resolution frames without changing its
        # spatial coverage. Raised parts are removed as negative residual
        # outliers during the robust iterations below.
        stride = max(1, int(math.ceil(xs.size / 50000.0)))
        xs_fit = xs[::stride].astype(float)
        ys_fit = ys[::stride].astype(float)
        values = depth[ys[::stride], xs[::stride]].astype(float)
        center_x = 0.5 * (depth.shape[1] - 1)
        center_y = 0.5 * (depth.shape[0] - 1)
        design = np.column_stack([
            xs_fit - center_x,
            ys_fit - center_y,
            np.ones(xs_fit.size, dtype=float),
        ])
        keep = np.ones(xs_fit.size, dtype=bool)
        coeff = None
        for _ in range(4):
            if np.count_nonzero(keep) < minimum_samples:
                return np.zeros(depth.shape, dtype=np.uint8)
            coeff, _, _, _ = np.linalg.lstsq(
                design[keep], values[keep], rcond=None
            )
            residual = values - design @ coeff
            residual_center = float(np.median(residual[keep]))
            residual_mad = float(
                np.median(np.abs(residual[keep] - residual_center))
            )
            threshold_m = max(0.0015, 4.0 * 1.4826 * residual_mad)
            keep = np.abs(residual - residual_center) <= threshold_m
        if coeff is None or np.count_nonzero(keep) < minimum_samples:
            return np.zeros(depth.shape, dtype=np.uint8)
        coeff, _, _, _ = np.linalg.lstsq(
            design[keep], values[keep], rcond=None
        )

        grid_y, grid_x = np.indices(depth.shape, dtype=float)
        support = (
            coeff[0] * (grid_x - center_x)
            + coeff[1] * (grid_y - center_y)
            + coeff[2]
        )
        height_mm = (support - depth.astype(float)) * 1000.0
        minimum_height_mm = max(
            self.args.min_observed_height_mm,
            self.args.part_height_mm * self.args.depth_mask_height_fraction,
        )
        maximum_height_mm = (
            self.args.part_height_mm + 2.0 * self.args.height_tolerance_mm
        )
        mask = (
            valid
            & (height_mm >= minimum_height_mm)
            & (height_mm <= maximum_height_mm)
        ).astype(np.uint8) * 255
        return cv2.morphologyEx(
            cv2.morphologyEx(
                mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
            ),
            cv2.MORPH_CLOSE, np.ones((5, 5), dtype=np.uint8),
        )

    def _build_mask(self, frame, depth=None):
        if self.args.segmentation_mode == 'depth':
            if depth is None or depth.shape != frame.shape[:2]:
                return np.zeros(frame.shape[:2], dtype=np.uint8)
            return self._build_depth_mask(depth)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.args.segmentation_mode == 'dark':
            background = float(np.percentile(gray, 65))
            threshold = min(
                float(self.args.max_gray),
                background - self.args.dark_gray_delta,
            )
            mask = (gray <= threshold).astype(np.uint8) * 255
        else:
            background = float(np.percentile(gray, 35))
            threshold = max(
                float(self.args.min_gray), background + self.args.gray_delta
            )
            mask = (gray >= threshold).astype(np.uint8) * 255
        if self.args.part_color != 'any':
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            profile = COLOR_PROFILES[self.args.part_color]
            color_mask = cv2.inRange(
                hsv,
                np.asarray([profile['h'][0], profile['s'][0], profile['v'][0]], dtype=np.uint8),
                np.asarray([profile['h'][1], profile['s'][1], profile['v'][1]], dtype=np.uint8),
            )
            # Saturated orange/brown parts can be darker than a white support
            # surface, so their HSV mask is the appearance source. The light
            # profile still needs the adaptive bright foreground gate.
            if (
                self.args.segmentation_mode == 'bright'
                and self.args.part_color in ('orange', 'brown')
            ):
                mask = color_mask
            else:
                mask = cv2.bitwise_and(mask, color_mask)
        return cv2.morphologyEx(
            cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), dtype=np.uint8)),
            cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8),
        )

    def _roi_cells(self, frame):
        h, w = frame.shape[:2]
        if self.args.scan_all_black_cells:
            return [(0, 0, 0, 0, w, h)]
        rows = self.args.fallback_grid_rows
        cols = self.args.fallback_grid_cols
        col = max(0, min(int(self.args.cell_col), max(cols - 1, 0)))
        row = max(0, min(int(self.args.cell_row), max(rows - 1, 0)))
        cell_w = w / max(cols, 1)
        cell_h = h / max(rows, 1)
        margin = int(round(min(cell_w, cell_h) * self.args.roi_margin))
        margin = max(4, margin)
        x0 = int(col * cell_w) + margin
        y0 = int(row * cell_h) + margin
        x1 = int((col + 1) * cell_w) - margin
        y1 = int((row + 1) * cell_h) - margin
        x0 = max(0, min(w - 1, x0))
        y0 = max(0, min(h - 1, y0))
        x1 = max(x0 + 1, min(w, x1))
        y1 = max(y0 + 1, min(h, y1))
        return [(col, row, x0, y0, x1, y1)]

    def _pixel_to_camera(self, u, v, depth_m):
        if not np.isfinite(depth_m) or self.K is None:
            return np.array([np.nan, np.nan, np.nan])
        x = (u - self.K[0, 2]) * depth_m / self.K[0, 0]
        y = (v - self.K[1, 2]) * depth_m / self.K[1, 1]
        return np.array([x, y, depth_m], dtype=float)

    def _long_axis_base_deg(self, rect, depth_m, base_t_camera):
        (u, v), (side_a, side_b), angle = rect
        if side_a >= side_b:
            long_px, short_px, long_angle = float(side_a), float(side_b), float(angle)
        else:
            long_px, short_px, long_angle = float(side_b), float(side_a), float(angle) + 90.0
        long_angle = ((long_angle + 90.0) % 180.0) - 90.0
        half = max(1.0, long_px * 0.5)
        rad = math.radians(long_angle)
        u1, v1 = u - half * math.cos(rad), v - half * math.sin(rad)
        u2, v2 = u + half * math.cos(rad), v + half * math.sin(rad)
        p1 = self._pixel_to_camera(u1, v1, depth_m)
        p2 = self._pixel_to_camera(u2, v2, depth_m)
        axis_cam = p2 - p1
        if np.linalg.norm(axis_cam) < 1e-9:
            return long_angle, long_px * 0.0, short_px * 0.0, long_px * 0.0, np.array([np.nan, np.nan, np.nan])
        axis_base = base_t_camera[:3, :3] @ axis_cam
        base_deg = signed_angle_xy_deg(axis_base[0], axis_base[1])
        if base_deg > 180.0:
            base_deg -= 360.0
        elif base_deg < -180.0:
            base_deg += 360.0
        mm_per_px = 0.5 * (depth_m * 1000.0 / self.K[0, 0] + depth_m * 1000.0 / self.K[1, 1])
        return long_angle, long_px * mm_per_px, short_px * mm_per_px, long_px * mm_per_px * 1.0, axis_base

    def save_debug(self, frame, rect):
        if frame is None:
            return
        annotated = frame.copy()
        if rect is not None:
            box = np.int32(np.round(cv2.boxPoints(rect)))
            cv2.drawContours(annotated, [box], 0, (0, 255, 0), 2)
            cv2.circle(
                annotated,
                tuple(np.int32(np.round(rect[0]))),
                4, (0, 0, 255), -1,
            )
        self.args.output_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.args.output_dir / 'small_part_board_top.jpg'), frame)
        cv2.imwrite(str(self.args.output_dir / 'small_part_roi.jpg'), annotated)

    def report(self):
        centers_board = np.asarray([s['part_center_board_mm'] for s in self.samples], dtype=float)
        centers_camera = np.asarray([s['part_center_camera_mm'] for s in self.samples], dtype=float)
        centers_base = np.asarray([s['part_center_base_mm'] for s in self.samples], dtype=float)
        sizes = np.asarray([s['size_mm'] for s in self.samples], dtype=float)
        cells = [(s['cell_col'], s['cell_row']) for s in self.samples]

        if self.args.orientation_mode == 'long_axis':
            base_angles = np.asarray(
                [s['long_axis_angle_base_deg'] for s in self.samples],
                dtype=float,
            )
            angle_image = np.asarray(
                [s['long_axis_angle_board_deg'] for s in self.samples],
                dtype=float,
            )
            base_angle_median = axis_angle_mean_deg(base_angles)
            image_angle_median = axis_angle_mean_deg(angle_image)
            base_angle_jitter = float(np.max(np.abs([
                axis_angle_delta_deg(value, base_angle_median)
                for value in base_angles
            ])))
        else:
            base_angle_median = None
            image_angle_median = None
            base_angle_jitter = None
        jitter = np.linalg.norm(centers_base - np.median(centers_base, axis=0), axis=1)
        depths_mm = np.asarray([float(s['depth_m']) * 1000.0 for s in self.samples])
        depth_valid = np.asarray([float(s['depth_valid_fraction']) for s in self.samples])
        depth_mad = np.asarray([float(s['depth_mad_mm']) for s in self.samples])
        support_mad = np.asarray([float(s['support_plane_mad_mm']) for s in self.samples])
        observed_heights = np.asarray([float(s['observed_height_mm']) for s in self.samples])
        depth_jitter_mm = float(np.max(np.abs(depths_mm - np.median(depths_mm))))

        print('\nPROFILE-SIZED PART RGB-D DRY RUN (MARKERLESS) - ROBOT DID NOT MOVE')
        print('Detected cell(s) [column,row]:', sorted(set(cells)))
        print('Part center X/Y proxy [mm]:', np.round(np.median(centers_board, axis=0), 3).tolist())
        print('Part size long/short median [mm]:', np.round(np.median(sizes, axis=0), 3).tolist())
        if self.args.orientation_mode == 'long_axis':
            print(f'Long-axis angle mean [deg, image/axis]: {image_angle_median:.2f}')
            print(f'Long-axis angle median [deg, base XY]: {base_angle_median:.2f}')
            print(f'Base axis-angle jitter max [deg]: {base_angle_jitter:.2f}')
        else:
            print('Orientation: preserve current TCP orientation (axis-free part)')
        print('Center Camera XYZ median [mm]:', np.round(np.median(centers_camera, axis=0), 3).tolist())
        print('Center Base XYZ median [mm]:', np.round(np.median(centers_base, axis=0), 3).tolist())
        print(f'Base jitter median/max [mm]: {np.median(jitter):.3f}/{np.max(jitter):.3f}')
        print(f'Depth median [m]: {np.median([float(s["depth_m"]) for s in self.samples]):.3f}')
        print(f'Depth valid fraction min/median: {np.min(depth_valid):.3f}/{np.median(depth_valid):.3f}')
        print(f'Depth MAD median/max [mm]: {np.median(depth_mad):.3f}/{np.max(depth_mad):.3f}')
        print(f'Support-plane MAD max [mm]: {np.max(support_mad):.3f}')
        print(f'Observed part height median [mm]: {np.median(observed_heights):.3f}')
        print(f'Depth frame jitter max [mm]: {depth_jitter_mm:.3f}')
        if float(np.max(jitter)) > self.args.max_base_jitter_mm:
            print(
                f'REJECTED: Base jitter max {np.max(jitter):.3f} mm exceeds '
                f'{self.args.max_base_jitter_mm:.3f} mm; target JSON was not updated.'
            )
            return
        if np.min(depth_valid) < self.args.min_depth_valid_fraction:
            print('REJECTED: insufficient valid depth support; target JSON was not updated.')
            return
        if np.max(depth_mad) > self.args.max_depth_mad_mm:
            print('REJECTED: local depth noise exceeds limit; target JSON was not updated.')
            return
        if depth_jitter_mm > self.args.max_depth_jitter_mm:
            print('REJECTED: depth changes across frames exceed limit; target JSON was not updated.')
            return
        if (
            base_angle_jitter is not None
            and base_angle_jitter > self.args.max_angle_jitter_deg
        ):
            print('REJECTED: part-axis angle is unstable; target JSON was not updated.')
            return

        result = {
            'timestamp_unix': time.time(),
            'mode': 'dry_run_no_robot_motion',
            'detection_mode': 'markerless_rgbd',
            'part_profile_id': self.args.part_profile_id,
            'part_shape': self.args.part_shape,
            'segmentation_mode': self.args.segmentation_mode,
            'orientation_mode': self.args.orientation_mode,
            'orientation_valid': self.args.orientation_mode == 'long_axis',
            'detected_cell_col_row': list(sorted(set(cells))[0]),
            'part_size_input_mm': [
                self.args.part_length_mm,
                self.args.part_width_mm,
                self.args.part_height_mm,
            ],
            'part_center_board_mm': np.median(centers_board, axis=0).tolist(),
            'part_center_camera_mm': np.median(centers_camera, axis=0).tolist(),
            'part_center_base_mm': np.median(centers_base, axis=0).tolist(),
            'contour_long_short_mm': np.median(sizes, axis=0).tolist(),
            'long_axis_angle_board_deg': image_angle_median,
            'long_axis_angle_base_deg': base_angle_median,
            'long_axis_angle_jitter_max_deg': base_angle_jitter,
            'part_color_profile': self.args.part_color,
            'base_jitter_median_mm': float(np.median(jitter)),
            'base_jitter_max_mm': float(np.max(jitter)),
            'depth_quality': {
                'depth_median_mm': float(np.median(depths_mm)),
                'valid_fraction_min': float(np.min(depth_valid)),
                'valid_fraction_median': float(np.median(depth_valid)),
                'local_mad_median_mm': float(np.median(depth_mad)),
                'local_mad_max_mm': float(np.max(depth_mad)),
                'support_plane_mad_max_mm': float(np.max(support_mad)),
                'frame_jitter_max_mm': depth_jitter_mm,
                'observed_height_median_mm': float(np.median(observed_heights)),
                'observed_height_range_mm': [
                    float(np.min(observed_heights)), float(np.max(observed_heights)),
                ],
                'expected_height_mm': float(self.args.part_height_mm),
                'accepted': True,
            },
            'selection': {
                'reference': 'tracked_base_target' if self.track_base_target_mm is not None else 'image_center',
                'locked_center_px': np.median(
                    np.asarray([s['center_px'] for s in self.samples]), axis=0
                ).tolist(),
                'max_tracking_jump_px': float(self.args.max_tracking_jump_px),
            },
            'handeye': {
                'result_file': str(self.args.result_file.resolve()),
                'sha256': self.handeye_sha256,
                'warning': self.handeye_warning,
            },
            'frames': len(self.samples),
        }
        self.args.output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = self.args.output_file.with_suffix(
            self.args.output_file.suffix + '.tmp'
        )
        temporary_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        temporary_output.replace(self.args.output_file)
        self.target_written = True
        print(f'Latest target JSON: {self.args.output_file}')
        print(f'Debug images: {self.args.output_dir}')

    def color_cb(self, message):
        if self.finished:
            return
        if self.K is None or self.robot is None or self.depth is None:
            self.last_status = 'camera info / robot / depth'
            return
        frame = self.bridge.compressed_imgmsg_to_cv2(message, 'bgr8')
        frame_stamp = stamp(message)
        if self.depth_stamp is None or abs(frame_stamp - self.depth_stamp) > self.args.depth_sync_sec:
            self.last_status = 'depth not synchronized'
            return
        if self.camera_info_size != (frame.shape[1], frame.shape[0]):
            self.last_status = 'color frame and CameraInfo dimensions differ'
            return
        if (
            not np.all(np.isfinite(self.K))
            or self.K[0, 0] <= 0.0
            or self.K[1, 1] <= 0.0
        ):
            self.last_status = 'invalid CameraInfo intrinsics'
            return
        if self.depth.shape != frame.shape[:2]:
            self.last_status = 'aligned depth and color dimensions differ'
            return
        if (
            self.robot_received_monotonic is None
            or time.monotonic() - self.robot_received_monotonic
            > self.args.max_robot_state_age_sec
        ):
            self.last_status = 'robot state is stale'
            return
        if (
            int(self.robot.robot_motion_done) != 1
            or int(self.robot.emg) != 0
            or int(self.robot.main_error_code) != 0
            or float(self.robot.collision_err) != 0.0
        ):
            self.samples.clear()
            self.locked_center_px = None
            self.last_status = 'robot must be stationary and error-free during detection'
            return

        base_t_camera = self._camera_pose_base()
        if base_t_camera is None:
            self.last_status = 'robot pose unavailable'
            return

        reference_u = frame.shape[1] * self.args.target_center_u_norm
        reference_v = frame.shape[0] * self.args.target_center_v_norm
        reference_name = 'image center'
        if self.track_base_target_mm is not None:
            camera_t_base = np.linalg.inv(base_t_camera)
            tracked_camera = (
                camera_t_base @ np.r_[self.track_base_target_mm / 1000.0, 1.0]
            )[:3]
            if tracked_camera[2] <= 0.05:
                self.last_status = 'tracked Base target projects behind camera'
                return
            reference_u = self.K[0, 0] * tracked_camera[0] / tracked_camera[2] + self.K[0, 2]
            reference_v = self.K[1, 1] * tracked_camera[1] / tracked_camera[2] + self.K[1, 2]
            reference_name = 'tracked Base target projection'
            if not (0 <= reference_u < frame.shape[1] and 0 <= reference_v < frame.shape[0]):
                self.last_status = 'tracked Base target is outside camera image'
                return

        all_candidates = []
        for cell_col, cell_row, x0, y0, x1, y1 in self._roi_cells(frame):
            roi = frame[y0:y1, x0:x1]
            if roi.size == 0:
                continue
            depth_roi = self.depth[y0:y1, x0:x1]
            mask = self._build_mask(roi, depth_roi)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < 30.0:
                    continue
                rect = cv2.minAreaRect(contour)
                (u_roi, v_roi), (side_a, side_b), angle = rect
                if min(side_a, side_b) < 2.0:
                    continue
                cx = float(u_roi + x0)
                cy = float(v_roi + y0)
                center_distance_px = math.hypot(cx - reference_u, cy - reference_v)
                max_center_distance_px = (
                    self.args.max_target_center_distance_fraction
                    * min(frame.shape[:2])
                )
                if center_distance_px > max_center_distance_px:
                    continue
                geometry = self._sample_depth_geometry(
                    contour, mask, x0, y0, x1, y1, cx, cy,
                    base_t_camera,
                )
                if geometry is None:
                    continue
                depth_m = geometry['top_depth_m']
                expected_area_px = self._expected_area_px(
                    self.args.part_length_mm,
                    self.args.part_width_mm,
                    depth_m,
                    self.K[0, 0],
                    self.K[1, 1],
                    self.args.part_shape,
                )
                if not (self.args.min_area_ratio * expected_area_px <= area <= self.args.max_area_ratio * expected_area_px):
                    continue
                if self.args.part_shape == 'circle':
                    perimeter = cv2.arcLength(contour, True)
                    circularity = (
                        4.0 * math.pi * area / (perimeter * perimeter)
                        if perimeter > 1e-6 else 0.0
                    )
                    if circularity < self.args.min_circularity:
                        continue
                angle_board, _, __, ___, axis_base = self._long_axis_base_deg(
                    rect, depth_m, base_t_camera
                )
                long_px = max(side_a, side_b)
                short_px = min(side_a, side_b)
                mm_per_px = 0.5 * (depth_m * 1000.0 / self.K[0, 0] + depth_m * 1000.0 / self.K[1, 1])
                long_mm = long_px * mm_per_px
                short_mm = short_px * mm_per_px
                expected_long = max(self.args.part_length_mm, self.args.part_width_mm)
                expected_short = min(self.args.part_length_mm, self.args.part_width_mm)
                if not (self.args.min_size_ratio * expected_long <= long_mm <= self.args.max_size_ratio * expected_long):
                    continue
                if not (self.args.min_size_ratio * expected_short <= short_mm <= self.args.max_size_ratio * expected_short):
                    continue

                part_camera_mm = np.asarray(geometry['top_camera_mm'], dtype=float)
                part_base = np.asarray(geometry['top_base_mm'], dtype=float)
                area_error = abs(area - expected_area_px) / max(expected_area_px, 1.0)
                size_error = abs(math.log(long_mm / expected_long)) + abs(math.log(short_mm / expected_short))
                score = area_error + 0.5 * size_error + 0.25 * center_distance_px / max(max_center_distance_px, 1.0)
                all_candidates.append({
                    'score': score,
                    'cell_col': int(cell_col),
                    'cell_row': int(cell_row),
                    'part_center_board_mm': [float(part_camera_mm[0]), float(part_camera_mm[1])],
                    'part_center_camera_mm': part_camera_mm.tolist(),
                    'part_center_base_mm': part_base.tolist(),
                    'size_mm': [long_mm, short_mm],
                    'long_axis_angle_board_deg': float(angle_board),
                    'long_axis_angle_base_deg': float(np.nan if not np.isfinite(axis_base[0]) else (
                        signed_angle_xy_deg(axis_base[0], axis_base[1])
                    )),
                    'depth_m': float(depth_m),
                    'depth_valid_fraction': geometry['top_valid_fraction'],
                    'depth_mad_mm': geometry['top_mad_mm'],
                    'support_plane_mad_mm': geometry['support_plane_mad_mm'],
                    'support_depth_m': geometry['support_depth_m'],
                    'support_base_z_mm': geometry['support_base_z_mm'],
                    'observed_height_mm': geometry['observed_height_mm'],
                    'center_px': [cx, cy],
                    'center_distance_px': center_distance_px,
                    'rect': rect,
                })

        if not all_candidates:
            self.last_status = (
                f'no valid part near {reference_name}: expected area~{self.args.part_length_mm * self.args.part_width_mm:.1f} mm²'
            )
            return

        all_candidates.sort(key=lambda item: (item['center_distance_px'], item['score']))
        if self.locked_center_px is not None:
            tracked_candidates = sorted(
                all_candidates,
                key=lambda item: math.dist(item['center_px'], self.locked_center_px),
            )
            best = tracked_candidates[0]
            if math.dist(best['center_px'], self.locked_center_px) > self.args.max_tracking_jump_px:
                self.samples.clear()
                self.locked_center_px = None
                self.last_status = 'target jumped in image; restarting target lock'
                return
        else:
            if (
                len(all_candidates) > 1
                and all_candidates[1]['center_distance_px']
                - all_candidates[0]['center_distance_px']
                < self.args.min_selection_margin_px
            ):
                self.last_status = 'multiple equally close part candidates; center the intended part'
                return
            best = all_candidates[0]
        if self.locked_cell is not None and (
            self.locked_cell != (best['cell_col'], best['cell_row'])
        ):
            self.samples.clear()
            self.locked_cell = None
            self.locked_center_px = None
            self.last_status = 'detected cell changed; restart stability'
            return
        if self.locked_cell is None:
            self.locked_cell = (best['cell_col'], best['cell_row'])
            self.locked_center_px = best['center_px']
            self.last_status = 'locking search cell'
        else:
            self.locked_center_px = best['center_px']

        self.samples.append(best)
        self.save_debug(frame, best['rect'])
        self.last_status = 'collecting stable detections'
        count = len(self.samples)
        if count == 1 or count % 5 == 0:
            self.get_logger().info(f'Stable part frames: {count}/{self.args.frames}')
        if count >= self.args.frames:
            self.finished = True
            self.report()
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cell-col', type=int, default=2)
    parser.add_argument('--cell-row', type=int, default=2)
    parser.add_argument('--fallback-grid-cols', type=int, default=5)
    parser.add_argument('--fallback-grid-rows', type=int, default=7)
    parser.add_argument(
        '--scan-all-black-cells', action=argparse.BooleanOptionalAction,
        default=True,
        help='Search whole image (markerless fallback). Kept for wrapper compatibility.',
    )
    parser.add_argument('--part-length-mm', type=float, default=6.0)
    parser.add_argument('--part-width-mm', type=float, default=3.5)
    parser.add_argument('--part-height-mm', type=float, default=2.5)
    parser.add_argument('--part-profile-id', default='custom')
    parser.add_argument('--part-shape', choices=('rectangle', 'circle'), default='rectangle')
    parser.add_argument(
        '--orientation-mode', choices=('long_axis', 'preserve'),
        default='long_axis',
    )
    parser.add_argument(
        '--segmentation-mode', choices=('bright', 'dark', 'depth'),
        default='bright',
    )
    parser.add_argument(
        '--square-pixels',
        type=int,
        default=None,
        help='Deprecated compatibility flag for marker-based flow; ignored in markerless mode.',
    )
    parser.add_argument('--part-color', choices=('light', 'orange', 'brown', 'any'), default='light')
    parser.add_argument('--frames', type=int, default=20)
    parser.add_argument('--min-corners', type=int, default=12)
    parser.add_argument('--roi-margin', type=float, default=0.03)
    parser.add_argument('--min-gray', type=float, default=55.0)
    parser.add_argument('--gray-delta', type=float, default=24.0)
    parser.add_argument('--max-gray', type=float, default=180.0)
    parser.add_argument('--dark-gray-delta', type=float, default=20.0)
    parser.add_argument('--depth-mask-height-fraction', type=float, default=0.35)
    parser.add_argument('--min-circularity', type=float, default=0.45)
    parser.add_argument('--min-area-ratio', type=float, default=0.20)
    parser.add_argument('--max-area-ratio', type=float, default=3.0)
    parser.add_argument('--min-size-ratio', type=float, default=0.55)
    parser.add_argument('--max-size-ratio', type=float, default=1.65)
    parser.add_argument('--depth-sync-sec', type=float, default=0.20)
    parser.add_argument('--min-depth-valid-fraction', type=float, default=0.55)
    parser.add_argument('--min-depth-pixels', type=int, default=9)
    parser.add_argument('--max-depth-mad-mm', type=float, default=2.0)
    parser.add_argument('--max-depth-jitter-mm', type=float, default=2.0)
    parser.add_argument('--support-ring-inner-px', type=int, default=3)
    parser.add_argument('--support-ring-outer-px', type=int, default=12)
    parser.add_argument('--min-support-depth-pixels', type=int, default=40)
    parser.add_argument('--max-support-plane-mad-mm', type=float, default=2.0)
    parser.add_argument('--min-observed-height-mm', type=float, default=0.5)
    parser.add_argument('--height-tolerance-mm', type=float, default=2.0)
    parser.add_argument('--max-base-jitter-mm', type=float, default=0.5)
    parser.add_argument('--max-angle-jitter-deg', type=float, default=5.0)
    parser.add_argument('--target-center-u-norm', type=float, default=0.5)
    parser.add_argument('--target-center-v-norm', type=float, default=0.5)
    parser.add_argument('--max-target-center-distance-fraction', type=float, default=0.30)
    parser.add_argument('--max-tracking-jump-px', type=float, default=12.0)
    parser.add_argument('--min-selection-margin-px', type=float, default=20.0)
    parser.add_argument('--max-robot-state-age-sec', type=float, default=0.5)
    parser.add_argument('--track-base-target-file', type=Path)
    parser.add_argument('--max-tracking-target-age-sec', type=float, default=300.0)
    parser.add_argument('--depth-topic', default='/camera/camera/aligned_depth_to_color/image_raw')
    parser.add_argument('--color-topic', default='/camera/camera/color/image_raw/compressed')
    parser.add_argument('--camera-info-topic', default='/camera/camera/color/camera_info')
    parser.add_argument('--robot-state-topic', default='/nonrt_state_data')
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

    if args.fallback_grid_cols <= 0 or args.fallback_grid_rows <= 0:
        parser.error('fallback grid dimensions must be positive')
    if not 0 <= args.cell_col < args.fallback_grid_cols:
        parser.error('--cell-col is outside the fallback grid')
    if not 0 <= args.cell_row < args.fallback_grid_rows:
        parser.error('--cell-row is outside the fallback grid')
    if args.frames <= 0:
        parser.error('--frames must be positive')
    if min(args.part_length_mm, args.part_width_mm, args.part_height_mm) <= 0.0:
        parser.error('part dimensions must be positive')
    if not 0.0 < args.min_area_ratio < args.max_area_ratio:
        parser.error('area ratios must be positive and increasing')
    if not 0.0 < args.min_size_ratio < args.max_size_ratio:
        parser.error('size ratios must be positive and increasing')
    if not 0.05 <= args.depth_mask_height_fraction <= 0.9:
        parser.error('--depth-mask-height-fraction must be in [0.05, 0.9]')
    if not 0.0 < args.min_circularity <= 1.0:
        parser.error('--min-circularity must be in (0, 1]')
    if not 0.0 <= args.max_gray <= 255.0 or args.dark_gray_delta < 0.0:
        parser.error('dark segmentation thresholds are invalid')
    if not 0.0 < args.min_depth_valid_fraction <= 1.0:
        parser.error('--min-depth-valid-fraction must be in (0, 1]')
    if args.min_depth_pixels < 3 or args.min_support_depth_pixels < 6:
        parser.error('depth pixel minimums are too small')
    if not 0 <= args.support_ring_inner_px < args.support_ring_outer_px:
        parser.error('support ring must satisfy 0 <= inner < outer')
    if (
        args.max_depth_mad_mm <= 0.0
        or args.max_depth_jitter_mm <= 0.0
        or args.max_support_plane_mad_mm <= 0.0
        or args.height_tolerance_mm <= 0.0
    ):
        parser.error('depth noise limits must be positive')
    if args.min_observed_height_mm < 0.0:
        parser.error('--min-observed-height-mm must be nonnegative')
    if args.max_angle_jitter_deg <= 0.0 or args.max_angle_jitter_deg > 45.0:
        parser.error('--max-angle-jitter-deg must be in (0, 45]')
    if not 0.0 <= args.target_center_u_norm <= 1.0 or not 0.0 <= args.target_center_v_norm <= 1.0:
        parser.error('target center normalized coordinates must be in [0, 1]')
    if not 0.05 <= args.max_target_center_distance_fraction <= 0.5:
        parser.error('--max-target-center-distance-fraction must be in [0.05, 0.5]')
    if min(args.max_tracking_jump_px, args.min_selection_margin_px, args.max_robot_state_age_sec) <= 0.0:
        parser.error('tracking and state-age limits must be positive')

    rclpy.init()
    node = SmallPartDetector(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        target_written = node.target_written
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if not target_written:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
