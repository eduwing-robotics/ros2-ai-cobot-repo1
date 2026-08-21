#!/usr/bin/env python3
"""TWIN MVP multi-color detector.

Copied from Farino_AIO/notebooks/hsv_depth_to_3d.py.  The original HSV,
contour, median-depth and pinhole projection flow is retained.  This isolated
copy adds per-part HSV profiles and publishes one geometry_msgs/PointStamped
per detected part type.  Coordinates are metres in the camera optical frame.

Run:
  python3 hsv_depth_multi_detector.py
  python3 hsv_depth_multi_detector.py --self-test
"""

import argparse
import json
import os
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image


DEFAULT_COLORS = os.path.join(os.path.dirname(__file__), "part_colors.json")
MIN_CONTOUR_AREA = 50
DEPTH_PATCH_HALF = 3


def load_profiles(path):
    with open(path, encoding="utf-8") as stream:
        raw = json.load(stream)

    profiles = {}
    for label, ranges in raw.items():
        if not label or not ranges:
            raise ValueError(f"Invalid empty color profile: {label!r}")
        parsed = []
        for hsv_range in ranges:
            lower = np.asarray(hsv_range["lower"], dtype=np.int16)
            upper = np.asarray(hsv_range["upper"], dtype=np.int16)
            if lower.shape != (3,) or upper.shape != (3,):
                raise ValueError(f"{label}: HSV bounds must contain three values")
            if np.any(lower < 0) or np.any(upper > [179, 255, 255]) or np.any(lower > upper):
                raise ValueError(f"{label}: invalid HSV bounds {lower.tolist()}..{upper.tolist()}")
            parsed.append((lower.astype(np.uint8), upper.astype(np.uint8)))
        profiles[label] = parsed
    return profiles


def patch_median_depth(depth, cx, cy, half=DEPTH_PATCH_HALF):
    height, width = depth.shape
    y0, y1 = max(0, cy - half), min(height, cy + half + 1)
    x0, x1 = max(0, cx - half), min(width, cx + half + 1)
    valid = depth[y0:y1, x0:x1]
    valid = valid[valid > 0]
    return None if valid.size == 0 else float(np.median(valid))


def detect_points(rgb, depth, intrinsics, profiles, min_area=MIN_CONTOUR_AREA):
    """Return the largest valid contour centre for every configured label."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    fx, fy, cx0, cy0 = intrinsics
    detections = {}

    for label, ranges in profiles.items():
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lower, upper in ranges:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) <= min_area:
            continue
        moments = cv2.moments(largest)
        if moments["m00"] == 0:
            continue
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        z = patch_median_depth(depth, cx, cy)
        if z is None:
            continue
        detections[label] = np.array([
            (cx - cx0) * z / fx,
            (cy - cy0) * z / fy,
            z,
        ])
    return detections


class HSVDepthMultiDetector(Node):
    def __init__(self, profiles, topic_prefix):
        super().__init__("twin_mvp_hsv_depth_detector")
        self.bridge = CvBridge()
        self.profiles = profiles
        self.color = None
        self.depth = None
        self.intrinsics = None
        self.last_log = {}
        self._point_publishers = {
            label: self.create_publisher(PointStamped, f"{topic_prefix}/{label}/point", 10)
            for label in profiles
        }

        self.create_subscription(Image, "/camera/camera/color/image_raw", self.on_color, 10)
        self.create_subscription(
            Image, "/camera/camera/aligned_depth_to_color/image_raw", self.on_depth, 10)
        self.create_subscription(
            CameraInfo, "/camera/camera/aligned_depth_to_color/camera_info", self.on_info, 1)
        self.create_timer(0.1, self.detect)

    def on_color(self, message):
        self.color = self.bridge.imgmsg_to_cv2(message, desired_encoding="rgb8")

    def on_depth(self, message):
        self.depth = np.frombuffer(message.data, dtype=np.uint16).reshape(
            message.height, message.width)

    def on_info(self, message):
        self.intrinsics = (message.k[0], message.k[4], message.k[2], message.k[5])

    def detect(self):
        if self.color is None or self.depth is None or self.intrinsics is None:
            return
        if self.color.shape[:2] != self.depth.shape:
            self.get_logger().error("Color/depth dimensions do not match")
            return

        now = self.get_clock().now()
        for label, xyz_mm in detect_points(
                self.color, self.depth, self.intrinsics, self.profiles).items():
            message = PointStamped()
            message.header.stamp = now.to_msg()
            message.header.frame_id = "sim_camera_optical_frame"
            message.point.x, message.point.y, message.point.z = xyz_mm / 1000.0
            self._point_publishers[label].publish(message)

            wall_time = time.monotonic()
            if wall_time - self.last_log.get(label, 0.0) >= 1.0:
                self.get_logger().info(
                    f"{label}: camera xyz(mm)="
                    f"{xyz_mm[0]:.1f}, {xyz_mm[1]:.1f}, {xyz_mm[2]:.1f}")
                self.last_log[label] = wall_time


def self_test(profiles):
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    rgb[20:42, 30:52] = [0, 0, 255]  # blue RGB -> chip profile
    depth = np.full((100, 100), 500, dtype=np.uint16)
    points = detect_points(rgb, depth, (100.0, 100.0, 50.0, 50.0), profiles)
    assert "chip" in points, points
    assert np.allclose(points["chip"], [-50.0, -100.0, 500.0]), points["chip"]
    print("self-test passed:", points["chip"].tolist())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--colors", default=DEFAULT_COLORS)
    parser.add_argument("--topic-prefix", default="/fr5_vision")
    parser.add_argument("--self-test", action="store_true")
    args, ros_args = parser.parse_known_args()
    profiles = load_profiles(args.colors)

    if args.self_test:
        self_test(profiles)
        return

    rclpy.init(args=ros_args)
    node = HSVDepthMultiDetector(profiles, args.topic_prefix.rstrip("/"))
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
