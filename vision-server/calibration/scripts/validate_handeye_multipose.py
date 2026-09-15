#!/usr/bin/env python3
"""Append one no-motion multi-pose Hand-Eye validation sample to CSV."""

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.executors import MultiThreadedExecutor
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage

from charuco_common import detect_charuco, detector_parameters, load_config


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULT = ROOT / "data" / "handeye_result.json"
DEFAULT_CSV = ROOT / "data" / "handeye_multipose_validation.csv"
ROBOT_SETTLE_SECONDS = 1.0
STABLE_TRANSLATION_MM = 0.25
STABLE_ROTATION_DEG = 0.10


def transform(rotation, translation):
    value = np.eye(4, dtype=float)
    value[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    value[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return value


def project_rotation(matrix):
    u, _, vt = np.linalg.svd(matrix)
    result = u @ vt
    if np.linalg.det(result) < 0:
        u[:, -1] *= -1
        result = u @ vt
    return result


def wrapped_delta_deg(current, previous):
    delta = np.asarray(current) - np.asarray(previous)
    return (delta + 180.0) % 360.0 - 180.0


def marker_center_for_id(board, marker_id):
    ids = np.asarray(board.ids).reshape(-1).astype(int).tolist()
    if marker_id not in ids:
        raise ValueError(f"Marker ID {marker_id} is not in this board: {ids}")
    index = ids.index(marker_id)
    return np.mean(
        np.asarray(board.objPoints[index], dtype=float).reshape(4, 3), axis=0
    )


FIELDS = [
    "sample_index", "timestamp_utc", "target_type", "target_id",
    "transform_chain", "handeye_sha256", "euler_convention", "handeye_method",
    "image_width", "image_height", "camera_info_width", "camera_info_height",
    "fx", "fy", "cx", "cy", "distortion_coefficients",
    "detected_markers", "detected_charuco_corners",
    "reprojection_median_px", "reprojection_max_px",
    "flange_x_mm", "flange_y_mm", "flange_z_mm",
    "flange_a_deg", "flange_b_deg", "flange_c_deg",
    "tcp_x_mm", "tcp_y_mm", "tcp_z_mm",
    "tcp_a_deg", "tcp_b_deg", "tcp_c_deg", "tool_num",
    "camera_base_rx_deg", "camera_base_ry_deg", "camera_base_rz_deg",
    "target_camera_x_mm", "target_camera_y_mm", "target_camera_z_mm",
    "target_base_x_mm", "target_base_y_mm", "target_base_z_mm",
    "frame_jitter_median_mm", "frame_jitter_max_mm",
    "T_base_flange", "T_flange_camera", "T_camera_board", "T_base_board",
]


class MultiPoseValidator(Node):
    def __init__(self, args):
        super().__init__("validate_handeye_multipose")
        self.args = args
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.marker_center_board = marker_center_for_id(self.board, args.marker_id)

        payload = json.loads(args.result.read_text(encoding="utf-8"))
        best = payload["best"]
        self.euler_convention = best["euler_convention"]
        self.handeye_method = best["method"]
        camera_to_flange = best["camera_to_flange"]
        self.T_flange_camera = transform(
            camera_to_flange["rotation_matrix"], camera_to_flange["translation_m"]
        )
        self.handeye_sha256 = hashlib.sha256(args.result.read_bytes()).hexdigest()

        self.camera_matrix = None
        self.distortion = None
        self.intrinsic_override = None
        if args.intrinsics_file is not None:
            intrinsic = json.loads(args.intrinsics_file.read_text(encoding="utf-8"))
            self.intrinsic_override = {
                "size": (int(intrinsic["image_width"]), int(intrinsic["image_height"])),
                "camera_matrix": np.asarray(intrinsic["camera_matrix"], dtype=float),
                "distortion": np.asarray(
                    intrinsic["distortion_coefficients"], dtype=float
                ),
            }
        self.camera_info_size = None
        self.robot_state = None
        self.last_stationary_pose = None
        self.stable_since = None
        self.image_received = False
        self.last_image_size = None
        self.size_mismatch = False
        self.last_markers = 0
        self.last_corners = 0
        self.last_reprojection_median = None
        self.last_reprojection_max = None
        self.rejected_pose_frames = 0
        self.samples = []
        self.last_processed_image_time = 0.0

        self.create_subscription(
            CompressedImage, self.config["image_topic"], self.on_image,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            CameraInfo, self.config["camera_info_topic"], self.on_camera_info,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            RobotNonrtState, self.config["robot_state_topic"], self.on_robot_state, 10
        )
        self.create_timer(3.0, self.report_status)
        self.get_logger().info(
            f"NO MOTION validation: marker ID={args.marker_id}, "
            f"PnP={args.pnp_method}, collecting {args.frames} stable frames"
        )

    def estimate_board_pose(self, charuco_corners, charuco_ids):
        if self.args.pnp_method == "charuco":
            valid, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
                charuco_corners, charuco_ids, self.board,
                self.camera_matrix, self.distortion, None, None,
            )
            return bool(valid), rvec, tvec
        object_points = np.asarray(
            self.board.chessboardCorners[charuco_ids.flatten()], dtype=np.float32
        ).reshape(-1, 3)
        image_points = np.asarray(charuco_corners, dtype=np.float32).reshape(-1, 2)
        flag = (
            cv2.SOLVEPNP_IPPE
            if self.args.pnp_method == "ippe"
            else cv2.SOLVEPNP_SQPNP
        )
        return cv2.solvePnP(
            object_points, image_points, self.camera_matrix, self.distortion,
            flags=flag,
        )

    def on_camera_info(self, msg):
        self.camera_info_size = (int(msg.width), int(msg.height))
        if self.intrinsic_override is None:
            self.camera_matrix = np.asarray(msg.k, dtype=float).reshape(3, 3)
            self.distortion = np.asarray(msg.d, dtype=float)
            return
        if self.camera_info_size != self.intrinsic_override["size"]:
            self.camera_matrix = None
            self.distortion = None
            return
        self.camera_matrix = self.intrinsic_override["camera_matrix"]
        self.distortion = self.intrinsic_override["distortion"]

    def on_robot_state(self, msg):
        self.robot_state = msg
        pose = np.asarray([
            msg.flange_x_cur_pos, msg.flange_y_cur_pos, msg.flange_z_cur_pos,
            msg.flange_a_cur_pos, msg.flange_b_cur_pos, msg.flange_c_cur_pos,
        ], dtype=float)
        stationary = int(msg.robot_motion_done) == 1
        stable = False
        if stationary and self.last_stationary_pose is not None:
            translation = np.linalg.norm(pose[:3] - self.last_stationary_pose[:3])
            rotation = np.linalg.norm(wrapped_delta_deg(pose[3:], self.last_stationary_pose[3:]))
            stable = translation <= STABLE_TRANSLATION_MM and rotation <= STABLE_ROTATION_DEG
        if not stationary or not stable:
            self.stable_since = None
            self.samples.clear()
        elif self.stable_since is None:
            self.stable_since = time.monotonic()
        self.last_stationary_pose = pose if stationary else None

    def robot_is_settled(self):
        return (
            self.robot_state is not None
            and int(self.robot_state.robot_motion_done) == 1
            and self.stable_since is not None
            and time.monotonic() - self.stable_since >= ROBOT_SETTLE_SECONDS
        )

    def on_image(self, msg):
        self.image_received = True
        now = time.monotonic()
        if now - self.last_processed_image_time < 0.1:
            return
        self.last_processed_image_time = now
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        height, width = frame.shape[:2]
        self.last_image_size = (width, height)
        if self.camera_info_size is not None and self.camera_info_size != self.last_image_size:
            self.size_mismatch = True
            self.samples.clear()
            return
        self.size_mismatch = False
        if self.camera_matrix is None or self.robot_state is None or not self.robot_is_settled():
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, marker_ids, charuco_corners, charuco_ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters,
            self.camera_matrix, self.distortion,
        )
        self.last_markers = 0 if marker_ids is None else len(marker_ids)
        self.last_corners = 0 if charuco_ids is None else len(charuco_ids)
        if marker_ids is None or charuco_ids is None or len(charuco_ids) < self.args.min_corners:
            return
        ids = marker_ids.reshape(-1).astype(int).tolist()
        if self.args.marker_id not in ids or len(ids) != len(set(ids)):
            return

        valid, rvec, tvec = self.estimate_board_pose(charuco_corners, charuco_ids)
        if not valid:
            return
        object_points = self.board.chessboardCorners[charuco_ids.flatten()]
        projected, _ = cv2.projectPoints(
            object_points, rvec, tvec, self.camera_matrix, self.distortion
        )
        reprojection = np.linalg.norm(
            projected.reshape(-1, 2) - charuco_corners.reshape(-1, 2), axis=1
        )
        reproj_median = float(np.median(reprojection))
        reproj_max = float(np.max(reprojection))
        self.last_reprojection_median = reproj_median
        self.last_reprojection_max = reproj_max
        if reproj_median > self.args.max_reprojection_median_px or reproj_max > self.args.max_reprojection_max_px:
            self.rejected_pose_frames += 1
            if self.rejected_pose_frames == 1 or self.rejected_pose_frames % 20 == 0:
                self.get_logger().warning(
                    f"Rejecting {self.args.pnp_method} pose: reprojection "
                    f"median={reproj_median:.3f}px (limit "
                    f"{self.args.max_reprojection_median_px:.3f}), "
                    f"max={reproj_max:.3f}px (limit "
                    f"{self.args.max_reprojection_max_px:.3f})"
                )
            return
        self.rejected_pose_frames = 0

        state = self.robot_state
        R_base_flange = Rotation.from_euler(
            self.euler_convention,
            [state.flange_a_cur_pos, state.flange_b_cur_pos, state.flange_c_cur_pos],
            degrees=True,
        ).as_matrix()
        T_base_flange = transform(R_base_flange, np.asarray([
            state.flange_x_cur_pos, state.flange_y_cur_pos, state.flange_z_cur_pos
        ]) / 1000.0)
        R_camera_board, _ = cv2.Rodrigues(rvec)
        T_camera_board = transform(R_camera_board, np.asarray(tvec).reshape(3))
        T_base_board = T_base_flange @ self.T_flange_camera @ T_camera_board
        marker_h = np.append(self.marker_center_board, 1.0)
        target_camera = (T_camera_board @ marker_h)[:3]
        target_base = (T_base_board @ marker_h)[:3]
        R_base_camera = (T_base_flange @ self.T_flange_camera)[:3, :3]
        camera_euler = Rotation.from_matrix(R_base_camera).as_euler(
            self.euler_convention, degrees=True
        )
        self.samples.append({
            "state": state,
            "target_camera": target_camera,
            "target_base": target_base,
            "camera_euler": camera_euler,
            "reproj_median": reproj_median,
            "reproj_max": reproj_max,
            "markers": len(marker_ids),
            "corners": len(charuco_ids),
            "T_base_flange": T_base_flange,
            "T_camera_board": T_camera_board,
            "T_base_board": T_base_board,
        })
        count = len(self.samples)
        if count == 1 or count % 5 == 0:
            self.get_logger().info(f"Stable frames: {count}/{self.args.frames}")
        if count >= self.args.frames:
            rclpy.shutdown()

    def report_status(self):
        waiting = []
        if not self.image_received:
            waiting.append("compressed color image")
        if self.camera_matrix is None:
            waiting.append("camera_info")
        if self.size_mismatch:
            waiting.append(
                f"matching image/intrinsic resolution (image={self.last_image_size}, "
                f"CameraInfo={self.camera_info_size})"
            )
        if self.robot_state is None:
            waiting.append("robot state")
        elif not self.robot_is_settled():
            waiting.append(f"robot stationary for {ROBOT_SETTLE_SECONDS:.1f} s")
        if self.image_received and self.last_corners < self.args.min_corners:
            waiting.append(
                f"ChArUco target (markers={self.last_markers}, "
                f"corners={self.last_corners}, need>={self.args.min_corners})"
            )
        if waiting:
            self.get_logger().warning("Still waiting for: " + ", ".join(waiting))

    def aggregate(self):
        if len(self.samples) < self.args.frames:
            raise RuntimeError(f"Only {len(self.samples)}/{self.args.frames} valid frames")
        centers = np.asarray([s["target_base"] for s in self.samples])
        center = np.median(centers, axis=0)
        errors = np.linalg.norm(centers - center, axis=1) * 1000.0
        reference = min(self.samples, key=lambda s: np.linalg.norm(s["target_base"] - center))
        return reference, center, errors


