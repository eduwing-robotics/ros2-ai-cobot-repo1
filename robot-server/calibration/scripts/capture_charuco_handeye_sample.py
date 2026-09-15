#!/usr/bin/env python3
"""Capture one stationary FR5 Eye-in-Hand sample using a ChArUco board."""

import argparse
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
from sensor_msgs.msg import CameraInfo, CompressedImage

from charuco_common import detect_charuco, detector_parameters, load_config


MIN_CORNERS = 12
MIN_POSES = 20
MAX_REPROJECTION_MEDIAN_PX = 1.2
MAX_REPROJECTION_MAX_PX = 3.0
ROBOT_SETTLE_SECONDS = 1.0
STABLE_TRANSLATION_MM = 0.25
STABLE_ROTATION_DEG = 0.10


def project_rotation(matrix):
    u, _, vt = np.linalg.svd(matrix)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        u[:, -1] *= -1
        rotation = u @ vt
    return rotation


class Collector(Node):
    def __init__(self, frame_count):
        super().__init__("capture_charuco_handeye_sample")
        self.frame_count = frame_count
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.total_markers = len(self.board.ids)
        self.total_corners = (int(self.config["squares_x"]) - 1) * (
            int(self.config["squares_y"]) - 1
        )
        self.camera_matrix = None
        self.distortion = None
        self.distortion_model = None
        self.camera_info_size = None
        self.camera_info_frame_id = ""
        self.camera_info_stamp = None
        self.last_image_size = None
        self.image_frame_id = ""
        self.image_stamp = None
        self.resolution_mismatch = False
        self.robot_state = None
        self.robot_stable_since = None
        self.last_stationary_flange_pose = None
        self.image_received = False
        self.board_seen = False
        self.last_marker_count = 0
        self.last_corner_count = 0
        self.duplicate_marker_ids = False
        self.last_reprojection_median = None
        self.last_reprojection_max = None
        self.rotations = []
        self.translations = []
        self.corner_counts = []
        self.reprojection_medians = []
        self.reprojection_maxes = []
        self.robot_samples = []
        self.representative_image = None

        self.image_sub = self.create_subscription(
            CompressedImage,
            self.config["image_topic"],
            self.on_image,
            qos_profile_sensor_data,
        )
        self.info_sub = self.create_subscription(
            CameraInfo,
            self.config["camera_info_topic"],
            self.on_camera_info,
            qos_profile_sensor_data,
        )
        self.robot_sub = self.create_subscription(
            RobotNonrtState, self.config["robot_state_topic"], self.on_robot_state, 10
        )
        self.status_timer = self.create_timer(3.0, self.report_status)
        self.get_logger().info(
            "Waiting for ChArUco board, camera info, and stationary robot state"
        )

    def on_camera_info(self, msg):
        self.camera_matrix = np.asarray(msg.k, dtype=np.float64).reshape(3, 3)
        self.distortion = np.asarray(msg.d, dtype=np.float64)
        self.distortion_model = str(msg.distortion_model)
        self.camera_info_size = (int(msg.width), int(msg.height))
        self.camera_info_frame_id = str(msg.header.frame_id)
        self.camera_info_stamp = {
            "sec": int(msg.header.stamp.sec),
            "nanosec": int(msg.header.stamp.nanosec),
        }

    def on_robot_state(self, msg):
        self.robot_state = msg
        pose = np.asarray(
            [
                msg.flange_x_cur_pos,
                msg.flange_y_cur_pos,
                msg.flange_z_cur_pos,
                msg.flange_a_cur_pos,
                msg.flange_b_cur_pos,
                msg.flange_c_cur_pos,
            ],
            dtype=float,
        )
        stationary = int(msg.robot_motion_done) == 1
        stable = False
        if stationary and self.last_stationary_flange_pose is not None:
            translation_delta = np.linalg.norm(
                pose[:3] - self.last_stationary_flange_pose[:3]
            )
            rotation_delta = pose[3:] - self.last_stationary_flange_pose[3:]
            rotation_delta = (rotation_delta + 180.0) % 360.0 - 180.0
            stable = (
                translation_delta <= STABLE_TRANSLATION_MM
                and np.linalg.norm(rotation_delta) <= STABLE_ROTATION_DEG
            )
        if not stationary or not stable:
            self.robot_stable_since = None
            if self.rotations:
                self.rotations.clear()
                self.translations.clear()
                self.corner_counts.clear()
                self.reprojection_medians.clear()
                self.reprojection_maxes.clear()
                self.robot_samples.clear()
        elif self.robot_stable_since is None:
            self.robot_stable_since = time.monotonic()
        self.last_stationary_flange_pose = pose if stationary else None

    def robot_is_settled(self):
        return (
            self.robot_state is not None
            and int(self.robot_state.robot_motion_done) == 1
            and self.robot_stable_since is not None
            and time.monotonic() - self.robot_stable_since >= ROBOT_SETTLE_SECONDS
        )

    def report_status(self):
        waiting = []
        if not self.image_received:
            waiting.append("compressed color image")
        if self.camera_matrix is None:
            waiting.append("camera_info")
        if self.resolution_mismatch:
            waiting.append(
                f"matching image/CameraInfo resolution "
                f"(image={self.last_image_size}, CameraInfo={self.camera_info_size})"
            )
        if self.robot_state is None:
            waiting.append("robot state")
        elif not self.robot_is_settled():
            waiting.append(f"robot stationary for {ROBOT_SETTLE_SECONDS:.1f} s")
        if self.image_received and not self.board_seen:
            if self.duplicate_marker_ids:
                waiting.append("only one ChArUco board (duplicate marker IDs detected)")
            if (
                self.last_reprojection_median is not None
                and (
                    self.last_reprojection_median > MAX_REPROJECTION_MEDIAN_PX
                    or self.last_reprojection_max > MAX_REPROJECTION_MAX_PX
                )
            ):
                waiting.append(
                    f"valid board geometry (reprojection median="
                    f"{self.last_reprojection_median:.2f}px, "
                    f"max={self.last_reprojection_max:.2f}px)"
                )
            waiting.append(
                f"ChArUco board (markers={self.last_marker_count}, "
                f"corners={self.last_corner_count}, need>={MIN_CORNERS})"
            )
        if waiting:
            self.get_logger().warning("Still waiting for: " + ", ".join(waiting))

    def on_image(self, msg):
        self.image_received = True
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        self.last_image_size = (int(frame.shape[1]), int(frame.shape[0]))
        self.image_frame_id = str(msg.header.frame_id)
        self.image_stamp = {
            "sec": int(msg.header.stamp.sec),
            "nanosec": int(msg.header.stamp.nanosec),
        }
        self.resolution_mismatch = (
            self.camera_info_size is not None
            and self.last_image_size != self.camera_info_size
        )
        if self.resolution_mismatch:
            self.board_seen = False
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        marker_corners, marker_ids, charuco_corners, charuco_ids, _ = detect_charuco(
            gray,
            self.dictionary,
            self.board,
            self.parameters,
            self.camera_matrix,
            self.distortion,
        )
        self.last_marker_count = 0 if marker_ids is None else len(marker_ids)
        self.last_corner_count = 0 if charuco_ids is None else len(charuco_ids)
        marker_values = [] if marker_ids is None else marker_ids.flatten().tolist()
        self.duplicate_marker_ids = len(marker_values) != len(set(marker_values))
        configured_ids = set(int(value) for value in self.board.ids.flatten())
        unknown_marker_ids = any(int(value) not in configured_ids for value in marker_values)
        if self.duplicate_marker_ids or unknown_marker_ids:
            self.board_seen = False
            return
        if charuco_ids is None or len(charuco_ids) < MIN_CORNERS:
            return
        self.board_seen = True
        if self.camera_matrix is None or self.robot_state is None:
            return
        if not self.robot_is_settled():
            return
        valid, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            charuco_corners,
            charuco_ids,
            self.board,
            self.camera_matrix,
            self.distortion,
            None,
            None,
        )
        if not valid:
            return
        object_points = self.board.chessboardCorners[charuco_ids.flatten()]
        projected, _ = cv2.projectPoints(
            object_points, rvec, tvec, self.camera_matrix, self.distortion
        )
        reprojection_errors = np.linalg.norm(
            projected.reshape(-1, 2) - charuco_corners.reshape(-1, 2), axis=1
        )
        reprojection_median = float(np.median(reprojection_errors))
        reprojection_max = float(np.max(reprojection_errors))
        self.last_reprojection_median = reprojection_median
        self.last_reprojection_max = reprojection_max
        if (
            reprojection_median > MAX_REPROJECTION_MEDIAN_PX
            or reprojection_max > MAX_REPROJECTION_MAX_PX
        ):
            self.board_seen = False
            return
        rotation, _ = cv2.Rodrigues(rvec)
        self.rotations.append(rotation)
        self.translations.append(np.asarray(tvec).reshape(3))
        self.corner_counts.append(len(charuco_ids))
        self.reprojection_medians.append(reprojection_median)
        self.reprojection_maxes.append(reprojection_max)
        s = self.robot_state
        self.robot_samples.append({
            "flange_xyz_mm": [s.flange_x_cur_pos, s.flange_y_cur_pos, s.flange_z_cur_pos],
            "flange_abc_deg": [s.flange_a_cur_pos, s.flange_b_cur_pos, s.flange_c_cur_pos],
            "cart_xyz_mm": [s.cart_x_cur_pos, s.cart_y_cur_pos, s.cart_z_cur_pos],
            "cart_abc_deg": [s.cart_a_cur_pos, s.cart_b_cur_pos, s.cart_c_cur_pos],
            "joint_deg": [s.j1_cur_pos, s.j2_cur_pos, s.j3_cur_pos, s.j4_cur_pos, s.j5_cur_pos, s.j6_cur_pos],
            "tool_num": int(s.tool_num),
            "robot_motion_done": int(s.robot_motion_done),
            "robot_state_timestamp": int(getattr(s, "timestamp", 0)),
        })
        # Keep the unmodified frame so samples can be reprocessed if board or
        # camera parameters ever need correction. Drawing overlays destroys
        # marker borders and prevents reliable redetection from saved images.
        self.representative_image = frame.copy()
        count = len(self.rotations)
        if count == 1 or count % 5 == 0:
            self.get_logger().info(
                f"Stable frames collected: {count}/{self.frame_count} "
                f"(markers={self.last_marker_count}/{self.total_markers}, "
                f"corners={self.last_corner_count}/{self.total_corners}, "
                f"reproj={reprojection_median:.2f}px)"
            )
        if count >= self.frame_count:
            rclpy.shutdown()

    def result(self):
        if len(self.rotations) < self.frame_count:
            raise RuntimeError(f"Only {len(self.rotations)}/{self.frame_count} valid frames collected")
        return (
            project_rotation(np.mean(self.rotations, axis=0)),
            np.median(self.translations, axis=0),
            self.robot_samples[len(self.robot_samples) // 2],
            self.representative_image,
            int(np.median(self.corner_counts)),
            float(np.median(self.reprojection_medians)),
            float(np.max(self.reprojection_maxes)),
            {
                "image_width": int(self.last_image_size[0]),
                "image_height": int(self.last_image_size[1]),
                "camera_info_width": int(self.camera_info_size[0]),
                "camera_info_height": int(self.camera_info_size[1]),
                "camera_matrix": self.camera_matrix.tolist(),
                "distortion_model": self.distortion_model,
                "distortion_coefficients": self.distortion.tolist(),
                "image_frame_id": self.image_frame_id,
                "camera_info_frame_id": self.camera_info_frame_id,
                "image_stamp": self.image_stamp,
                "camera_info_stamp": self.camera_info_stamp,
                "image_topic": self.config["image_topic"],
                "camera_info_topic": self.config["camera_info_topic"],
            },
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--data-file", type=Path, default=None)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_file = args.data_file or data_dir / "handeye_samples.json"
    image_dir = data_file.parent / (f"{data_file.stem}_images" if args.data_file else "images")
    image_dir.mkdir(parents=True, exist_ok=True)

    preloaded_payload = None
    if data_file.exists():
        preloaded_payload = json.loads(data_file.read_text(encoding="utf-8"))
        if preloaded_payload.get("target", {}).get("type") != "charuco":
            raise SystemExit(f"Refusing to mix non-ChArUco data in {data_file}")
        legacy = [
            sample.get("index", "?")
            for sample in preloaded_payload.get("samples", [])
            if not sample.get("camera")
        ]
        if legacy:
            raise SystemExit(
                f"{data_file} is a preserved legacy dataset without per-sample "
                "CameraInfo. Do not append to it; choose a new --data-file name."
            )

    rclpy.init()
    node = Collector(args.frames)
    try:
        rclpy.spin(node)
        (
            rotation,
            translation,
            robot,
            image,
            corner_count,
            reprojection_median,
            reprojection_max,
            camera,
        ) = node.result()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; no sample was written")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    if preloaded_payload is not None:
        payload = preloaded_payload
    else:
        payload = {
            "schema_version": 3,
            "calibration_type": "eye_in_hand",
            "robot_pose": "base_to_flange",
            "target_pose": "charuco_board_to_color_camera",
            "target": {
                "type": "charuco",
                "dictionary": node.config["dictionary"],
                "squares_x": node.config["squares_x"],
                "squares_y": node.config["squares_y"],
                "square_length_m": node.config["square_length_m"],
                "marker_length_m": node.config["marker_length_m"],
            },
            "samples": [],
        }
    expected_target = {
        "dictionary": node.config["dictionary"],
        "squares_x": node.config["squares_x"],
        "squares_y": node.config["squares_y"],
        "square_length_m": node.config["square_length_m"],
        "marker_length_m": node.config["marker_length_m"],
    }
    existing_target = payload.get("target", {})
    for key, expected in expected_target.items():
        if key not in existing_target:
            continue
        actual = existing_target[key]
        if isinstance(expected, float):
            matches = np.isclose(float(actual), float(expected), atol=1e-12)
        else:
            matches = actual == expected
        if not matches:
            raise SystemExit(
                f"Refusing to mix ChArUco target definitions in {data_file}: "
                f"{key}={actual!r}, current={expected!r}"
            )

    previous_camera_contracts = [
        sample.get("camera") for sample in payload["samples"] if sample.get("camera")
    ]
    if previous_camera_contracts:
        previous = previous_camera_contracts[0]
        previous_size = (previous["image_width"], previous["image_height"])
        current_size = (camera["image_width"], camera["image_height"])
        if previous_size != current_size:
            raise SystemExit(
                f"Refusing to mix image resolutions in {data_file}: "
                f"existing={previous_size}, current={current_size}"
            )
        if not np.allclose(
            np.asarray(previous["camera_matrix"], dtype=float),
            np.asarray(camera["camera_matrix"], dtype=float),
            rtol=0.0,
            atol=1e-9,
        ) or not np.allclose(
            np.asarray(previous["distortion_coefficients"], dtype=float),
            np.asarray(camera["distortion_coefficients"], dtype=float),
            rtol=0.0,
            atol=1e-9,
        ):
            raise SystemExit(
                f"Refusing to mix camera intrinsics in {data_file}; "
                "use a new --data-file after changing CameraInfo"
            )
    new_xyz = np.asarray(robot["flange_xyz_mm"], dtype=float)
    new_abc = np.asarray(robot["flange_abc_deg"], dtype=float)
    for previous in payload["samples"]:
        old_robot = previous["robot"]
        xyz_delta = np.linalg.norm(
            new_xyz - np.asarray(old_robot["flange_xyz_mm"], dtype=float)
        )
        abc_delta = np.asarray(old_robot["flange_abc_deg"], dtype=float) - new_abc
        abc_delta = (abc_delta + 180.0) % 360.0 - 180.0
        if xyz_delta < 1.0 and np.linalg.norm(abc_delta) < 0.5:
            raise SystemExit(
                f"Duplicate robot pose matches sample {previous['index']}; "
                "move the robot before capturing again. No sample was written."
            )
    index = len(payload["samples"]) + 1
    image_path = image_dir / f"sample_{index:03d}.jpg"
    if not cv2.imwrite(str(image_path), image):
        raise SystemExit(f"Failed to save sample image: {image_path}")
    payload["samples"].append({
        "index": index,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "image": image_path.relative_to(data_file.parent).as_posix(),
        "detected_charuco_corners": corner_count,
        "detected_marker_count": node.last_marker_count,
        "reprojection_median_px": reprojection_median,
        "reprojection_max_px": reprojection_max,
        "camera": camera,
        "robot": robot,
        "target_to_camera": {
            "rotation_matrix": rotation.tolist(),
            "translation_m": translation.tolist(),
        },
    })
    data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved ChArUco hand-eye sample {index}: {data_file}")
    if "validation" in data_file.stem.lower():
        print(f"Validation poses: {len(payload['samples'])} (need 5 distinct poses)")
    else:
        print(f"Total poses: {len(payload['samples'])} (recommended 25-30, minimum {MIN_POSES})")


if __name__ == "__main__":
    main()
