#!/usr/bin/env python3
"""Freeze the assembly-station PCB frame and export all placement slots.

This tool is read-only with respect to the conveyor and robot.  It combines a
stable S22 board polygon with the Unity-derived board-relative layout, saves a
lossless overview frame, and exports board-mm/image-pixel coordinates for all
25 component slots.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PolygonStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_srvs.srv import Trigger


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_LAYOUT = PROJECT_DIR / "vision_assembly/config/board_layout_from_unity.json"
DEFAULT_PHYSICAL_BOARD = PROJECT_DIR / "vision_assembly/config/physical_board.json"
DEFAULT_CALIBRATION = PROJECT_DIR / "vision_assembly/data/s22_plane_calibration.json"
DEFAULT_ARCHIVE = PROJECT_DIR / "runtime/assembly_coordinates"
DEFAULT_EXPORT_PREFIX = PROJECT_DIR / "vision_assembly/data/assembly_slot_coordinates"
INSPECTION_DIR = PROJECT_DIR / "vision_assembly/inspection"
if str(INSPECTION_DIR) not in sys.path:
    sys.path.insert(0, str(INSPECTION_DIR))

from layout_overrides import apply_component_slot_overrides  # noqa: E402

TYPE_COLORS = {
    "GPU": (255, 90, 220),
    "HBM": (85, 220, 120),
    "Power Module": (40, 165, 255),
    "VRM": (225, 90, 80),
    "Inductor": (70, 230, 245),
    "SMD Capacitor": (90, 235, 90),
}
TYPE_CODES = {
    "GPU": "G",
    "HBM": "H",
    "Power Module": "P",
    "VRM": "V",
    "Inductor": "I",
    "SMD Capacitor": "S",
}


def ordered_image_quad(points: np.ndarray) -> np.ndarray:
    """Return top-left, top-right, bottom-right, bottom-left."""
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    result = np.empty((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    result[0] = points[np.argmin(sums)]
    result[1] = points[np.argmin(differences)]
    result[2] = points[np.argmax(sums)]
    result[3] = points[np.argmax(differences)]
    if len({tuple(point) for point in result.tolist()}) != 4:
        raise ValueError("board polygon corners could not be ordered")
    return result


def board_source_corners(board_x_mm: float, board_y_mm: float) -> np.ndarray:
    """Board coordinates matching the current fixture orientation in S22.

    The fixture handle defines +Y at the image top.  With an unmirrored S22
    frame and board normal pointing upward, +X is the image-left direction.
    """
    half_x = board_x_mm * 0.5
    half_y = board_y_mm * 0.5
    return np.float32([
        [half_x, half_y],
        [-half_x, half_y],
        [-half_x, -half_y],
        [half_x, -half_y],
    ])


def project_points(homography: np.ndarray, points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(points, homography).reshape(-1, 2)


def angle_image_deg(
    homography: np.ndarray,
    center_xy: tuple[float, float],
    long_axis_board_deg: float,
) -> float:
    radians = math.radians(long_axis_board_deg)
    direction = np.asarray((math.cos(radians), math.sin(radians)), dtype=np.float32)
    points = project_points(
        homography,
        np.asarray((center_xy, np.asarray(center_xy) + direction), dtype=np.float32),
    )
    delta = points[1] - points[0]
    return float(math.degrees(math.atan2(float(delta[1]), float(delta[0]))))


def project_homogeneous(homography: np.ndarray, point: np.ndarray) -> np.ndarray:
    homogeneous = homography @ np.asarray((point[0], point[1], 1.0), dtype=float)
    if abs(float(homogeneous[2])) < 1e-12:
        raise ValueError("homography projected a point to infinity")
    return homogeneous[:2] / homogeneous[2]


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(f".{link.name}.{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)


def short_label(slot_id: str, component_type: str) -> str:
    if slot_id == "ai_gpu":
        return "G1"
    match = re.search(r"_(\d+)$", slot_id)
    suffix = int(match.group(1)) if match else 1
    return f"{TYPE_CODES[component_type]}{suffix}"


def nominal_box_points(placement: dict[str, Any]) -> np.ndarray:
    center = placement["center_board_mm"]
    size = placement["nominal_size_mm"]
    half_long = max(float(size["x"]), float(size["y"])) * 0.5
    half_short = min(float(size["x"]), float(size["y"])) * 0.5
    radians = math.radians(float(placement["long_axis_deg_in_board"]))
    long_direction = np.float32((math.cos(radians), math.sin(radians)))
    short_direction = np.float32((-math.sin(radians), math.cos(radians)))
    center_xy = np.float32((center["x"], center["y"]))
    return np.float32([
        center_xy - long_direction * half_long - short_direction * half_short,
        center_xy + long_direction * half_long - short_direction * half_short,
        center_xy + long_direction * half_long + short_direction * half_short,
        center_xy - long_direction * half_long + short_direction * half_short,
    ])


class PolygonCollector(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("capture_assembly_slot_coordinates")
        self.args = args
        self.samples: list[np.ndarray] = []
        self.create_subscription(
            PolygonStamped,
            args.polygon_topic,
            self._polygon_callback,
            qos_profile_sensor_data,
        )
        self.snapshot_client = self.create_client(Trigger, args.snapshot_service)
        self.get_logger().info(
            f"NO MOTION: collecting {args.frames} assembly-board polygons from "
            f"{args.polygon_topic}"
        )

    def _polygon_callback(self, message: PolygonStamped) -> None:
        if len(self.samples) >= self.args.frames:
            return
        points = np.asarray(
            [[point.x, point.y] for point in message.polygon.points],
            dtype=np.float32,
        )
        if points.shape != (4, 2) or not np.all(np.isfinite(points)):
            return
        try:
            ordered = ordered_image_quad(points)
        except ValueError:
            return
        self.samples.append(ordered)
        count = len(self.samples)
        if count in (1, 5, 10, 20, self.args.frames):
            self.get_logger().info(f"Stable polygon frames: {count}/{self.args.frames}")

    def collect(self) -> np.ndarray:
        deadline = time.monotonic() + self.args.timeout_seconds
        while rclpy.ok() and len(self.samples) < self.args.frames:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"timed out after {self.args.timeout_seconds:g}s with "
                    f"{len(self.samples)}/{self.args.frames} board frames"
                )
            rclpy.spin_once(self, timeout_sec=0.1)
        return np.median(np.asarray(self.samples, dtype=np.float32), axis=0)

    def capture_snapshot(self) -> Path:
        if not self.snapshot_client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(f"snapshot service unavailable: {self.args.snapshot_service}")
        future = self.snapshot_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=15.0)
        if not future.done() or future.result() is None:
            raise RuntimeError("S22 snapshot service did not respond")
        response = future.result()
        if not response.success:
            raise RuntimeError(f"S22 snapshot failed: {response.message}")
        match = re.match(r"^(.*) \(\d+x\d+, lossless PNG\)$", response.message)
        path = Path(match.group(1) if match else response.message).expanduser()
        if not path.is_file():
            raise RuntimeError(f"snapshot service returned a missing file: {path}")
        return path.resolve()


def yellow_handle_scores(
    image: np.ndarray,
    board_to_pixel: np.ndarray,
    board_x_mm: float,
    board_y_mm: float,
) -> dict[str, int]:
    half_x = board_x_mm * 0.5
    half_y = board_y_mm * 0.5
    patches = {
        "+Y": [(-16, half_y), (16, half_y), (16, half_y + 11), (-16, half_y + 11)],
        "-Y": [(-16, -half_y - 11), (16, -half_y - 11), (16, -half_y), (-16, -half_y)],
        "+X": [(half_x, -16), (half_x + 11, -16), (half_x + 11, 16), (half_x, 16)],
        "-X": [(-half_x - 11, -16), (-half_x, -16), (-half_x, 16), (-half_x - 11, 16)],
    }
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 80, 90), (42, 255, 255))
    scores: dict[str, int] = {}
    for name, board_points in patches.items():
        polygon = np.rint(
            project_points(board_to_pixel, np.asarray(board_points, dtype=np.float32))
        ).astype(np.int32)
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(mask, polygon, 255, cv2.LINE_AA)
        scores[name] = int(np.count_nonzero((yellow > 0) & (mask > 0)))
    return scores


def load_base_calibration(path: Path) -> tuple[np.ndarray, float] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("quality", {}).get("passed", False):
        return None
    matrix = np.asarray(
        payload["homography_normalized_image_to_base_mm"], dtype=float
    ).reshape(3, 3)
    return matrix, float(payload["plane_z_mm"])


def draw_overlay(
    image: np.ndarray,
    polygon_px: np.ndarray,
    board_to_pixel: np.ndarray,
    placements: list[dict[str, Any]],
) -> np.ndarray:
    canvas = image.copy()
    cv2.polylines(
        canvas, [np.rint(polygon_px).astype(np.int32)], True, (60, 245, 230), 4,
        cv2.LINE_AA,
    )
    for placement in placements:
        component_type = placement["component_type"]
        color = TYPE_COLORS[component_type]
        box = np.rint(
            project_points(board_to_pixel, nominal_box_points(placement))
        ).astype(np.int32)
        center_board = placement["center_board_mm"]
        center = np.rint(project_points(
            board_to_pixel,
            [[float(center_board["x"]), float(center_board["y"])]]
        )[0]).astype(int)
        cv2.polylines(canvas, [box], True, color, 2, cv2.LINE_AA)
        cv2.drawMarker(
            canvas, tuple(center), color, cv2.MARKER_CROSS, 15, 2, cv2.LINE_AA
        )
        label = short_label(placement["slot_id"], component_type)
        anchor = (int(center[0] + 6), int(center[1] - 6))
        cv2.putText(
            canvas, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.42,
            (8, 12, 16), 3, cv2.LINE_AA,
        )
        cv2.putText(
            canvas, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, 0.42,
            color, 1, cv2.LINE_AA,
        )

    center = project_points(board_to_pixel, [[0.0, 0.0]])[0]
    x_tip = project_points(board_to_pixel, [[30.0, 0.0]])[0]
    y_tip = project_points(board_to_pixel, [[0.0, 30.0]])[0]
    cv2.arrowedLine(
        canvas, tuple(np.rint(center).astype(int)), tuple(np.rint(x_tip).astype(int)),
        (255, 120, 40), 3, cv2.LINE_AA, tipLength=0.13,
    )
    cv2.arrowedLine(
        canvas, tuple(np.rint(center).astype(int)), tuple(np.rint(y_tip).astype(int)),
        (40, 245, 245), 3, cv2.LINE_AA, tipLength=0.13,
    )
    cv2.putText(
        canvas, "+X", tuple(np.rint(x_tip + (6, -5)).astype(int)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 120, 40), 2, cv2.LINE_AA,
    )
    cv2.putText(
        canvas, "+Y", tuple(np.rint(y_tip + (6, -5)).astype(int)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 245, 245), 2, cv2.LINE_AA,
    )

    minimum = np.floor(np.min(polygon_px, axis=0) - 75).astype(int)
    maximum = np.ceil(np.max(polygon_px, axis=0) + 75).astype(int)
    x0 = int(np.clip(minimum[0], 0, image.shape[1] - 1))
    y0 = int(np.clip(minimum[1], 0, image.shape[0] - 1))
    x1 = int(np.clip(maximum[0], x0 + 1, image.shape[1]))
    y1 = int(np.clip(maximum[1], y0 + 1, image.shape[0]))
    crop = canvas[y0:y1, x0:x1]
    return cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)


def export_coordinates(
    args: argparse.Namespace,
    polygon_normalized: np.ndarray,
    samples: np.ndarray,
    image_path: Path,
) -> tuple[Path, Path, Path]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read S22 snapshot: {image_path}")
    height, width = image.shape[:2]
    pixel_scale = np.float32([width - 1, height - 1])
    polygon_px = polygon_normalized * pixel_scale

    layout = json.loads(args.layout_file.read_text(encoding="utf-8"))
    physical_board = json.loads(
        args.physical_board_file.read_text(encoding="utf-8")
    )
    layout, physical_override_slots = apply_component_slot_overrides(
        layout, physical_board
    )
    board_x_mm = float(layout["board"]["size_mm"]["x"])
    board_y_mm = float(layout["board"]["size_mm"]["y"])
    board_to_normalized = cv2.getPerspectiveTransform(
        board_source_corners(board_x_mm, board_y_mm),
        polygon_normalized.astype(np.float32),
    )
    board_to_pixel = cv2.getPerspectiveTransform(
        board_source_corners(board_x_mm, board_y_mm),
        polygon_px.astype(np.float32),
    )

    handle_scores = yellow_handle_scores(
        image, board_to_pixel, board_x_mm, board_y_mm
    )
    ordered_scores = sorted(handle_scores.items(), key=lambda item: item[1], reverse=True)
    orientation_valid = bool(
        ordered_scores[0][0] == "+Y"
        and ordered_scores[0][1] >= args.minimum_handle_yellow_pixels
        and ordered_scores[0][1] >= max(1, ordered_scores[1][1]) * args.handle_score_ratio
    )
    if not orientation_valid and not args.allow_unverified_orientation:
        raise RuntimeError(
            "fixture +Y handle was not uniquely detected at the image-top edge; "
            f"scores={handle_scores}. Do not export potentially 180-degree-flipped slots."
        )

    sample_pixels = samples * pixel_scale
    median_pixels = np.median(sample_pixels, axis=0)
    corner_jitter_px = np.linalg.norm(sample_pixels - median_pixels, axis=2)
    max_jitter_px = float(np.max(corner_jitter_px))
    if max_jitter_px > args.maximum_corner_jitter_px:
        raise RuntimeError(
            f"board polygon is not stable: max corner jitter={max_jitter_px:.2f}px "
            f"> {args.maximum_corner_jitter_px:.2f}px"
        )

    base_calibration = load_base_calibration(args.calibration_file)
    placements_output = []
    for placement in layout["placements"]:
        center_board = placement["center_board_mm"]
        center_xy = (float(center_board["x"]), float(center_board["y"]))
        center_normalized = project_points(board_to_normalized, [center_xy])[0]
        center_pixel = center_normalized * pixel_scale
        item = {
            "slot_id": placement["slot_id"],
            "component_type": placement["component_type"],
            "label": short_label(placement["slot_id"], placement["component_type"]),
            "center_board_mm": [center_xy[0], center_xy[1]],
            "top_z_mm_nominal": float(placement["top_z_mm_nominal"]),
            "long_axis_board_deg": float(placement["long_axis_deg_in_board"]),
            "center_image_normalized": [
                float(center_normalized[0]), float(center_normalized[1])
            ],
            "center_image_px": [float(center_pixel[0]), float(center_pixel[1])],
            "long_axis_image_deg": angle_image_deg(
                board_to_normalized,
                center_xy,
                float(placement["long_axis_deg_in_board"]),
            ),
            "nominal_size_mm": placement["nominal_size_mm"],
            "coordinate_source": placement.get(
                "coordinate_source", "Unity-derived CAD candidate"
            ),
            "coordinate_status": placement.get(
                "coordinate_status", "requires physical TCP-hover validation"
            ),
        }
        if base_calibration is not None:
            image_to_base, plane_z_mm = base_calibration
            center_base = project_homogeneous(image_to_base, center_normalized)
            direction_radians = math.radians(item["long_axis_board_deg"])
            direction_board = np.asarray((
                math.cos(direction_radians), math.sin(direction_radians)
            ))
            direction_normalized = project_points(
                board_to_normalized,
                [center_xy, np.asarray(center_xy) + direction_board],
            )
            base_a = project_homogeneous(image_to_base, direction_normalized[0])
            base_b = project_homogeneous(image_to_base, direction_normalized[1])
            base_delta = base_b - base_a
            item["center_base_mm"] = [
                float(center_base[0]), float(center_base[1]), plane_z_mm
            ]
            item["long_axis_base_deg"] = float(math.degrees(
                math.atan2(float(base_delta[1]), float(base_delta[0]))
            ))
        placements_output.append(item)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    created_at = datetime.now().astimezone().isoformat()
    top_length_px = float(np.linalg.norm(polygon_px[1] - polygon_px[0]))
    bottom_length_px = float(np.linalg.norm(polygon_px[2] - polygon_px[3]))
    left_length_px = float(np.linalg.norm(polygon_px[3] - polygon_px[0]))
    right_length_px = float(np.linalg.norm(polygon_px[2] - polygon_px[1]))
    payload = {
        "schema_version": 1,
        "created_at": created_at,
        "station": "assembly",
        "status": (
            "BOARD_RELATIVE_AND_IMAGE_COORDINATES_VALID"
            if orientation_valid else "ORIENTATION_UNVERIFIED"
        ),
        "robot_motion_sent": False,
        "source_image": str(image_path),
        "source_layout": str(args.layout_file),
        "source_physical_board": str(args.physical_board_file),
        "physical_override_slots": physical_override_slots,
        "source_polygon_topic": args.polygon_topic,
        "coordinate_frames": {
            "board": {
                "origin": "geometric PCB center",
                "+x": "toward image left in the current assembly fixture orientation",
                "+y": "toward fixture handle / image top",
                "+z": "upward from PCB top",
                "units": "mm",
            },
            "image": {
                "origin": "top-left of source image",
                "+x": "right",
                "+y": "down",
                "size_px": [width, height],
            },
            "robot_base": (
                "CALIBRATED" if base_calibration is not None
                else "UNAVAILABLE: S22 plane calibration has not passed"
            ),
        },
        "board": {
            "size_mm": [board_x_mm, board_y_mm],
            "polygon_normalized_tl_tr_br_bl": polygon_normalized.astype(float).tolist(),
            "polygon_px_tl_tr_br_bl": polygon_px.astype(float).tolist(),
            "center_image_px": np.mean(polygon_px, axis=0).astype(float).tolist(),
            "edge_lengths_px": {
                "top": top_length_px,
                "right": right_length_px,
                "bottom": bottom_length_px,
                "left": left_length_px,
            },
            "sample_count": int(samples.shape[0]),
            "max_corner_jitter_px": max_jitter_px,
            "fixture_handle_yellow_scores": handle_scores,
            "orientation_valid": orientation_valid,
            "orientation_rule": "fixture handle is board +Y; board +X is image left",
        },
        "homography_board_mm_to_normalized_image": board_to_normalized.astype(float).tolist(),
        "placements": placements_output,
        "warnings": [
            "S22 pixel coordinates are valid only while the camera and stopped PCB remain fixed.",
            "Inductor and SMD coordinates use physical-board overrides; all slots still require a no-descent TCP hover before placement.",
            "Nominal top Z is not a robot TCP descent coordinate.",
        ],
    }

    args.archive_dir.mkdir(parents=True, exist_ok=True)
    archive_json = args.archive_dir / f"assembly_slot_coordinates_{timestamp}.json"
    archive_csv = args.archive_dir / f"assembly_slot_coordinates_{timestamp}.csv"
    archive_overlay = args.archive_dir / f"assembly_slot_coordinates_{timestamp}.png"
    atomic_write_text(
        archive_json,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    rows = [
        "slot_id,component_type,label,x_board_mm,y_board_mm,top_z_mm_nominal,"
        "long_axis_board_deg,image_x_px,image_y_px,long_axis_image_deg,"
        "base_x_mm,base_y_mm,base_z_mm,long_axis_base_deg"
    ]
    for item in placements_output:
        base = item.get("center_base_mm", ["", "", ""])
        rows.append(
            f"{item['slot_id']},{item['component_type']},{item['label']},"
            f"{item['center_board_mm'][0]:.4f},{item['center_board_mm'][1]:.4f},"
            f"{item['top_z_mm_nominal']:.4f},{item['long_axis_board_deg']:.3f},"
            f"{item['center_image_px'][0]:.3f},{item['center_image_px'][1]:.3f},"
            f"{item['long_axis_image_deg']:.3f},"
            f"{base[0] if base[0] == '' else f'{base[0]:.3f}'},"
            f"{base[1] if base[1] == '' else f'{base[1]:.3f}'},"
            f"{base[2] if base[2] == '' else f'{base[2]:.3f}'},"
            f"{item.get('long_axis_base_deg', '')}"
        )
    atomic_write_text(archive_csv, "\n".join(rows) + "\n")
    overlay = draw_overlay(
        image, polygon_px, board_to_pixel, layout["placements"]
    )
    if not cv2.imwrite(str(archive_overlay), overlay, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
        raise RuntimeError(f"could not write overlay: {archive_overlay}")

    export_json = args.export_prefix.with_suffix(".json")
    export_csv = args.export_prefix.with_suffix(".csv")
    export_overlay = args.export_prefix.with_name(
        args.export_prefix.name + "_overlay.png"
    )
    export_json.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive_json, export_json)
    shutil.copy2(archive_csv, export_csv)
    shutil.copy2(archive_overlay, export_overlay)
    atomic_symlink(archive_json, args.archive_dir / "assembly_slot_coordinates_latest.json")
    atomic_symlink(archive_csv, args.archive_dir / "assembly_slot_coordinates_latest.csv")
    atomic_symlink(archive_overlay, args.archive_dir / "assembly_slot_coordinates_latest.png")
    return export_json, export_csv, export_overlay


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the stopped empty PCB at the assembly station and export "
            "all 25 board-relative/image coordinates. No motion is commanded."
        )
    )
    parser.add_argument(
        "--polygon-topic",
        default="/vision/conveyor/assembly/board_polygon_normalized",
    )
    parser.add_argument(
        "--snapshot-service",
        default="/camera2/capture_inspection_frame",
    )
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--maximum-corner-jitter-px", type=float, default=6.0)
    parser.add_argument("--minimum-handle-yellow-pixels", type=int, default=80)
    parser.add_argument("--handle-score-ratio", type=float, default=1.5)
    parser.add_argument("--allow-unverified-orientation", action="store_true")
    parser.add_argument("--layout-file", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument(
        "--physical-board-file", type=Path, default=DEFAULT_PHYSICAL_BOARD
    )
    parser.add_argument("--calibration-file", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--export-prefix", type=Path, default=DEFAULT_EXPORT_PREFIX)
    args = parser.parse_args()
    if args.frames < 5:
        parser.error("--frames must be at least 5")
    if args.timeout_seconds <= 0.0:
        parser.error("--timeout-seconds must be > 0")
    for name in (
        "layout_file", "physical_board_file", "calibration_file",
        "archive_dir", "export_prefix",
    ):
        value = Path(os.path.abspath(getattr(args, name).expanduser()))
        setattr(args, name, value)
    return args


def main() -> int:
    args = parse_args()
    if not args.layout_file.is_file():
        raise SystemExit(f"layout file is missing: {args.layout_file}")
    if not args.physical_board_file.is_file():
        raise SystemExit(
            f"physical board override file is missing: {args.physical_board_file}"
        )
    rclpy.init()
    node = PolygonCollector(args)
    try:
        polygon = node.collect()
        samples = np.asarray(node.samples, dtype=np.float32)
        image_path = node.capture_snapshot()
    except KeyboardInterrupt:
        return 130
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    json_path, csv_path, overlay_path = export_coordinates(
        args, polygon, samples, image_path
    )
    print("\nASSEMBLY SLOT COORDINATES CAPTURED - NO ROBOT MOTION")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print(f"Overlay: {overlay_path}")
    if not args.calibration_file.is_file():
        print("Robot Base XYZ: unavailable (S22 plane calibration is missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