def matrix_json(value):
    return json.dumps(np.asarray(value, dtype=float).round(12).tolist(), separators=(",", ":"))


def append_csv(node, reference, center, errors):
    path = node.args.csv
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8"))) if path.exists() else []
    if rows:
        if int(rows[0]["target_id"]) != node.args.marker_id:
            raise SystemExit(
                f"CSV already contains target ID {rows[0]['target_id']}; use another --csv file"
            )
        if rows[0]["handeye_sha256"] != node.handeye_sha256:
            raise SystemExit("CSV uses a different Hand-Eye result; use another --csv file")
    state = reference["state"]
    camera = np.median(np.asarray([s["target_camera"] for s in node.samples]), axis=0) * 1000.0
    cam_euler = np.median(np.asarray([s["camera_euler"] for s in node.samples]), axis=0)
    K = node.camera_matrix
    row = {
        "sample_index": len(rows) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_type": f"charuco_marker_center_from_full_board_pose:{node.args.pnp_method}",
        "target_id": node.args.marker_id,
        "transform_chain": (
            "T_base_target=T_base_flange@T_flange_camera@T_camera_board@"
            f"p_board_target;pnp={node.args.pnp_method}"
        ),
        "handeye_sha256": node.handeye_sha256,
        "euler_convention": node.euler_convention,
        "handeye_method": node.handeye_method,
        "image_width": node.last_image_size[0], "image_height": node.last_image_size[1],
        "camera_info_width": node.camera_info_size[0], "camera_info_height": node.camera_info_size[1],
        "fx": K[0, 0], "fy": K[1, 1], "cx": K[0, 2], "cy": K[1, 2],
        "distortion_coefficients": json.dumps(node.distortion.tolist(), separators=(",", ":")),
        "detected_markers": int(np.median([s["markers"] for s in node.samples])),
        "detected_charuco_corners": int(np.median([s["corners"] for s in node.samples])),
        "reprojection_median_px": float(np.median([s["reproj_median"] for s in node.samples])),
        "reprojection_max_px": float(np.max([s["reproj_max"] for s in node.samples])),
        "flange_x_mm": state.flange_x_cur_pos, "flange_y_mm": state.flange_y_cur_pos,
        "flange_z_mm": state.flange_z_cur_pos, "flange_a_deg": state.flange_a_cur_pos,
        "flange_b_deg": state.flange_b_cur_pos, "flange_c_deg": state.flange_c_cur_pos,
        "tcp_x_mm": state.cart_x_cur_pos, "tcp_y_mm": state.cart_y_cur_pos,
        "tcp_z_mm": state.cart_z_cur_pos, "tcp_a_deg": state.cart_a_cur_pos,
        "tcp_b_deg": state.cart_b_cur_pos, "tcp_c_deg": state.cart_c_cur_pos,
        "tool_num": int(state.tool_num),
        "camera_base_rx_deg": cam_euler[0], "camera_base_ry_deg": cam_euler[1],
        "camera_base_rz_deg": cam_euler[2],
        "target_camera_x_mm": camera[0], "target_camera_y_mm": camera[1],
        "target_camera_z_mm": camera[2],
        "target_base_x_mm": center[0] * 1000.0, "target_base_y_mm": center[1] * 1000.0,
        "target_base_z_mm": center[2] * 1000.0,
        "frame_jitter_median_mm": float(np.median(errors)),
        "frame_jitter_max_mm": float(np.max(errors)),
        "T_base_flange": matrix_json(reference["T_base_flange"]),
        "T_flange_camera": matrix_json(node.T_flange_camera),
        "T_camera_board": matrix_json(reference["T_camera_board"]),
        "T_base_board": matrix_json(reference["T_base_board"]),
    }
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not rows:
            writer.writeheader()
        writer.writerow(row)
    return path


