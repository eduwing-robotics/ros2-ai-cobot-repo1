#!/usr/bin/env python3
"""Verify the configured ChArUco board on the compressed RealSense color topic."""

import argparse

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

from charuco_common import detect_charuco, detector_parameters, load_config


class CharucoDetector(Node):
    def __init__(self, topic):
        super().__init__("detect_charuco_board")
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.subscription = self.create_subscription(
            CompressedImage, topic, self.on_image, qos_profile_sensor_data
        )
        self.get_logger().info(f"Waiting for ChArUco board on {topic}")

    def on_image(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, marker_ids, _, charuco_ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters
        )
        if marker_ids is None or charuco_ids is None:
            return
        marker_count = len(marker_ids)
        corner_count = len(charuco_ids)
        total_markers = len(self.board.ids)
        total_corners = (int(self.config["squares_x"]) - 1) * (
            int(self.config["squares_y"]) - 1
        )
        if corner_count < 8:
            return
        self.get_logger().info(
            f"Detected ChArUco board: {self.config['dictionary']}, "
            f"markers={marker_count}/{total_markers}, "
            f"corners={corner_count}/{total_corners}"
        )
        rclpy.shutdown()


def main():
    config, _, _ = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default=config["image_topic"])
    args = parser.parse_args()
    rclpy.init()
    node = CharucoDetector(args.topic)
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
