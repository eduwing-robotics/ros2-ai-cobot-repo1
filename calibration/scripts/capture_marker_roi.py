#!/usr/bin/env python3
"""Save one full-resolution color frame and a crop around an ArUco marker."""

import argparse
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class CaptureMarkerRoi(Node):
    def __init__(self, args):
        super().__init__('capture_marker_roi')
        self.args = args
        self.bridge = CvBridge()
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_50)
        parameters = (
            cv2.aruco.DetectorParameters_create()
            if hasattr(cv2.aruco, 'DetectorParameters_create')
            else cv2.aruco.DetectorParameters()
        )
        self.dictionary = dictionary
        self.parameters = parameters
        self.detector = (
            cv2.aruco.ArucoDetector(dictionary, parameters)
            if hasattr(cv2.aruco, 'ArucoDetector')
            else None
        )
        self.create_subscription(
            CompressedImage, args.topic, self.on_image, qos_profile_sensor_data
        )
        self.get_logger().info(
            f'Waiting for marker {args.marker_id} on {args.topic}; no robot motion'
        )

    def on_image(self, message):
        frame = self.bridge.compressed_imgmsg_to_cv2(message, 'bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.detector is not None:
            corners, ids, _ = self.detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(
                gray, self.dictionary, parameters=self.parameters
            )
        if ids is None or self.args.marker_id not in ids.reshape(-1).tolist():
            return
        index = ids.reshape(-1).tolist().index(self.args.marker_id)
        points = np.asarray(corners[index], dtype=float).reshape(4, 2)
        marker_px = float(np.mean([
            np.linalg.norm(points[(i + 1) % 4] - points[i]) for i in range(4)
        ]))
        center = np.mean(points, axis=0)
        radius = max(80, int(round(marker_px * self.args.radius_markers)))
        x0 = max(0, int(round(center[0])) - radius)
        y0 = max(0, int(round(center[1])) - radius)
        x1 = min(frame.shape[1], int(round(center[0])) + radius)
        y1 = min(frame.shape[0], int(round(center[1])) + radius)
        crop = frame[y0:y1, x0:x1].copy()

        annotated = frame.copy()
        cv2.aruco.drawDetectedMarkers(annotated, [corners[index]], ids[index:index + 1])
        cv2.rectangle(annotated, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 255), 3)
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        paths = {
            'full': self.args.output.with_name(self.args.output.stem + '_full.jpg'),
            'annotated': self.args.output.with_name(
                self.args.output.stem + '_annotated.jpg'
            ),
            'roi': self.args.output.with_name(self.args.output.stem + '_roi.jpg'),
        }
        for key, image in (
            ('full', frame), ('annotated', annotated), ('roi', crop)
        ):
            if not cv2.imwrite(str(paths[key]), image):
                raise RuntimeError(f'Failed to save {paths[key]}')
        mm_per_px = self.args.marker_length_mm / marker_px
        print(f'Image: {frame.shape[1]}x{frame.shape[0]}')
        print(f'Marker {self.args.marker_id}: {marker_px:.2f} px')
        print(f'Local scale: {mm_per_px:.4f} mm/px')
        print(
            f'Expected 6.0x3.5 mm footprint: '
            f'{6.0/mm_per_px:.1f}x{3.5/mm_per_px:.1f} px'
        )
        print(f'ROI: x={x0}:{x1}, y={y0}:{y1}')
        print(f'Saved: {paths["roi"]}')
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--marker-id', type=int, default=8)
    parser.add_argument('--marker-length-mm', type=float, default=16.8)
    parser.add_argument('--radius-markers', type=float, default=4.0)
    parser.add_argument(
        '--topic', default='/camera/camera/color/image_raw/compressed'
    )
    parser.add_argument(
        '--output', type=Path, default=Path('/tmp/ksmc_marker8_part.jpg')
    )
    args = parser.parse_args()
    rclpy.init()
    node = CaptureMarkerRoi(args)
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
