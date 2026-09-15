#!/usr/bin/env python3
"""Estimate the fixed ChArUco board center in FR5 base coordinates without motion."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage
from scipy.spatial.transform import Rotation

from charuco_common import detect_charuco, detector_parameters, load_config


ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "data" / "handeye_result.json"


def transform(rotation, translation):
    value = np.eye(4)
    value[:3, :3] = np.asarray(rotation).reshape(3, 3)
    value[:3, 3] = np.asarray(translation).reshape(3)
    return value


class Checker(Node):
    def __init__(self, frames):
        super().__init__("check_charuco_base_pose")
        self.frames = frames
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))["best"]
        self.euler_convention = result["euler_convention"]
        camera_to_flange = result["camera_to_flange"]
        self.flange_t_camera = transform(
            camera_to_flange["rotation_matrix"], camera_to_flange["translation_m"]
        )
        self.camera_matrix = None
        self.distortion = None
        self.robot_state = None
        self.image_received = False
        self.last_markers = 0
        self.last_corners = 0
        self.centers = []
        self.normals = []
        self.image_sub = self.create_subscription(
            CompressedImage,
            self.config["image_topic"],
            self.on_image,
            qos_profile_sensor_data,
        )
        self.info_sub = self.create_subscription(
            CameraInfo,
            self.config["camera_info_topic"],
            self.on_info,
            qos_profile_sensor_data,
        )
        self.robot_sub = self.create_subscription(
            RobotNonrtState,
            self.config["robot_state_topic"],
            self.on_robot,
            10,
        )
        self.status_timer = self.create_timer(3.0, self.report_status)
        self.get_logger().info("Dry run only: no robot motion commands will be sent")

    def on_info(self, msg):
        self.camera_matrix = np.asarray(msg.k, dtype=float).reshape(3, 3)
        self.distortion = np.asarray(msg.d, dtype=float)

    def on_robot(self, msg):
        self.robot_state = msg

    def on_image(self, msg):
        self.image_received = True
        if self.camera_matrix is None or self.robot_state is None:
            return
        if int(self.robot_state.robot_motion_done) != 1:
            return
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, marker_ids, charuco_corners, charuco_ids, _ = detect_charuco(
            gray,
            self.dictionary,
            self.board,
            self.parameters,
            self.camera_matrix,
            self.distortion,
        )
        self.last_markers = 0 if marker_ids is None else len(marker_ids)
        self.last_corners = 0 if charuco_ids is None else len(charuco_ids)
        if marker_ids is None or charuco_ids is None or len(charuco_ids) < 12:
            return
        values = marker_ids.flatten().tolist()
        if len(values) != len(set(values)):
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
        camera_r_board, _ = cv2.Rodrigues(rvec)
        camera_t_board = transform(camera_r_board, np.asarray(tvec).reshape(3))
        state = self.robot_state
        base_r_flange = Rotation.from_euler(
            self.euler_convention,
            [state.flange_a_cur_pos, state.flange_b_cur_pos, state.flange_c_cur_pos],
            degrees=True,
        ).as_matrix()
        base_t_flange = transform(
            base_r_flange,
            np.asarray(
                [state.flange_x_cur_pos, state.flange_y_cur_pos, state.flange_z_cur_pos]
            )
            / 1000.0,
        )
        base_t_board = base_t_flange @ self.flange_t_camera @ camera_t_board
        center_in_board = np.asarray(
            [
                self.config["squares_x"] * self.config["square_length_m"] / 2.0,
                self.config["squares_y"] * self.config["square_length_m"] / 2.0,
                0.0,
                1.0,
            ]
        )
        self.centers.append((base_t_board @ center_in_board)[:3])
        self.normals.append(base_t_board[:3, 2])
        count = len(self.centers)
        if count == 1 or count % 10 == 0:
            self.get_logger().info(f"Stable board frames: {count}/{self.frames}")
        if count >= self.frames:
            rclpy.shutdown()

    def report_status(self):
        if self.centers:
            return
        waiting = []
        if not self.image_received:
            waiting.append("compressed color image")
        if self.camera_matrix is None:
            waiting.append("camera_info")
        if self.robot_state is None:
            waiting.append("robot state")
        elif int(self.robot_state.robot_motion_done) != 1:
            waiting.append("robot to stop")
        if self.image_received and self.last_corners < 12:
            waiting.append(
                f"ChArUco board (markers={self.last_markers}, corners={self.last_corners})"
            )
        if waiting:
            self.get_logger().warning("Still waiting for: " + ", ".join(waiting))

    def report(self):
        centers = np.asarray(self.centers)
        normals = np.asarray(self.normals)
        center = np.median(centers, axis=0)
        normal = np.mean(normals, axis=0)
        normal /= np.linalg.norm(normal)
        errors_mm = np.linalg.norm(centers - center, axis=1) * 1000.0
        return center, normal, errors_mm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    rclpy.init()
    node = Checker(args.frames)
    try:
        rclpy.spin(node)
        center, normal, errors = node.report()
    except KeyboardInterrupt:
        raise SystemExit("Cancelled")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print("DRY RUN - ROBOT DID NOT MOVE")
    print("Board center in base [mm]:", np.round(center * 1000.0, 3).tolist())
    print("Board +Z normal in base:", np.round(normal, 6).tolist())
    print(
        "Frame repeatability [mm] median/max:",
        f"{np.median(errors):.3f}/{np.max(errors):.3f}",
    )


if __name__ == "__main__":
    main()
