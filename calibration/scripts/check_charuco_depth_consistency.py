#!/usr/bin/env python3
"""Compare ChArUco RGB-PnP depth with aligned D435 depth; no robot motion."""

import argparse
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from fairino_msgs.msg import RobotNonrtState
from scipy.spatial.transform import Rotation

from charuco_common import detect_charuco, detector_parameters, load_config


class DepthCheck(Node):
    def __init__(self, args):
        super().__init__("check_charuco_depth_consistency")
        self.args = args
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.k = None
        self.d = None
        self.depth = None
        self.depth_stamp = None
        self.rows = []
        self.last_robot_pose = None
        self.robot = None
        result = json.loads(args.result_file.read_text(encoding="utf-8"))["best"]
        self.euler_convention = result["euler_convention"]
        handeye = result["camera_to_flange"]
        self.t_flange_camera = np.eye(4)
        self.t_flange_camera[:3, :3] = np.asarray(handeye["rotation_matrix"])
        self.t_flange_camera[:3, 3] = np.asarray(handeye["translation_m"])
        self.last_report = time.monotonic()
        self.create_subscription(CameraInfo, self.config["camera_info_topic"], self.info_cb, qos_profile_sensor_data)
        self.create_subscription(CompressedImage, self.config["image_topic"], self.color_cb, qos_profile_sensor_data)
        self.create_subscription(Image, args.depth_topic, self.depth_cb, qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState, self.config["robot_state_topic"], self.robot_cb, 10)
        self.get_logger().info(
            f"NO MOTION: comparing marker {args.marker_id} RGB-PnP with aligned depth"
        )

    @staticmethod
    def stamp(msg):
        return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

    def info_cb(self, msg):
        self.k = np.asarray(msg.k, dtype=np.float64).reshape(3, 3)
        self.d = np.asarray(msg.d, dtype=np.float64)

    def robot_cb(self, msg):
        self.robot = msg

    def depth_cb(self, msg):
        image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        if msg.encoding in ("16UC1", "mono16"):
            image = image.astype(np.float32) * 0.001
        else:
            image = image.astype(np.float32)
        self.depth = image
        self.depth_stamp = self.stamp(msg)

    def color_cb(self, msg):
        if self.k is None or self.depth is None or self.robot is None:
            return
        if abs(self.stamp(msg) - self.depth_stamp) > self.args.max_stamp_delta:
            return
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        if self.depth.shape != frame.shape[:2]:
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        marker_corners, marker_ids, charuco_corners, charuco_ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters, self.k, self.d
        )
        if marker_ids is None or charuco_ids is None or len(charuco_ids) < 12:
            return
        ids = marker_ids.flatten().tolist()
        if self.args.marker_id not in ids:
            return
        valid, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            charuco_corners, charuco_ids, self.board, self.k, self.d, None, None
        )
        if not valid:
            return
        marker_index = np.where(self.board.ids.flatten() == self.args.marker_id)[0]
        if len(marker_index) != 1:
            return
        object_center = np.mean(self.board.objPoints[int(marker_index[0])], axis=0).reshape(1, 3)
        rotation, _ = cv2.Rodrigues(rvec)
        pnp_xyz = (rotation @ object_center[0] + np.asarray(tvec).reshape(3))
        image_center = np.mean(marker_corners[ids.index(self.args.marker_id)].reshape(4, 2), axis=0)
        u, v = np.rint(image_center).astype(int)
        radius = self.args.patch_radius
        y0, y1 = max(0, v-radius), min(self.depth.shape[0], v+radius+1)
        x0, x1 = max(0, u-radius), min(self.depth.shape[1], u+radius+1)
        values = self.depth[y0:y1, x0:x1]
        values = values[np.isfinite(values) & (values > 0.1) & (values < 3.0)]
        if len(values) < self.args.min_depth_pixels:
            return
        z = float(np.median(values))
        depth_xyz = np.array([(u-self.k[0,2])*z/self.k[0,0], (v-self.k[1,2])*z/self.k[1,1], z])
        s = self.robot
        t_base_flange = np.eye(4)
        t_base_flange[:3, :3] = Rotation.from_euler(
            self.euler_convention,
            [s.flange_a_cur_pos, s.flange_b_cur_pos, s.flange_c_cur_pos],
            degrees=True,
        ).as_matrix()
        t_base_flange[:3, 3] = np.asarray(
            [s.flange_x_cur_pos, s.flange_y_cur_pos, s.flange_z_cur_pos]
        ) / 1000.0
        self.last_robot_pose = {
            "flange_xyz_mm": [s.flange_x_cur_pos, s.flange_y_cur_pos, s.flange_z_cur_pos],
            "flange_abc_deg": [s.flange_a_cur_pos, s.flange_b_cur_pos, s.flange_c_cur_pos],
        }
        pnp_h = np.r_[pnp_xyz, 1.0]
        depth_h = np.r_[depth_xyz, 1.0]
        pnp_base = (t_base_flange @ self.t_flange_camera @ pnp_h)[:3]
        depth_base = (t_base_flange @ self.t_flange_camera @ depth_h)[:3]
        self.rows.append((pnp_xyz, depth_xyz, pnp_base, depth_base))
        n = len(self.rows)
        if n in (1, 5, 10, 20, self.args.frames):
            self.get_logger().info(f"Stable comparisons: {n}/{self.args.frames}")
        if n >= self.args.frames:
            self.report()
            rclpy.shutdown()

    def report(self):
        pnp = np.asarray([x[0] for x in self.rows]) * 1000.0
        dep = np.asarray([x[1] for x in self.rows]) * 1000.0
        pnp_base = np.asarray([x[2] for x in self.rows]) * 1000.0
        depth_base = np.asarray([x[3] for x in self.rows]) * 1000.0
        delta = dep - pnp
        print("\nCHARUCO RGB-PNP vs ALIGNED DEPTH - NO ROBOT MOTION")
        print("PnP marker XYZ median [mm]:", np.round(np.median(pnp, axis=0), 3).tolist())
        print("Depth XYZ median      [mm]:", np.round(np.median(dep, axis=0), 3).tolist())
        print("Depth - PnP median    [mm]:", np.round(np.median(delta, axis=0), 3).tolist())
        print(f"Z difference median/max abs [mm]: {np.median(delta[:,2]):.3f}/{np.max(np.abs(delta[:,2])):.3f}")
        print("PnP marker Base XYZ   [mm]:", np.round(np.median(pnp_base, axis=0), 3).tolist())
        print("Depth marker Base XYZ [mm]:", np.round(np.median(depth_base, axis=0), 3).tolist())
        print("Depth-PnP Base delta  [mm]:", np.round(np.median(depth_base-pnp_base, axis=0), 3).tolist())
        if self.args.data_file is not None:
            payload = {"schema_version": 1, "type": "depth_point_extrinsic_refinement", "samples": []}
            if self.args.data_file.exists():
                payload = json.loads(self.args.data_file.read_text(encoding="utf-8"))
            for old in payload["samples"]:
                if old["label"] == self.args.label:
                    raise RuntimeError(f"Duplicate label: {self.args.label}; no sample written")
            payload["samples"].append({
                "index": len(payload["samples"]) + 1,
                "label": self.args.label,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "marker_id": self.args.marker_id,
                "frames": len(self.rows),
                "robot": self.last_robot_pose,
                "depth_camera_xyz_m": (np.median(dep, axis=0) / 1000.0).tolist(),
                "pnp_camera_xyz_m": (np.median(pnp, axis=0) / 1000.0).tolist(),
                "depth_base_xyz_with_active_m": (np.median(depth_base, axis=0) / 1000.0).tolist(),
            })
            self.args.data_file.parent.mkdir(parents=True, exist_ok=True)
            self.args.data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Saved depth refinement sample {len(payload['samples'])}: {self.args.data_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker-id", type=int, default=8)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--depth-topic", default="/camera/camera/aligned_depth_to_color/image_raw")
    parser.add_argument("--patch-radius", type=int, default=4)
    parser.add_argument("--min-depth-pixels", type=int, default=20)
    parser.add_argument("--max-stamp-delta", type=float, default=0.20)
    parser.add_argument(
        "--result-file", type=Path,
        default=Path(__file__).resolve().parents[1] / "data/handeye_result.json"
    )
    parser.add_argument("--data-file", type=Path, default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    if args.data_file is not None and not args.label:
        parser.error("--label is required with --data-file")
    rclpy.init()
    node = DepthCheck(args)
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
