#!/usr/bin/env python3
"""Publish a continuously annotated ChArUco image for rqt_image_view."""

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

from charuco_common import detect_charuco, detector_parameters, load_config


OUTPUT_TOPIC = "/calibration/charuco/image_annotated/compressed"


class CharucoViewer(Node):
    def __init__(self):
        super().__init__("view_charuco_board")
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.total_markers = len(self.board.ids)
        self.total_corners = (int(self.config["squares_x"]) - 1) * (
            int(self.config["squares_y"]) - 1
        )
        self.frame_count = 0
        self.publisher = self.create_publisher(
            CompressedImage, OUTPUT_TOPIC, qos_profile_sensor_data
        )
        self.subscription = self.create_subscription(
            CompressedImage,
            self.config["image_topic"],
            self.on_image,
            qos_profile_sensor_data,
        )
        self.get_logger().info(
            f"Publishing annotated ChArUco view on {OUTPUT_TOPIC}"
        )

    def on_image(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        marker_corners, marker_ids, charuco_corners, charuco_ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters
        )
        marker_count = 0 if marker_ids is None else len(marker_ids)
        corner_count = 0 if charuco_ids is None else len(charuco_ids)
        if marker_ids is not None:
            cv2.aruco.drawDetectedMarkers(frame, marker_corners, marker_ids)
        if charuco_ids is not None:
            cv2.aruco.drawDetectedCornersCharuco(
                frame, charuco_corners, charuco_ids, (0, 0, 255)
            )
        label = (
            f"markers {marker_count}/{self.total_markers}  "
            f"corners {corner_count}/{self.total_corners}"
        )
        cv2.rectangle(frame, (8, 8), (540, 58), (0, 0, 0), -1)
        cv2.putText(
            frame,
            label,
            (20, 43),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0) if corner_count >= 12 else (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
        output = self.bridge.cv2_to_compressed_imgmsg(frame, dst_format="jpg")
        output.header = msg.header
        self.publisher.publish(output)
        self.frame_count += 1
        if self.frame_count % 60 == 0:
            self.get_logger().info(label)


def main():
    rclpy.init()
    node = CharucoViewer()
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
