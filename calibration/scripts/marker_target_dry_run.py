#!/usr/bin/env python3
"""Detect one ArUco marker and estimate its position in the FR5 base frame.

This node is a dry run by default.  A motion command is sent only when both
``--move`` and ``--confirm-move`` are explicitly supplied.  It uses the
compressed color image, the calibrated color camera intrinsics, the current
flange pose, and the saved camera->flange Hand-Eye result.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
import yaml
from cv_bridge import CvBridge
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, CompressedImage


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "charuco_board.yaml"
RESULT_PATH = ROOT / "data" / "handeye_result.json"
DEFAULT_OUTPUT = ROOT / "data" / "marker_target_last.json"
DEFAULT_ANNOTATED_TOPIC = "/calibration/marker_target/image_annotated/compressed"
ROBOT_SETTLE_SECONDS = 1.0
STABLE_TRANSLATION_MM = 0.25
STABLE_ROTATION_DEG = 0.10


def make_transform(rotation, translation):
    value = np.eye(4, dtype=float)
    value[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    value[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return value


def format_transform(name, value):
    matrix = np.asarray(value, dtype=float).reshape(4, 4)
    rows = ["  " + np.array2string(row, precision=6, suppress_small=True) for row in matrix]
    xyz_mm = matrix[:3, 3] * 1000.0
    return (
        f"{name}:\n" + "\n".join(rows) + "\n"
        f"  XYZ [mm]: {np.round(xyz_mm, 3).tolist()}"
    )


def align_tool_to_board(current_r_tool, marker_normal_base):
    """Align Tool +Z toward the board while preserving finger yaw."""
    desired_tool_z = -np.asarray(marker_normal_base, dtype=float)
    desired_tool_z /= max(np.linalg.norm(desired_tool_z), 1e-12)
    desired_tool_x = current_r_tool[:, 0] - np.dot(
        current_r_tool[:, 0], desired_tool_z
    ) * desired_tool_z
    desired_tool_x /= max(np.linalg.norm(desired_tool_x), 1e-12)
    desired_tool_y = np.cross(desired_tool_z, desired_tool_x)
    desired_tool_y /= max(np.linalg.norm(desired_tool_y), 1e-12)
    desired_tool_x = np.cross(desired_tool_y, desired_tool_z)
    return np.column_stack([desired_tool_x, desired_tool_y, desired_tool_z])


def detect_markers(gray, dictionary, parameters):
    if hasattr(cv2.aruco, "ArucoDetector"):
        return cv2.aruco.ArucoDetector(dictionary, parameters).detectMarkers(gray)
    return cv2.aruco.detectMarkers(gray, dictionary, parameters=parameters)


def marker_pose(corners, marker_length_m, camera_matrix, distortion):
    """Return marker->camera rvec/tvec for one marker."""
    image_points = np.asarray(corners, dtype=np.float32).reshape(4, 2)
    half = marker_length_m / 2.0
    object_points = np.array(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np.float32,
    )

    if hasattr(cv2.aruco, "estimatePoseSingleMarkers"):
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            image_points.reshape(1, 4, 2),
            marker_length_m,
            camera_matrix,
            distortion,
        )
        return rvecs[0].reshape(3), tvecs[0].reshape(3)

    flag = getattr(cv2, "SOLVEPNP_IPPE_SQUARE", cv2.SOLVEPNP_ITERATIVE)
    ok, rvec, tvec = cv2.solvePnP(
        object_points,
        image_points,
        camera_matrix,
        distortion,
        flags=flag,
    )
    if not ok:
        raise RuntimeError("solvePnP failed")
    return rvec.reshape(3), tvec.reshape(3)


class MarkerTargetDryRun(Node):
    def __init__(self, args):
        super().__init__("marker_target_dry_run")
        self.args = args
        self.bridge = CvBridge()

        self.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        dictionary_id = getattr(cv2.aruco, self.config["dictionary"])
        self.dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        self.board = cv2.aruco.CharucoBoard_create(
            int(self.config["squares_x"]),
            int(self.config["squares_y"]),
            float(self.config["square_length_m"]),
            float(self.config["marker_length_m"]),
            self.dictionary,
        )
        if hasattr(cv2.aruco, "DetectorParameters_create"):
            self.detector_parameters = cv2.aruco.DetectorParameters_create()
        else:
            self.detector_parameters = cv2.aruco.DetectorParameters()

        result_payload = json.loads(args.result_file.read_text(encoding="utf-8"))
        self.result_status = str(result_payload.get("status", "legacy_active_result"))
        self.result_sha256 = hashlib.sha256(args.result_file.read_bytes()).hexdigest()
        result = result_payload["best"]
        self.euler_convention = result["euler_convention"]
        camera_to_flange = result["camera_to_flange"]
        self.flange_t_camera = make_transform(
            camera_to_flange["rotation_matrix"],
            camera_to_flange["translation_m"],
        )

        self.marker_id = int(args.marker_id)
        self.marker_length_m = float(args.marker_length_mm) / 1000.0
        board_ids = np.asarray(self.board.ids).reshape(-1).astype(int).tolist()
        if self.marker_id not in board_ids:
            raise ValueError(
                f"Marker ID {self.marker_id} is not in this ChArUco board: {board_ids}"
            )
        marker_index = board_ids.index(self.marker_id)
        self.marker_center_board = np.mean(
            np.asarray(self.board.objPoints[marker_index], dtype=float).reshape(4, 3),
            axis=0,
        )
        self.approach_offset_m = float(args.approach_offset_mm) / 1000.0
        correction = self.config.get("tcp_target_correction_tool_mm", {})
        self.tcp_target_correction_tool_m = np.asarray(
            [
                float(correction.get("x", 0.0)),
                float(correction.get("y", 0.0)),
                float(correction.get("z", 0.0)),
            ],
            dtype=float,
        ) / 1000.0
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
        self.robot_state = None
        self.robot_stable_since = None
        self.last_stationary_flange_pose = None
        self.image_received = False
        self.last_detection = None
        self.last_marker_count = 0
        self.last_charuco_corner_count = 0
        self.samples = []
        self.last_report_time = 0.0
        self.last_status_time = 0.0
        self.reported_once = False
        self.move_pending = False
        self.move_sent = False
        self.motion_client = None
        self.motion_phase = None
        self.move_target = None
        self.shutdown_timer = None

        image_topic = args.image_topic or self.config["image_topic"]
        camera_info_topic = args.camera_info_topic or self.config["camera_info_topic"]
        robot_state_topic = args.robot_state_topic or self.config["robot_state_topic"]

        self.create_subscription(
            CompressedImage,
            image_topic,
            self.on_image,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            CameraInfo,
            camera_info_topic,
            self.on_camera_info,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            RobotNonrtState,
            robot_state_topic,
            self.on_robot_state,
            10,
        )
        self.annotated_pub = self.create_publisher(
            CompressedImage,
            args.annotated_topic,
            qos_profile_sensor_data,
        )
        self.create_timer(1.0, self.report_status)
        if args.move:
            self.create_timer(0.1, self.process_move_request)

        self.get_logger().info(
            f"Hand-Eye result: {args.result_file} | status={self.result_status} | "
            f"sha256={self.result_sha256[:12]}..."
        )

        if args.move:
            self.get_logger().info(
                f"MOTION ENABLED: marker ID={self.marker_id}, "
                "target from full ChArUco-board pose, "
                "two-flag confirmation accepted; staged approach only",
            )
        else:
            self.get_logger().info(
                f"DRY RUN only: marker ID={self.marker_id}, "
                "target from full ChArUco-board pose, "
                "no robot motion commands",
            )
        self.get_logger().info("Waiting for marker, camera info, and stationary robot state")

    def on_camera_info(self, msg):
        if self.intrinsic_override is None:
            self.camera_matrix = np.asarray(msg.k, dtype=float).reshape(3, 3)
            self.distortion = np.asarray(msg.d, dtype=float)
            return
        expected = self.intrinsic_override["size"]
        received = (int(msg.width), int(msg.height))
        if received != expected:
            self.get_logger().error(
                f"Intrinsic override resolution {expected} does not match CameraInfo {received}"
            )
            self.camera_matrix = None
            self.distortion = None
            return
        self.camera_matrix = self.intrinsic_override["camera_matrix"]
        self.distortion = self.intrinsic_override["distortion"]

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
            if self.samples and not self.reported_once:
                self.samples.clear()
                self.last_detection = None
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

    def on_image(self, msg):
        self.image_received = True
        try:
            frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        except Exception as exc:  # pragma: no cover - hardware-dependent
            self.get_logger().warning(f"Could not decode image: {exc}")
            return

        annotated = frame.copy()
        if self.reported_once:
            cv2.putText(
                annotated,
                "TARGET LOCKED - image no longer changes the target",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 165, 255),
                2,
                cv2.LINE_AA,
            )
            self.publish_annotated(annotated, msg.header)
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        marker_corners, marker_ids, _ = detect_markers(
            gray,
            self.dictionary,
            self.detector_parameters,
        )

        selected_index = None
        if marker_ids is not None:
            ids = marker_ids.reshape(-1).tolist()
            for index, value in enumerate(ids):
                if int(value) == self.marker_id:
                    selected_index = index
                    break
        self.last_marker_count = 0 if marker_ids is None else len(marker_ids)

        charuco_corners = None
        charuco_ids = None
        if marker_ids is not None and self.camera_matrix is not None:
            count, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                marker_corners,
                marker_ids,
                gray,
                self.board,
                cameraMatrix=self.camera_matrix,
                distCoeffs=self.distortion,
            )
            if count is None or int(count) == 0:
                charuco_corners, charuco_ids = None, None
        self.last_charuco_corner_count = (
            0 if charuco_ids is None else len(charuco_ids)
        )
        if charuco_ids is not None:
            cv2.aruco.drawDetectedCornersCharuco(
                annotated, charuco_corners, charuco_ids, (0, 0, 255)
            )

        detection = None
        if (
            selected_index is not None
            and self.camera_matrix is not None
            and charuco_ids is not None
            and len(charuco_ids) >= int(self.args.min_charuco_corners)
        ):
            try:
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
                    raise RuntimeError("estimatePoseCharucoBoard failed")
                camera_r_board, _ = cv2.Rodrigues(rvec)
                camera_t_board = make_transform(camera_r_board, np.asarray(tvec).reshape(3))

                state = self.robot_state
                if state is not None and self.robot_is_settled():
                    base_r_flange = Rotation.from_euler(
                        self.euler_convention,
                        [
                            state.flange_a_cur_pos,
                            state.flange_b_cur_pos,
                            state.flange_c_cur_pos,
                        ],
                        degrees=True,
                    ).as_matrix()
                    base_t_flange = make_transform(
                        base_r_flange,
                        np.asarray(
                            [
                                state.flange_x_cur_pos,
                                state.flange_y_cur_pos,
                                state.flange_z_cur_pos,
                            ],
                            dtype=float,
                        )
                        / 1000.0,
                    )
                    base_t_camera = base_t_flange @ self.flange_t_camera
                    base_t_board = base_t_camera @ camera_t_board
                    marker_center_board_h = np.append(self.marker_center_board, 1.0)
                    marker_center_camera = (camera_t_board @ marker_center_board_h)[:3]
                    marker_center_base = (base_t_board @ marker_center_board_h)[:3]
                    marker_normal_base = base_t_board[:3, 2].copy()
                    marker_normal_base /= max(np.linalg.norm(marker_normal_base), 1e-12)
                    to_camera = base_t_camera[:3, 3] - marker_center_base
                    if float(np.dot(marker_normal_base, to_camera)) < 0.0:
                        marker_normal_base *= -1.0
                    camera_side_approach = (
                        marker_center_base + marker_normal_base * self.approach_offset_m
                    )
                    detection = {
                        "aruco_rvec": np.asarray(rvec).reshape(3).tolist(),
                        "aruco_tvec_m": np.asarray(tvec).reshape(3).tolist(),
                        "camera_center_m": marker_center_camera.tolist(),
                        "base_center_m": marker_center_base.tolist(),
                        "marker_z_normal_base": marker_normal_base.tolist(),
                        "camera_side_approach_m": camera_side_approach.tolist(),
                        "detected_markers": int(self.last_marker_count),
                        "detected_charuco_corners": int(self.last_charuco_corner_count),
                        "flange_xyz_mm": [
                            float(state.flange_x_cur_pos),
                            float(state.flange_y_cur_pos),
                            float(state.flange_z_cur_pos),
                        ],
                        "T_base_flange": base_t_flange.tolist(),
                        "T_flange_camera": self.flange_t_camera.tolist(),
                        "T_camera_board": camera_t_board.tolist(),
                        "T_base_board": base_t_board.tolist(),
                    }
            except Exception as exc:  # pragma: no cover - hardware-dependent
                self.get_logger().warning(f"ChArUco target pose estimation failed: {exc}")

        if selected_index is not None:
            selected = np.asarray(marker_corners[selected_index]).reshape(4, 2).astype(int)
            cv2.polylines(annotated, [selected], True, (0, 255, 0), 3)
            center_px = tuple(np.mean(selected, axis=0).astype(int).tolist())
            cv2.circle(annotated, center_px, 7, (0, 0, 255), -1)
            cv2.putText(
                annotated,
                f"TARGET ID {self.marker_id}",
                (center_px[0] + 10, center_px[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            if detection is not None:
                base_mm = np.asarray(detection["base_center_m"]) * 1000.0
                cv2.putText(
                    annotated,
                    "base center [%.1f, %.1f, %.1f] mm"
                    % (base_mm[0], base_mm[1], base_mm[2]),
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
        else:
            cv2.putText(
                annotated,
                f"waiting for marker ID {self.marker_id}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )

        if detection is not None:
            self.last_detection = detection
            self.samples.append(detection)
            self.samples = self.samples[-max(1, int(self.args.frames)) :]
            if len(self.samples) >= max(1, int(self.args.frames)):
                now = time.monotonic()
                if now - self.last_report_time > 1.0:
                    self.report_stable_target()
                    self.last_report_time = now

        self.publish_annotated(annotated, msg.header)

    def publish_annotated(self, frame, header):
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(self.args.jpeg_quality)],
        )
        if not ok:
            return
        out = CompressedImage()
        out.header = header
        out.format = "jpeg"
        out.data = encoded.tobytes()
        self.annotated_pub.publish(out)

    def report_stable_target(self):
        if self.reported_once:
            return
        centers = np.asarray([sample["base_center_m"] for sample in self.samples])
        normals = np.asarray([sample["marker_z_normal_base"] for sample in self.samples])
        center = np.median(centers, axis=0)
        normal = np.mean(normals, axis=0)
        normal /= max(np.linalg.norm(normal), 1e-12)
        errors_mm = np.linalg.norm(centers - center, axis=1) * 1000.0
        if self.args.approach_frame == "base_z":
            approach = center + np.asarray([0.0, 0.0, self.approach_offset_m])
        else:
            # The selected board normal faces the camera, so this remains on
            # the non-contact camera side of the target surface.
            approach = center + normal * self.approach_offset_m
        state = self.robot_state
        current_r_tool = Rotation.from_euler(
            self.euler_convention,
            [state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos],
            degrees=True,
        ).as_matrix()
        desired_r_tool = align_tool_to_board(current_r_tool, normal)
        correction_base = desired_r_tool @ self.tcp_target_correction_tool_m
        target_position = approach + correction_base
        reference = min(
            self.samples,
            key=lambda sample: np.linalg.norm(
                np.asarray(sample["base_center_m"], dtype=float) - center
            ),
        )
        base_t_marker = np.asarray(reference["T_base_board"], dtype=float)
        base_t_marker = base_t_marker.copy()
        base_t_marker[:3, 3] = center
        base_t_target = make_transform(desired_r_tool, target_position)
        status = {
            "mode": "move_enabled" if self.args.move else "dry_run_no_robot_motion",
            "handeye_result_file": str(self.args.result_file),
            "handeye_result_status": self.result_status,
            "handeye_result_sha256": self.result_sha256,
            "intrinsics_file": (
                None if self.args.intrinsics_file is None else str(self.args.intrinsics_file)
            ),
            "marker_id": self.marker_id,
            "marker_length_mm": self.marker_length_m * 1000.0,
            "samples": len(self.samples),
            "pose_source": "full_charuco_board",
            "approach_frame": self.args.approach_frame,
            "detected_markers": int(self.samples[-1]["detected_markers"]),
            "detected_charuco_corners": int(
                self.samples[-1]["detected_charuco_corners"]
            ),
            "base_marker_center_mm": (center * 1000.0).tolist(),
            "marker_z_normal_base": normal.tolist(),
            "approach_point_mm": (approach * 1000.0).tolist(),
            # Retained for readers of older output files. Use
            # approach_point_mm + approach_frame in new code.
            "camera_side_approach_mm": (approach * 1000.0).tolist(),
            "tcp_target_correction_tool_mm": (
                self.tcp_target_correction_tool_m * 1000.0
            ).tolist(),
            "tcp_target_correction_resolved_base_mm": (
                correction_base * 1000.0
            ).tolist(),
            "target_tcp_approach_mm": (target_position * 1000.0).tolist(),
            "aruco_rvec": reference["aruco_rvec"],
            "aruco_tvec_m": reference["aruco_tvec_m"],
            "T_base_flange": reference["T_base_flange"],
            "T_flange_camera": reference["T_flange_camera"],
            "T_camera_board": reference["T_camera_board"],
            "T_base_marker": base_t_marker.tolist(),
            "T_base_target": base_t_target.tolist(),
            "center_jitter_median_mm": float(np.median(errors_mm)),
            "center_jitter_max_mm": float(np.max(errors_mm)),
            "annotated_topic": self.args.annotated_topic,
        }
        self.args.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.args.output_file.write_text(json.dumps(status, indent=2), encoding="utf-8")

        if not self.reported_once:
            self.get_logger().info(
                f"Stable target acquired: {len(self.samples)} frames"
            )
            self.get_logger().info(
                f"Marker center in base [mm]: "
                f"{np.round(center * 1000.0, 3).tolist()}"
            )
            self.get_logger().info(
                f"Approach ({self.args.approach_frame}, "
                f"{self.approach_offset_m * 1000.0:g} mm) "
                f"in base [mm]: {np.round(approach * 1000.0, 3).tolist()}"
            )
            self.get_logger().info(
                f"TCP correction in Tool [mm]: "
                f"{np.round(self.tcp_target_correction_tool_m * 1000.0, 3).tolist()}"
            )
            self.get_logger().info(
                f"TCP correction resolved in Base [mm]: "
                f"{np.round(correction_base * 1000.0, 3).tolist()}"
            )
            self.get_logger().info(
                f"Target TCP approach in Base [mm]: "
                f"{np.round(target_position * 1000.0, 3).tolist()}"
            )
            self.get_logger().info(
                "[Camera] ArUco/ChArUco board pose: "
                f"rvec={np.round(reference['aruco_rvec'], 6).tolist()}, "
                f"tvec [m]={np.round(reference['aruco_tvec_m'], 6).tolist()}"
            )
            for label, matrix in (
                ("[Robot] T_base_flange", reference["T_base_flange"]),
                ("[HandEye] T_flange_camera", reference["T_flange_camera"]),
                ("[Camera] T_camera_board", reference["T_camera_board"]),
                ("[Calculated] T_base_marker", base_t_marker),
                ("[Target] T_base_target", base_t_target),
            ):
                self.get_logger().info(format_transform(label, matrix))
            self.get_logger().info(
                f"Center jitter median/max [mm]: "
                f"{float(np.median(errors_mm)):.3f}/"
                f"{float(np.max(errors_mm)):.3f}"
            )
            if self.args.move:
                self.get_logger().info(
                    "Motion is authorized; waiting for stable-target safety checks"
                )
                self.move_target = {
                    "approach_m": target_position.tolist(),
                    "marker_center_m": center.tolist(),
                    "normal_base": normal.tolist(),
                    "jitter_max_mm": float(np.max(errors_mm)),
                }
                self.move_pending = True
            else:
                self.get_logger().info(
                    f"No robot motion command was sent. Output: "
                    f"{self.args.output_file}"
                )
                self.shutdown_timer = self.create_timer(
                    0.5, self.shutdown_after_move
                )
            self.reported_once = True

    def process_move_request(self):
        if not self.move_pending or self.move_sent or self.motion_phase is not None:
            return
        state = self.robot_state
        if state is None or int(state.robot_motion_done) != 1:
            self.get_logger().warning("Move postponed: robot is not stationary")
            return
        if int(state.robot_mode) != 0:
            self.get_logger().error(
                f"Move cancelled: robot_mode={int(state.robot_mode)} is manual mode. "
                "Restart the command server if an earlier MoveCart is pending, "
                "then select AUTO mode (robot_mode=0) and enable the robot."
            )
            self.move_pending = False
            return
        if int(getattr(state, "emg", 0)) != 0:
            self.get_logger().error("Move cancelled: emergency-stop signal is active")
            self.move_pending = False
            return
        if int(state.tool_num) != int(self.args.tool_id):
            self.get_logger().error(
                f"Move cancelled: active tool is {int(state.tool_num)}, "
                f"but --tool-id is {int(self.args.tool_id)}"
            )
            self.move_pending = False
            return
        if float(self.move_target["jitter_max_mm"]) > float(self.args.max_jitter_mm):
            self.get_logger().error(
                f"Move cancelled: target jitter is "
                f"{float(self.move_target['jitter_max_mm']):.2f} mm, "
                f"limit is {float(self.args.max_jitter_mm):.2f} mm"
            )
            self.move_pending = False
            return

        target_mm = np.asarray(self.move_target["approach_m"], dtype=float) * 1000.0
        normal = np.asarray(self.move_target["normal_base"], dtype=float)
        minimum_normal_z = float(np.cos(np.deg2rad(self.args.max_board_tilt_deg)))
        if float(normal[2]) < minimum_normal_z:
            self.get_logger().error(
                f"Move cancelled: board normal {np.round(normal, 4).tolist()} "
                f"is tilted more than {self.args.max_board_tilt_deg:g} deg"
            )
            self.move_pending = False
            return
        current_mm = np.asarray(
            [state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos],
            dtype=float,
        )
        distance_mm = float(np.linalg.norm(target_mm - current_mm))
        if distance_mm > float(self.args.max_distance_mm):
            self.get_logger().error(
                f"Move cancelled: target is {distance_mm:.1f} mm away, "
                f"limit is {float(self.args.max_distance_mm):.1f} mm"
            )
            self.move_pending = False
            return

        current_r_tool = Rotation.from_euler(
            self.euler_convention,
            [state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos],
            degrees=True,
        ).as_matrix()
        tool_z = current_r_tool[:, 2]
        alignment = float(np.dot(tool_z, -normal))
        minimum_alignment = float(
            np.cos(np.deg2rad(self.args.max_tool_tilt_deg))
        )
        if alignment < minimum_alignment:
            angle_deg = float(np.degrees(np.arccos(np.clip(alignment, -1.0, 1.0))))
            self.get_logger().error(
                f"Move cancelled: Tool +Z is {angle_deg:.1f} deg from the board; "
                f"limit is {self.args.max_tool_tilt_deg:g} deg"
            )
            self.move_pending = False
            return

        desired_r_tool = align_tool_to_board(current_r_tool, normal)
        desired_orientation = Rotation.from_matrix(desired_r_tool).as_euler(
            self.euler_convention, degrees=True
        )
        orientation_change_deg = float(
            np.degrees(
                Rotation.from_matrix(current_r_tool.T @ desired_r_tool).magnitude()
            )
        )

        if self.motion_client is None:
            self.motion_client = self.create_client(
                RemoteCmdInterface, "/fairino_remote_command_service"
            )
        if not self.motion_client.service_is_ready():
            if not self.motion_client.wait_for_service(timeout_sec=0.1):
                self.get_logger().warning(
                    "Move waiting: /fairino_remote_command_service is not available"
                )
                return

        # Use three safe stages: raise if needed, move horizontally over the
        # target, then descend vertically to the non-contact approach point.
        current_orientation = [
            float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos),
            float(state.cart_c_cur_pos),
        ]
        orientation = desired_orientation.astype(float).tolist()
        safe_z = max(
            float(current_mm[2]),
            float(target_mm[2]) + float(self.args.safe_clearance_mm),
        )
        waypoints = []
        if safe_z - float(current_mm[2]) > 1.0:
            waypoints.append(
                {
                    "name": "vertical raise",
                    "pose": [float(current_mm[0]), float(current_mm[1]), safe_z]
                    + current_orientation,
                    "speed": int(self.args.descent_speed_percent),
                }
            )
        if orientation_change_deg > 0.5:
            waypoints.append(
                {
                    "name": "vertical tool alignment",
                    "pose": [float(current_mm[0]), float(current_mm[1]), safe_z]
                    + orientation,
                    "speed": int(self.args.descent_speed_percent),
                }
            )
        waypoints.append(
            {
                "name": "horizontal positioning",
                "pose": [float(target_mm[0]), float(target_mm[1]), safe_z] + orientation,
                "speed": int(self.args.speed_percent),
            }
        )
        if safe_z - float(target_mm[2]) > 1.0:
            waypoints.append(
                {
                    "name": "vertical approach",
                    "pose": [float(target_mm[0]), float(target_mm[1]), float(target_mm[2])]
                    + orientation,
                    "speed": int(self.args.descent_speed_percent),
                }
            )
        self.move_target["waypoints"] = waypoints
        self.move_target["waypoint_index"] = 0
        self.move_target["distance_mm"] = distance_mm
        speed_cmd = f"SetSpeed({int(self.args.speed_percent)})"
        self.motion_phase = "set_speed"
        self.move_pending = False
        self.get_logger().info(
            f"Sending {speed_cmd}; staged target distance={distance_mm:.1f} mm, "
            f"target TCP/base [mm]={np.round(target_mm, 2).tolist()}, "
            f"safe Z={safe_z:.1f} mm, tool alignment={orientation_change_deg:.1f} deg, "
            f"target orientation={np.round(desired_orientation, 3).tolist()}"
        )
        self.send_motion_command(speed_cmd)

    def send_motion_command(self, command):
        request = RemoteCmdInterface.Request()
        request.cmd_str = command
        future = self.motion_client.call_async(request)
        future.add_done_callback(self.on_motion_response)

    def send_next_waypoint(self):
        index = int(self.move_target["waypoint_index"])
        waypoints = self.move_target["waypoints"]
        if index >= len(waypoints):
            self.get_logger().info(
                "Staged marker approach completed. The node did not move to the "
                "marker surface and did not actuate the gripper."
            )
            self.move_sent = True
            self.motion_phase = None
            self.shutdown_timer = self.create_timer(0.5, self.shutdown_after_move)
            return
        waypoint = waypoints[index]
        pose = waypoint["pose"]
        speed = int(waypoint["speed"])
        move_cmd = (
            f"MoveCart({pose[0]:.3f},{pose[1]:.3f},{pose[2]:.3f},"
            f"{pose[3]:.3f},{pose[4]:.3f},{pose[5]:.3f},"
            f"{int(self.args.tool_id)},{int(self.args.user_id)},"
            f"{speed},{speed},{speed},-1,-1)"
        )
        self.motion_phase = "move_cart"
        self.get_logger().info(
            f"Stage {index + 1}/{len(waypoints)} ({waypoint['name']}): "
            f"{move_cmd}"
        )
        self.send_motion_command(move_cmd)

    def shutdown_after_move(self):
        if self.shutdown_timer is not None:
            self.shutdown_timer.cancel()
        if rclpy.ok():
            rclpy.shutdown()

    def on_motion_response(self, future):
        try:
            response = future.result()
            result = str(response.cmd_res)
        except Exception as exc:  # pragma: no cover - hardware-dependent
            self.get_logger().error(f"Motion service failed: {exc}")
            self.motion_phase = None
            self.move_sent = True
            return

        if result != "0":
            self.get_logger().error(
                f"FR5 rejected command during {self.motion_phase}: result={result}"
            )
            self.motion_phase = None
            self.move_sent = True
            return

        if self.motion_phase == "set_speed":
            self.send_next_waypoint()
            return

        if self.motion_phase == "move_cart":
            self.move_target["waypoint_index"] += 1
            self.send_next_waypoint()

    def report_status(self):
        now = time.monotonic()
        if now - self.last_status_time < 2.5:
            return
        self.last_status_time = now
        waiting = []
        if not self.image_received:
            waiting.append("compressed color image")
        if self.camera_matrix is None:
            waiting.append("camera_info")
        if self.robot_state is None:
            waiting.append("robot state")
        elif not self.robot_is_settled():
            waiting.append(f"robot stationary for {ROBOT_SETTLE_SECONDS:.1f} s")
        if self.image_received and self.last_detection is None:
            waiting.append(
                f"ChArUco target ID {self.marker_id} "
                f"(markers={self.last_marker_count}, "
                f"corners={self.last_charuco_corner_count}, "
                f"need>={int(self.args.min_charuco_corners)})"
            )
        if waiting:
            self.get_logger().warning("Still waiting for: " + ", ".join(waiting))


def parse_args():
    parser = argparse.ArgumentParser(
        description="ChArUco marker-center targeting in the FR5 base frame."
    )
    parser.add_argument("--marker-id", type=int, required=True)
    parser.add_argument(
        "--marker-length-mm",
        type=float,
        default=None,
        help="Compatibility option; board dimensions come from the ChArUco config.",
    )
    parser.add_argument("--approach-offset-mm", type=float, default=100.0)
    parser.add_argument(
        "--approach-frame",
        choices=("base_z", "board_normal"),
        default="base_z",
        help="Apply the safety offset along Robot Base +Z (default) or the board normal.",
    )
    parser.add_argument("--frames", type=int, default=15)
    parser.add_argument("--min-charuco-corners", type=int, default=12)
    parser.add_argument("--dry-run", action="store_true", help="Explicit no-motion mode (default).")
    parser.add_argument("--execute", action="store_true", help="Alias for --move; still requires --confirm-move.")
    parser.add_argument(
        "--move",
        action="store_true",
        help="Enable one low-speed MoveCart to the camera-side approach point.",
    )
    parser.add_argument(
        "--confirm-move",
        action="store_true",
        help="Required together with --move; explicit second motion confirmation.",
    )
    parser.add_argument("--tool-id", type=int, default=1)
    parser.add_argument("--user-id", type=int, default=0)
    parser.add_argument("--speed-percent", type=int, default=40)
    parser.add_argument("--descent-speed-percent", type=int, default=15)
    parser.add_argument("--safe-clearance-mm", type=float, default=50.0)
    parser.add_argument("--max-jitter-mm", type=float, default=2.0)
    parser.add_argument("--max-board-tilt-deg", type=float, default=20.0)
    parser.add_argument("--max-tool-tilt-deg", type=float, default=20.0)
    parser.add_argument("--max-distance-mm", type=float, default=600.0)
    parser.add_argument("--image-topic", default=None)
    parser.add_argument("--camera-info-topic", default=None)
    parser.add_argument("--robot-state-topic", default=None)
    parser.add_argument("--annotated-topic", default=DEFAULT_ANNOTATED_TOPIC)
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--result-file", type=Path, default=RESULT_PATH)
    parser.add_argument("--intrinsics-file", type=Path, default=None)
    parser.add_argument(
        "--allow-candidate-motion",
        action="store_true",
        help=(
            "Third explicit acknowledgement required to move with a result whose "
            "file/status says candidate or not active. Dry-run never needs this flag."
        ),
    )
    args = parser.parse_args()
    if args.dry_run and (args.move or args.execute):
        parser.error("--dry-run cannot be combined with --move or --execute")
    if args.execute:
        args.move = True
    if args.marker_length_mm is None:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        args.marker_length_mm = float(config["marker_length_m"]) * 1000.0
    if args.move != args.confirm_move:
        parser.error("실제 이동에는 --move와 --confirm-move를 둘 다 지정해야 합니다.")
    if not args.result_file.is_file():
        parser.error(f"Hand-Eye result file not found: {args.result_file}")
    try:
        result_payload = json.loads(args.result_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Cannot read Hand-Eye result: {exc}")
    result_status = str(result_payload.get("status", "")).lower()
    candidate_result = (
        "candidate" in args.result_file.stem.lower()
        or "candidate" in result_status
        or "not_active" in result_status
    )
    if args.move and candidate_result and not args.allow_candidate_motion:
        parser.error(
            "Candidate/non-active Hand-Eye results are dry-run only. After independent "
            "validation, add --allow-candidate-motion as an explicit third acknowledgement."
        )
    if not 1 <= args.tool_id <= 15:
        parser.error("--tool-id must be in the FR5 tool range 1..15")
    if not 1 <= args.speed_percent <= 40:
        parser.error("--speed-percent must be between 1 and 40 for this safety test")
    if not 1 <= args.descent_speed_percent <= 25:
        parser.error("--descent-speed-percent must be between 1 and 25")
    if not 6 <= args.min_charuco_corners <= 24:
        parser.error("--min-charuco-corners must be between 6 and 24")
    if args.safe_clearance_mm < 20:
        parser.error("--safe-clearance-mm must be at least 20")
    if args.max_jitter_mm <= 0:
        parser.error("--max-jitter-mm must be positive")
    if args.max_distance_mm <= 0:
        parser.error("--max-distance-mm must be positive")
    return args


def main():
    args = parse_args()
    rclpy.init()
    node = MarkerTargetDryRun(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
