#!/usr/bin/env python3
"""Let the operator click the two white terminal centres for each SMD."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from smd_manual_axis import canonical_axis_angle_deg, directed_axis_angle_deg
from smd_set_selection import select_smd_set


class OneFrame(Node):
    def __init__(self, color_topic: str, robot_topic: str) -> None:
        super().__init__("manual_set_smd_axes")
        self.image = None
        self.robot = None
        self.create_subscription(CompressedImage, color_topic, self.image_cb, qos_profile_sensor_data)
        self.create_subscription(RobotNonrtState, robot_topic, self.robot_cb, 10)

    def image_cb(self, message: CompressedImage) -> None:
        if self.image is None:
            self.image = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)

    def robot_cb(self, message: RobotNonrtState) -> None:
        self.robot = message


def wait_for_frame(node: OneFrame, timeout: float) -> tuple[np.ndarray, RobotNonrtState]:
    deadline = time.monotonic() + timeout
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if node.image is not None and node.robot is not None:
            return node.image, node.robot
    raise RuntimeError("camera image or robot state was not received")


def annotate_part(image: np.ndarray, box: np.ndarray, instance: int, zoom: int) -> np.ndarray:
    center = np.asarray(box, dtype=float).mean(axis=0)
    radius = 72
    x0 = max(0, int(round(center[0])) - radius)
    y0 = max(0, int(round(center[1])) - radius)
    x1 = min(image.shape[1], x0 + 2 * radius)
    y1 = min(image.shape[0], y0 + 2 * radius)
    x0 = max(0, x1 - 2 * radius)
    y0 = max(0, y1 - 2 * radius)
    crop = image[y0:y1, x0:x1]
    clicks: list[tuple[int, int]] = []
    window = "SMD manual axis - click terminal A then B; Enter confirm; R reset; Esc cancel"

    def mouse(event, x, y, _flags, _parameter):
        if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < 2:
            clicks.append((int(round(x / zoom + x0)), int(round(y / zoom + y0))))

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, crop.shape[1] * zoom, crop.shape[0] * zoom)
    cv2.setMouseCallback(window, mouse)
    while True:
        view = cv2.resize(crop, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
        local_box = (np.asarray(box) - [x0, y0]) * zoom
        cv2.polylines(view, [np.rint(local_box).astype(np.int32)], True, (0, 220, 0), 2, cv2.LINE_AA)
        local_clicks = [((x - x0) * zoom, (y - y0) * zoom) for x, y in clicks]
        for index, point in enumerate(local_clicks):
            label = "A" if index == 0 else "B"
            cv2.circle(view, tuple(map(int, point)), 8, (0, 255, 255), -1, cv2.LINE_AA)
            cv2.putText(view, label, (int(point[0]) + 10, int(point[1]) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        if len(local_clicks) == 2:
            p0, p1 = (tuple(map(int, point)) for point in local_clicks)
            cv2.arrowedLine(view, p0, p1, (0, 0, 0), 8, cv2.LINE_AA, tipLength=0.18)
            cv2.arrowedLine(view, p0, p1, (255, 255, 255), 3, cv2.LINE_AA, tipLength=0.18)
        cv2.putText(view, f"SMD {instance}: A first, B second", (16, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.72, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow(window, view)
        key = cv2.waitKey(30) & 0xFF
        if key in (27, ord("q")):
            cv2.destroyAllWindows()
            raise SystemExit("manual SMD axis entry cancelled")
        if key in (ord("r"), ord("R")):
            clicks.clear()
        if key in (10, 13) and len(clicks) == 2:
            break
    cv2.destroyWindow(window)
    return np.asarray(clicks, dtype=float)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-index", type=int, choices=(1, 2), default=1)
    parser.add_argument("--consumed-prefix-count", type=int, default=0,
                        help="Confirmed empty leading slots; preserve physical numbering")
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--model", type=Path, default=root / "models/smd_obb/pilot_03/weights/best.pt")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--color-topic", default="/camera/camera/color/image_raw/compressed")
    parser.add_argument("--robot-topic", default="/nonrt_state_data")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--zoom", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if not 2 <= args.zoom <= 8:
        parser.error("--zoom must be between 2 and 8")
    args.output = args.output or root / "data" / f"smd_manual_axes_set{args.set_index}.json"
    args.review = args.review or root / "data" / f"smd_manual_axes_set{args.set_index}_review.jpg"

    config = json.loads(args.config.read_text(encoding="utf-8"))
    reference = np.asarray(config["reference_tcp_base"], dtype=float)
    width, height = map(int, config["canonical_size"])
    rclpy.init()
    node = OneFrame(args.color_topic, args.robot_topic)
    try:
        image, robot = wait_for_frame(node, args.timeout)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    pose = np.asarray([
        robot.cart_x_cur_pos, robot.cart_y_cur_pos, robot.cart_z_cur_pos,
        robot.cart_a_cur_pos, robot.cart_b_cur_pos, robot.cart_c_cur_pos,
    ], dtype=float)
    position_error = float(np.max(np.abs(pose[:3] - reference[:3])))
    angle_error = float(np.max(np.abs((pose[3:] - reference[3:] + 180.0) % 360.0 - 180.0)))
    if int(robot.robot_motion_done) != 1 or position_error > 1.0 or angle_error > 0.2:
        raise RuntimeError(
            f"manual SMD axes require the fixed SMDSectionView; current={pose.tolist()}"
        )
    safety = [robot.emg, robot.abnormal_stop, robot.main_error_code, robot.sub_error_code,
              robot.collision_err, robot.alarm, robot.safetydoor_alarm, robot.safetyplanealarm]
    if any(float(value) != 0.0 for value in safety):
        raise RuntimeError("robot safety state is not clear")

    source_size = np.asarray(config["source_image_size"], dtype=float)
    scale = np.asarray([image.shape[1], image.shape[0]], dtype=float) / source_size
    section = (np.asarray(config["section_polygon_pixel"], dtype=np.float32) * scale).astype(np.float32)
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    homography = cv2.getPerspectiveTransform(section, destination)
    inverse = np.linalg.inv(homography)
    rectified = cv2.warpPerspective(image, homography, (width, height), flags=cv2.INTER_CUBIC)
    result = YOLO(str(args.model)).predict(
        rectified, imgsz=args.image_size, conf=args.confidence, device="0", verbose=False
    )[0]
    count = 0 if result.obb is None else len(result.obb)
    layout = config["set_layout"]
    prefix = args.consumed_prefix_count
    if not 0 <= prefix < int(layout["parts_per_set"]):
        raise RuntimeError("invalid confirmed consumed prefix")
    allowed_counts = {int(layout["parts_per_set"]) - prefix, int(layout["required_count"]) - prefix}
    if count not in allowed_counts:
        raise RuntimeError(
            "manual labeling requires all remaining parts in one or both sets; "
            f"received {count}, allowed={sorted(allowed_counts)}")
    items = [
        {"box": box, "center": box.mean(axis=0), "confidence": float(confidence)}
        for box, confidence in zip(
            result.obb.xyxyxyxy.cpu().numpy(), result.obb.conf.cpu().numpy()
        )
    ]
    selected = select_smd_set(items, layout, args.set_index, consumed_prefix_count=prefix)
    parts = []
    for instance, item in enumerate(selected, 1):
        if item is None:
            continue
        endpoints = annotate_part(rectified, item["box"], instance, args.zoom)
        directed = directed_axis_angle_deg(endpoints[0], endpoints[1])
        source_endpoints = cv2.perspectiveTransform(
            endpoints.astype(np.float32).reshape(-1, 1, 2), inverse
        )[:, 0]
        parts.append({
            "instance_index": instance,
            "detection_center_canonical_pixel": np.round(item["center"], 3).tolist(),
            "terminal_endpoints_canonical_pixel": np.round(endpoints, 3).tolist(),
            "terminal_endpoints_source_pixel": np.round(source_endpoints, 3).tolist(),
            "directed_axis_canonical_deg": round(directed, 4),
            "long_axis_canonical_deg": round(canonical_axis_angle_deg(directed), 4),
            "detection_confidence": round(item["confidence"], 4),
        })

    review = rectified.copy()
    for part in parts:
        points = np.rint(np.asarray(part["terminal_endpoints_canonical_pixel"])).astype(int)
        cv2.arrowedLine(review, tuple(points[0]), tuple(points[1]), (0, 0, 0), 9, cv2.LINE_AA, tipLength=0.18)
        cv2.arrowedLine(review, tuple(points[0]), tuple(points[1]), (255, 255, 255), 4, cv2.LINE_AA, tipLength=0.18)
        center = np.rint(points.mean(axis=0)).astype(int)
        cv2.putText(review, str(part["instance_index"]), tuple(center + [10, -10]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
    payload = {
        "schema_version": 1,
        "mode": "operator_two_terminal_axes",
        "robot_motion_authorized": False,
        "operator_confirmed_consumed_prefix_count": prefix,
        "timestamp_unix": time.time(),
        "set_index": args.set_index,
        "canonical_size": [width, height],
        "reference_tcp_base": reference.tolist(),
        "source_image_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "click_semantics": "terminal A first, terminal B second; arrow A-to-B",
        "parts": parts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    cv2.imwrite(str(args.review), review, [cv2.IMWRITE_JPEG_QUALITY, 96])
    print(f"Saved manual SMD axes: {args.output}")
    print(f"Review image: {args.review}")


if __name__ == "__main__":
    main()
