#!/usr/bin/env python3
"""Collect registered tray images and per-bin crops for segmentation labeling."""

import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String


TARGET_PARTS = {"black_block", "marked_white", "right_white_brown", "long_orange", "gpu", "hbm"}


class DatasetCollector(Node):
    def __init__(self, args):
        super().__init__("tray_segmentation_dataset_collector")
        self.args = args
        self.layout = json.loads(args.layout.read_text(encoding="utf-8"))
        size = self.layout["reference_image_size_px"]
        self.width, self.height = int(size["width"]), int(size["height"])
        self.bins = [b for b in self.layout["bins"] if b["part_type"] in args.parts]
        if not self.bins:
            raise RuntimeError("No requested part types exist in the tray layout")

        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = args.output_root / (args.session or stamp)
        (self.session_dir / "full").mkdir(parents=True, exist_ok=True)
        for item in self.bins:
            (self.session_dir / "crops" / item["part_type"]).mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.session_dir / "manifest.jsonl"
        self.latest_h = None
        self.registration_state = "NONE"
        self.last_registration_ns = 0
        self.last_save_time = 0.0
        self.last_gray = None
        self.previous_gray = None
        self.motion_armed = True
        self.stable_since = None
        self.saved = len(list((self.session_dir / "full").glob("frame_*.jpg")))
        self.next_timed_capture = time.monotonic() + args.timed_capture_seconds
        self.last_countdown = None

        qos = QoSProfile(
            depth=1,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.create_subscription(CompressedImage, args.color_topic, self.image_cb, qos)
        self.create_subscription(String, args.registration_topic, self.registration_cb, 10)
        self.get_logger().info(f"Dataset session: {self.session_dir}")
        self.get_logger().info("Targets: " + ", ".join(b["part_type"] for b in self.bins))
        if self.saved:
            self.get_logger().info(f"Resuming at {self.saved}/{args.max_frames or 'unlimited'} frames")
        if args.timed_capture_seconds > 0:
            self.get_logger().info(
                f"Timed capture every {args.timed_capture_seconds:g}s; move parts before 3-2-1"
            )

    def registration_cb(self, message):
        try:
            payload = json.loads(message.data)
            h = np.asarray(payload["homography_reference_to_image"], dtype=np.float64)
            if h.shape != (3, 3) or not np.isfinite(h).all():
                return
            self.latest_h = h
            self.registration_state = str(payload.get("state", "UNKNOWN"))
            self.last_registration_ns = int(payload.get("timestamp_ros_ns", 0))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.get_logger().warning("Ignored invalid tray registration")

    def image_cb(self, message):
        if self.saved >= self.args.max_frames > 0:
            return
        now = time.monotonic()
        if now - self.last_save_time < self.args.interval:
            return
        if self.latest_h is None or self.registration_state not in {"TRACKING", "HELD"}:
            return
        stamp_ns = int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)
        age_ms = abs(stamp_ns - self.last_registration_ns) / 1_000_000.0
        if age_ms > self.args.max_registration_age_ms:
            return
        encoded = np.frombuffer(message.data, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            return
        try:
            canonical = cv2.warpPerspective(
                image, np.linalg.inv(self.latest_h), (self.width, self.height), flags=cv2.INTER_LINEAR
            )
        except np.linalg.LinAlgError:
            return

        gray = cv2.resize(cv2.cvtColor(canonical, cv2.COLOR_BGR2GRAY), (320, 180))
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if sharpness < self.args.min_sharpness:
            self.previous_gray = gray
            return
        timed_capture = self.args.timed_capture_seconds > 0
        if timed_capture:
            remaining = self.next_timed_capture - now
            countdown = max(0, int(math.ceil(remaining)))
            if 1 <= countdown <= 3 and countdown != self.last_countdown:
                self.get_logger().info(f"Capture in {countdown}...")
                self.last_countdown = countdown
            if remaining > 0:
                return
        frame_motion = None if self.previous_gray is None else float(
            np.mean(cv2.absdiff(gray, self.previous_gray))
        )
        self.previous_gray = gray
        difference = None if self.last_gray is None else float(np.mean(cv2.absdiff(gray, self.last_gray)))
        if not timed_capture:
            if frame_motion is not None and frame_motion >= self.args.motion_threshold:
                self.motion_armed = True
                self.stable_since = None
                return
            if not self.motion_armed:
                return
            if frame_motion is None or frame_motion > self.args.stable_threshold:
                self.stable_since = None
                return
            if self.stable_since is None:
                self.stable_since = now
                return
            if now - self.stable_since < self.args.stable_seconds:
                return
            if difference is not None and difference < self.args.min_frame_difference:
                self.motion_armed = False
                self.stable_since = None
                return

        frame_id = f"frame_{self.saved:06d}_{stamp_ns}"
        full_rel = Path("full") / f"{frame_id}.jpg"
        cv2.imwrite(str(self.session_dir / full_rel), canonical, [cv2.IMWRITE_JPEG_QUALITY, 95])
        crops = []
        for item in self.bins:
            x1, y1, x2, y2 = map(int, item["roi_px"])
            pad = self.args.padding
            x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
            x2, y2 = min(self.width, x2 + pad), min(self.height, y2 + pad)
            crop = canonical[y1:y2, x1:x2]
            rel = Path("crops") / item["part_type"] / f"{frame_id}.jpg"
            cv2.imwrite(str(self.session_dir / rel), crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            crops.append({"part_type": item["part_type"], "path": str(rel), "roi_px": [x1, y1, x2, y2]})

        record = {
            "frame_id": frame_id,
            "timestamp_ros_ns": stamp_ns,
            "registration_state": self.registration_state,
            "registration_age_ms": round(age_ms, 2),
            "sharpness": round(sharpness, 2),
            "difference_from_previous": None if difference is None else round(difference, 3),
            "full_image": str(full_rel),
            "crops": crops,
        }
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.saved += 1
        self.last_save_time = now
        self.last_gray = gray
        self.motion_armed = False
        self.stable_since = None
        if timed_capture:
            self.next_timed_capture = now + self.args.timed_capture_seconds
            self.last_countdown = None
        self.get_logger().info(f"Saved {self.saved}/{self.args.max_frames or 'unlimited'}: {frame_id}")
        if self.saved >= self.args.max_frames > 0:
            self.get_logger().info("Requested frame count reached")
            rclpy.shutdown()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, default=root / "config/tray_layout_candidate.json")
    parser.add_argument("--output-root", type=Path, default=root / "datasets/tray_segmentation/raw")
    parser.add_argument("--session", default=None)
    parser.add_argument("--parts", nargs="+", default=sorted(TARGET_PARTS))
    parser.add_argument("--color-topic", default="/camera/camera/color/image_raw/compressed")
    parser.add_argument("--registration-topic", default="/vision/tray/registration")
    parser.add_argument("--interval", type=float, default=0.75)
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--max-registration-age-ms", type=float, default=5000.0)
    parser.add_argument("--min-sharpness", type=float, default=18.0)
    parser.add_argument("--min-frame-difference", type=float, default=1.5)
    parser.add_argument("--motion-threshold", type=float, default=3.0)
    parser.add_argument("--stable-threshold", type=float, default=1.2)
    parser.add_argument("--stable-seconds", type=float, default=1.2)
    parser.add_argument("--padding", type=int, default=20)
    parser.add_argument(
        "--timed-capture-seconds", type=float, default=0.0,
        help="Capture at this interval and show a terminal 3-2-1 countdown; 0 uses motion detection",
    )
    args = parser.parse_args()
    rclpy.init()
    node = DatasetCollector(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            node.get_logger().info(f"Collection finished: {node.saved} frames in {node.session_dir}")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
