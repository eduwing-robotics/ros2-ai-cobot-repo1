#!/usr/bin/env python3
"""Save one sharp 1920x1080 ChArUco image for intrinsic calibration."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

from charuco_common import detect_charuco, detector_parameters, load_config


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "intrinsic_1920_images.json"


class Collector(Node):
    def __init__(self, args):
        super().__init__("capture_charuco_intrinsic_image")
        self.args = args
        self.bridge = CvBridge()
        self.config, self.dictionary, self.board = load_config()
        self.parameters = detector_parameters()
        self.valid = []
        self.last_markers = 0
        self.last_corners = 0
        self.create_subscription(
            CompressedImage, self.config["image_topic"], self.on_image,
            qos_profile_sensor_data,
        )
        self.create_timer(3.0, self.status)
        self.get_logger().info(
            f"Waiting for {args.frames} valid 1920x1080 ChArUco frames"
        )

    def on_image(self, msg):
        frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
        height, width = frame.shape[:2]
        if (width, height) != (1920, 1080):
            self.get_logger().error(
                f"Expected 1920x1080, received {width}x{height}; no image saved"
            )
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, marker_ids, corners, ids, _ = detect_charuco(
            gray, self.dictionary, self.board, self.parameters
        )
        self.last_markers = 0 if marker_ids is None else len(marker_ids)
        self.last_corners = 0 if ids is None else len(ids)
        if ids is None or len(ids) < self.args.min_corners:
            return
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        self.valid.append((sharpness, frame.copy(), self.last_markers, self.last_corners))
        count = len(self.valid)
        if count == 1 or count % 5 == 0:
            self.get_logger().info(
                f"Valid frames: {count}/{self.args.frames} "
                f"(markers={self.last_markers}, corners={self.last_corners})"
            )
        if count >= self.args.frames:
            rclpy.shutdown()

    def status(self):
        if not self.valid:
            self.get_logger().warning(
                f"Waiting for board: markers={self.last_markers}, "
                f"corners={self.last_corners}, need>={self.args.min_corners}"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--min-corners", type=int, default=12)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    rclpy.init()
    node = Collector(args)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        raise SystemExit("Cancelled; no image was written")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if len(node.valid) < args.frames:
        raise SystemExit("Not enough valid frames; no image was written")
    sharpness, image, markers, corners = max(node.valid, key=lambda item: item[0])
    if args.data_file.exists():
        payload = json.loads(args.data_file.read_text(encoding="utf-8"))
    else:
        payload = {
            "schema_version": 1,
            "purpose": "d435_color_intrinsic_1920x1080",
            "image_width": 1920,
            "image_height": 1080,
            "board_config": str(ROOT / "config" / "charuco_board.yaml"),
            "samples": [],
        }
    index = len(payload["samples"]) + 1
    image_dir = args.data_file.parent / f"{args.data_file.stem}_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / f"sample_{index:03d}.jpg"
    if not cv2.imwrite(str(image_path), image, [int(cv2.IMWRITE_JPEG_QUALITY), 98]):
        raise SystemExit("Could not write image")
    payload["samples"].append({
        "index": index,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "image": image_path.relative_to(args.data_file.parent).as_posix(),
        "detected_markers": markers,
        "detected_charuco_corners": corners,
        "sharpness": sharpness,
    })
    args.data_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved intrinsic image {index}: {image_path}")
    print(f"Label: {args.label or '(none)'}, corners={corners}, sharpness={sharpness:.1f}")
    print(f"Total images: {index} (target 25)")


if __name__ == "__main__":
    main()
