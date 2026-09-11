#!/usr/bin/env python3
"""Compare a live SMD OBB model with operator terminal-axis references.

This utility only subscribes to camera/robot-state topics. It never publishes a
robot command.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from ultralytics import YOLO

from smd_set_selection import select_smd_set


def canonical_axis(angle: float) -> float:
    return (float(angle) + 90.0) % 180.0 - 90.0


def axis_error(predicted: float, reference: float) -> float:
    return abs(canonical_axis(float(predicted) - float(reference)))


def box_geometry(points: np.ndarray) -> tuple[float, float]:
    (_, _), (width, height), angle = cv2.minAreaRect(points.astype(np.float32))
    if height > width:
        width, height = height, width
        angle += 90.0
    aspect = float(width / max(height, 1e-6))
    return canonical_axis(angle), aspect


class LiveFrames(Node):
    def __init__(self, color_topic: str, robot_topic: str, count: int) -> None:
        super().__init__("evaluate_smd_axis_model_live")
        self.robot = None
        self.frames: list[np.ndarray] = []
        self.count = count
        self.create_subscription(RobotNonrtState, robot_topic, self.robot_cb, 10)
        self.create_subscription(CompressedImage, color_topic, self.image_cb, qos_profile_sensor_data)

    def robot_cb(self, message: RobotNonrtState) -> None:
        self.robot = message

    def image_cb(self, message: CompressedImage) -> None:
        if len(self.frames) >= self.count:
            return
        image = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)
        if image is not None:
            self.frames.append(image)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-index", type=int, choices=(1, 2), default=1)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--model", type=Path, default=root / "models/smd_obb/pilot_04/weights/best.pt")
    parser.add_argument("--manual-axes", type=Path)
    parser.add_argument("--output", type=Path, default=root / "data/smd_axis_model_live_evaluation.json")
    parser.add_argument("--review", type=Path, default=root / "data/smd_axis_model_live_evaluation.jpg")
    parser.add_argument("--snapshot", type=Path, default=root / "data/smd_axis_model_live_rectified.jpg")
    parser.add_argument("--source-snapshot", type=Path, default=root / "data/smd_axis_model_live_source.jpg")
    parser.add_argument("--color-topic", default="/camera/camera/color/image_raw/compressed")
    parser.add_argument("--robot-topic", default="/nonrt_state_data")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--device", default="0")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-angle-error-deg", type=float, default=8.0)
    parser.add_argument("--min-aspect-ratio", type=float, default=1.35)
    args = parser.parse_args()
    if args.frames < 3:
        parser.error("--frames must be at least 3")
    manual_path = args.manual_axes or root / "data" / f"smd_manual_axes_set{args.set_index}.json"

    config = json.loads(args.config.read_text(encoding="utf-8"))
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    references = {int(part["instance_index"]): part for part in manual["parts"]}
    width, height = map(int, config["canonical_size"])
    reference_pose = np.asarray(config["reference_tcp_base"], dtype=float)

    rclpy.init()
    node = LiveFrames(args.color_topic, args.robot_topic, args.frames)
    deadline = time.monotonic() + args.timeout
    try:
        while rclpy.ok() and len(node.frames) < args.frames and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    if node.robot is None or len(node.frames) < args.frames:
        raise RuntimeError(f"camera/state timeout: received {len(node.frames)}/{args.frames} frames")
    robot = node.robot
    pose = np.asarray([
        robot.cart_x_cur_pos, robot.cart_y_cur_pos, robot.cart_z_cur_pos,
        robot.cart_a_cur_pos, robot.cart_b_cur_pos, robot.cart_c_cur_pos,
    ], dtype=float)
    position_error = float(np.max(np.abs(pose[:3] - reference_pose[:3])))
    rotation_error = float(np.max(np.abs((pose[3:] - reference_pose[3:] + 180.0) % 360.0 - 180.0)))
    if int(robot.robot_motion_done) != 1 or position_error > 1.0 or rotation_error > 0.2:
        raise RuntimeError(f"fixed SMD view required; current={pose.tolist()}")

    source_size = np.asarray(config["source_image_size"], dtype=float)
    frame_size = np.asarray([node.frames[0].shape[1], node.frames[0].shape[0]], dtype=float)
    section = (
        np.asarray(config["section_polygon_pixel"], dtype=np.float32)
        * (frame_size / source_size)
    ).astype(np.float32)
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    homography = cv2.getPerspectiveTransform(section, destination)
    rectified = [cv2.warpPerspective(frame, homography, (width, height), flags=cv2.INTER_CUBIC)
                 for frame in node.frames]
    model = YOLO(str(args.model))
    samples: dict[int, list[dict]] = {index: [] for index in references}
    first_selected = None
    rejected = []
    for frame_index, image in enumerate(rectified, 1):
        prediction = model.predict(image, imgsz=args.image_size, conf=args.confidence,
                                   device=args.device, verbose=False)[0]
        items = []
        if prediction.obb is not None:
            for box, confidence in zip(prediction.obb.xyxyxyxy.cpu().numpy(),
                                       prediction.obb.conf.cpu().numpy()):
                angle, aspect = box_geometry(box)
                items.append({"box": box, "center": box.mean(axis=0), "angle": angle,
                              "aspect_ratio": aspect, "confidence": float(confidence)})
        try:
            selected = select_smd_set(items, config["set_layout"], args.set_index)
        except RuntimeError as error:
            rejected.append({"frame": frame_index, "reason": str(error), "count": len(items)})
            continue
        if first_selected is None:
            first_selected = selected
        for instance, item in enumerate(selected, 1):
            samples[instance].append({
                "angle_deg": round(float(item["angle"]), 4),
                "aspect_ratio": round(float(item["aspect_ratio"]), 4),
                "confidence": round(float(item["confidence"]), 4),
                "center_canonical_pixel": np.round(item["center"], 3).tolist(),
            })
    if first_selected is None:
        raise RuntimeError("no frame produced a complete SMD set")

    results = []
    all_passed = len(rejected) == 0
    for instance in sorted(samples):
        rows = samples[instance]
        if not rows:
            all_passed = False
            results.append({"instance_index": instance, "passed": False, "reason": "no samples"})
            continue
        values = np.asarray([row["angle_deg"] for row in rows], dtype=float)
        reference = float(references[instance]["long_axis_canonical_deg"])
        unwrapped = reference + (values - reference + 90.0) % 180.0 - 90.0
        median = canonical_axis(float(np.median(unwrapped)))
        error = axis_error(median, reference)
        aspects = np.asarray([row["aspect_ratio"] for row in rows], dtype=float)
        passed = error <= args.max_angle_error_deg and float(np.median(aspects)) >= args.min_aspect_ratio
        all_passed &= passed
        results.append({
            "instance_index": instance,
            "reference_angle_deg": round(reference, 4),
            "predicted_angle_median_deg": round(median, 4),
            "angle_error_deg": round(error, 4),
            "angle_span_deg": round(float(np.ptp(unwrapped)), 4),
            "aspect_ratio_median": round(float(np.median(aspects)), 4),
            "confidence_median": round(float(np.median([row["confidence"] for row in rows])), 4),
            "sample_count": len(rows),
            "passed": bool(passed),
            "samples": rows,
        })

    review = rectified[0].copy()
    for instance, item in enumerate(first_selected, 1):
        box = np.rint(item["box"]).astype(np.int32)
        cv2.polylines(review, [box], True, (0, 220, 0), 2, cv2.LINE_AA)
        center = np.rint(item["center"]).astype(int)
        theta = np.deg2rad(float(item["angle"]))
        half_length = 42
        delta = np.rint([np.cos(theta) * half_length, np.sin(theta) * half_length]).astype(int)
        cv2.arrowedLine(review, tuple(center - delta), tuple(center + delta), (0, 0, 255),
                        3, cv2.LINE_AA, tipLength=0.18)
        label = f"{instance}: {item['angle']:.1f} deg AR {item['aspect_ratio']:.2f}"
        cv2.putText(review, label, tuple(center + [10, -12]), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 2, cv2.LINE_AA)
    payload = {
        "schema_version": 1,
        "mode": "live_smd_obb_axis_vs_operator_reference",
        "timestamp_unix": time.time(),
        "robot_motion_authorized": False,
        "model": str(args.model),
        "manual_axes": str(manual_path),
        "set_index": args.set_index,
        "captured_frames": len(node.frames),
        "accepted_frames": len(node.frames) - len(rejected),
        "rejected_frames": rejected,
        "limits": {"max_angle_error_deg": args.max_angle_error_deg,
                   "min_aspect_ratio": args.min_aspect_ratio},
        "all_passed": bool(all_passed),
        "results": results,
    }
    for path in (args.output, args.review, args.snapshot, args.source_snapshot):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    cv2.imwrite(str(args.review), review, [cv2.IMWRITE_JPEG_QUALITY, 96])
    cv2.imwrite(str(args.snapshot), rectified[0], [cv2.IMWRITE_JPEG_QUALITY, 96])
    cv2.imwrite(str(args.source_snapshot), node.frames[0], [cv2.IMWRITE_JPEG_QUALITY, 96])
    print(json.dumps({"all_passed": payload["all_passed"], "results": [
        {key: row[key] for key in ("instance_index", "reference_angle_deg",
                                   "predicted_angle_median_deg", "angle_error_deg",
                                   "aspect_ratio_median", "passed")}
        for row in results]}, indent=2))
    if not all_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