def report_csv(path):
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    xyz = np.asarray([[float(r[f"target_base_{axis}_mm"]) for axis in "xyz"] for r in rows])
    mean = np.mean(xyz, axis=0)
    delta = xyz - mean
    norms = np.linalg.norm(delta, axis=1)
    print("\nMULTI-POSE HAND-EYE VALIDATION - NO ROBOT MOTION")
    print(f"Samples/target: {len(rows)} / marker ID {rows[0]['target_id']}")
    print("Mean Base XYZ [mm]:", np.round(mean, 3).tolist())
    print("Std Base XYZ  [mm]:", np.round(np.std(xyz, axis=0), 3).tolist())
    print(" index        dX        dY        dZ      norm")
    for row, d, norm in zip(rows, delta, norms):
        print(f" {int(row['sample_index']):5d} {d[0]:9.3f} {d[1]:9.3f} {d[2]:9.3f} {norm:9.3f}")
    print(f"Maximum 3D error [mm]: {np.max(norms):.3f}")
    print(f"RMS position error [mm]: {np.sqrt(np.mean(norms ** 2)):.3f}")
    if len(rows) >= 3:
        rotations = np.asarray([[float(r[f"camera_base_r{axis}_deg"]) for axis in "xyz"] for r in rows])
        print("Rotation/error Pearson correlation (diagnostic only):")
        for axis_index, axis in enumerate("XYZ"):
            if np.std(rotations[:, axis_index]) < 1e-9 or np.std(norms) < 1e-9:
                value = float("nan")
            else:
                value = np.corrcoef(rotations[:, axis_index], norms)[0, 1]
            print(f"  Camera Base R{axis} vs 3D error: {value:.3f}")
    print("CSV:", path)


def parse_args():
    parser = argparse.ArgumentParser(description="No-motion multi-pose Hand-Eye validation")
    parser.add_argument("--marker-id", type=int, required=True)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--min-corners", type=int, default=12)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--intrinsics-file", type=Path, default=None)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--pnp-method", choices=("charuco", "ippe", "sqpnp"), default="charuco",
        help="Board pose solver. charuco preserves the existing OpenCV behavior.",
    )
    parser.add_argument("--max-reprojection-median-px", type=float, default=1.2)
    parser.add_argument("--max-reprojection-max-px", type=float, default=3.0)
    args = parser.parse_args()
    if args.frames < 5:
        parser.error("--frames must be at least 5")
    if not 6 <= args.min_corners <= 24:
        parser.error("--min-corners must be between 6 and 24")
    return args


def main():
    args = parse_args()
    rclpy.init()
    node = MultiPoseValidator(args)
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
        reference, center, errors = node.aggregate()
        path = append_csv(node, reference, center, errors)
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; no validation sample was written")
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    report_csv(path)


if __name__ == "__main__":
    main()
