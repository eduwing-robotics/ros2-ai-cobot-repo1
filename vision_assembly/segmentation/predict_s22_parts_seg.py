#!/usr/bin/env python3
"""Run one S22 segmentation preview and emit provider-contract evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from common import CLASS_COLORS, CLASS_NAMES, NORMAL_CLASS_COUNTS, polygon_area

PROJECT_DIR = Path(__file__).resolve().parents[2]
INSPECTION_DIR = Path(__file__).resolve().parents[1] / "inspection"
if str(INSPECTION_DIR) not in sys.path:
    sys.path.insert(0, str(INSPECTION_DIR))
from layout_overrides import apply_component_slot_overrides


COMPONENT_TO_CLASS = {
    "GPU": "gpu",
    "HBM": "hbm",
    "Power Module": "power_module",
    "VRM": "vrm",
    "Inductor": "inductor",
    "SMD Capacitor": "smd_capacitor",
}
CLASS_CONFIDENCE = {
    "gpu": 0.20,
    "hbm": 0.20,
    "power_module": 0.10,
    "vrm": 0.20,
    "inductor": 0.20,
    "smd_capacitor": 0.10,
}


def image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def long_axis_angle_deg(points: np.ndarray) -> float:
    (_, _), (width, height), angle = cv2.minAreaRect(np.asarray(points, np.float32))
    if width < height:
        angle += 90.0
    return float(angle % 180.0)


def polygon_centroid(points: np.ndarray) -> np.ndarray:
    contour = np.asarray(points, np.float32)
    moments = cv2.moments(contour)
    if abs(float(moments["m00"])) > 1e-6:
        return np.asarray(
            (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]),
            np.float32,
        )
    return np.mean(contour, axis=0).astype(np.float32)


def box_iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(float(a[0]), float(b[0]))
    y1 = max(float(a[1]), float(b[1]))
    x2 = min(float(a[2]), float(b[2]))
    y2 = min(float(a[3]), float(b[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, float(a[2] - a[0])) * max(0.0, float(a[3] - a[1]))
    area_b = max(0.0, float(b[2] - b[0])) * max(0.0, float(b[3] - b[1]))
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def suppress_duplicate_masks(candidates: list[dict], iou_threshold: float) -> list[dict]:
    """Keep the strongest same-class mask for each physical component."""
    kept: list[dict] = []
    for candidate in sorted(candidates, key=lambda item: item["confidence"], reverse=True):
        duplicate = any(
            candidate["class_id"] == previous["class_id"]
            and box_iou(candidate["box"], previous["box"]) >= iou_threshold
            for previous in kept
        )
        if not duplicate:
            kept.append(candidate)
    return kept


def load_expected_slots(project: Path, width: int, height: int) -> list[dict]:
    config = json.loads(
        (project / "vision_assembly/config/full_board_inspection.json").read_text(
            encoding="utf-8"
        )
    )
    layout = json.loads((project / config["board_layout"]).read_text(encoding="utf-8"))
    physical = json.loads(
        (project / config["physical_board"]).read_text(encoding="utf-8")
    )
    layout, _ = apply_component_slot_overrides(layout, physical)
    board = layout["board"]["size_mm"]
    board_width = float(board["x"])
    board_height = float(board["y"])
    mapping = config["coordinate_mapping"]
    sign_x = float(mapping.get("image_x_from_board_x_sign", 1.0))
    sign_y = float(mapping.get("image_y_from_board_y_sign", 1.0))
    slots = []
    for placement in layout["placements"]:
        class_name = COMPONENT_TO_CLASS[str(placement["component_type"])]
        center = placement["center_board_mm"]
        size = placement["nominal_size_mm"]
        slots.append(
            {
                "slot_id": str(placement["slot_id"]),
                "class_id": CLASS_NAMES.index(class_name),
                "class_name": class_name,
                "center": np.asarray(
                    (
                        (sign_x * float(center["x"]) / board_width + 0.5) * width,
                        (sign_y * float(center["y"]) / board_height + 0.5) * height,
                    ),
                    np.float32,
                ),
                "size": np.asarray(
                    (
                        float(size["x"]) / board_width * width,
                        float(size["y"]) / board_height * height,
                    ),
                    np.float32,
                ),
            }
        )
    return slots


def match_candidates_to_slots(candidates: list[dict], slots: list[dict]) -> list[dict]:
    possible = []
    for slot_index, slot in enumerate(slots):
        allowed = np.maximum(slot["size"] * 0.35, np.asarray((18.0, 18.0)))
        for candidate_index, candidate in enumerate(candidates):
            if candidate["class_id"] != slot["class_id"]:
                continue
            if candidate["confidence"] < CLASS_CONFIDENCE[slot["class_name"]]:
                continue
            delta = np.abs(candidate["center"] - slot["center"])
            if np.any(delta > allowed):
                continue
            distance = float(np.linalg.norm(delta / allowed))
            cost = distance - 0.20 * float(candidate["confidence"])
            possible.append((cost, slot_index, candidate_index, distance))
    assigned_slots = set()
    assigned_candidates = set()
    assignments = {}
    for _, slot_index, candidate_index, distance in sorted(possible):
        if slot_index in assigned_slots or candidate_index in assigned_candidates:
            continue
        assigned_slots.add(slot_index)
        assigned_candidates.add(candidate_index)
        assignments[slot_index] = (candidate_index, distance)
    return [
        {
            "slot": slot,
            "candidate": candidates[assignments[index][0]] if index in assignments else None,
            "normalized_slot_distance": assignments[index][1] if index in assignments else None,
        }
        for index, slot in enumerate(slots)
    ]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        type=Path,
        default=PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=root / "models/s22_parts_seg_candidate.pt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "runtime/inspection/segmentation/s22_parts",
    )
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--conf", type=float, default=0.01)
    parser.add_argument("--iou", type=float, default=0.55)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = args.image.resolve()
    weights = args.weights.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Inspection image does not exist: {image_path}")
    if not weights.is_file():
        raise FileNotFoundError(
            f"S22 segmentation weights do not exist: {weights}. Train the model first."
        )
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; run S22 segmentation on the RTX GPU host")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot decode inspection image: {image_path}")
    height, width = image.shape[:2]
    input_hash = image_sha256(image_path)
    calibration_id = input_hash[:16]
    model = YOLO(str(weights))
    result = model.predict(
        source=image,
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        nms=True,
        device=args.device,
        verbose=False,
        retina_masks=True,
    )[0]
    overlay = image.copy()
    tint = image.copy()
    detections = []
    counts = Counter()
    candidates = []
    if result.masks is not None and result.boxes is not None:
        polygons = result.masks.xy
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        confidences = result.boxes.conf.detach().cpu().numpy().astype(float)
        boxes = result.boxes.xyxy.detach().cpu().numpy().astype(float)
        raw_candidates = suppress_duplicate_masks(
            [
                {
                    "class_id": int(class_id),
                    "confidence": float(confidence),
                    "points": points_value,
                    "box": box,
                }
                for class_id, confidence, points_value, box in zip(
                    classes, confidences, polygons, boxes
                )
            ],
            args.iou,
        )
        for candidate in raw_candidates:
            class_id = candidate["class_id"]
            if not 0 <= class_id < len(CLASS_NAMES):
                continue
            points = np.asarray(candidate["points"], np.float32)
            if len(points) < 3 or polygon_area(points) < 4.0:
                continue
            candidate["points"] = points
            candidate["center"] = polygon_centroid(points)
            candidates.append(candidate)

    slots = load_expected_slots(PROJECT_DIR, width, height)
    assignments = match_candidates_to_slots(candidates, slots)
    for assignment in assignments:
        slot = assignment["slot"]
        candidate = assignment["candidate"]
        class_id = slot["class_id"]
        name = slot["class_name"]
        color = CLASS_COLORS[class_id]
        expected_center = slot["center"]
        if candidate is not None:
            confidence = candidate["confidence"]
            points = candidate["points"]
            contour = np.rint(points).astype(np.int32)
            cv2.fillPoly(tint, [contour], color)
            cv2.polylines(overlay, [contour], True, (10, 10, 10), 4, cv2.LINE_AA)
            cv2.polylines(overlay, [contour], True, color, 2, cv2.LINE_AA)
            center = candidate["center"]
            counts[name] += 1
            evidence = {
                "present": True,
                "class_id": int(class_id),
                "class_name": name,
                "class_confidence_threshold": CLASS_CONFIDENCE[name],
                "center_px": [float(center[0]), float(center[1])],
                "expected_center_px": [
                    float(expected_center[0]),
                    float(expected_center[1]),
                ],
                "normalized_slot_distance": assignment["normalized_slot_distance"],
                "long_axis_angle_deg_undirected": long_axis_angle_deg(points),
                "mask_area_px": polygon_area(points),
                "polygon_px": points.round(2).tolist(),
            }
        else:
            confidence = 0.0
            point = tuple(np.rint(expected_center).astype(int))
            cv2.drawMarker(
                overlay, point, (30, 30, 245), cv2.MARKER_TILTED_CROSS, 14, 2, cv2.LINE_AA
            )
            evidence = {
                "present": False,
                "class_id": int(class_id),
                "class_name": name,
                "class_confidence_threshold": CLASS_CONFIDENCE[name],
                "expected_center_px": [
                    float(expected_center[0]),
                    float(expected_center[1]),
                ],
            }
        detections.append(
            {
                "stage_id": "component_presence_and_pose",
                "slot_id": slot["slot_id"],
                "status": "UNKNOWN",
                "confidence": confidence,
                "calibration_id": calibration_id,
                "evidence": evidence,
            }
        )
    visible = np.any(tint != image, axis=2)
    blended = cv2.addWeighted(image, 0.76, tint, 0.24, 0.0)
    overlay[visible] = cv2.addWeighted(overlay, 0.68, blended, 0.32, 0.0)[visible]

    panel_height = 112
    panel = np.full((panel_height, width, 3), 20, np.uint8)
    cv2.putText(
        panel,
        "S22 PART SEGMENTATION | ADVISORY ONLY | FIXED SLOT MATCHING",
        (22, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (90, 230, 255),
        2,
        cv2.LINE_AA,
    )
    x = 22
    for class_id, name in enumerate(CLASS_NAMES):
        expected = NORMAL_CLASS_COUNTS[name]
        label = f"{name.upper()} {counts[name]}/{expected}"
        cv2.putText(
            panel,
            label,
            (x, 83),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            CLASS_COLORS[class_id],
            2,
            cv2.LINE_AA,
        )
        x += max(175, cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.58, 2)[0][0] + 34)
    visualization = np.vstack((panel, overlay))
    args.output.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_output = args.output / f"s22_parts_seg_{timestamp}.png"
    report_output = args.output / f"s22_parts_seg_{timestamp}.json"
    if not cv2.imwrite(str(image_output), visualization, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
        raise RuntimeError(f"Cannot save segmentation preview: {image_output}")
    report = {
        "schema_version": 1,
        "contract_id": "s22_hybrid_aoi_v1",
        "provider": "S22-trained YOLO instance segmentation",
        "authority": "ADVISORY_ONLY",
        "reason": "controlled defect validation and threshold calibration are not complete",
        "input_image": str(image_path),
        "input_sha256": input_hash,
        "weights": str(weights),
        "thresholds": {
            "model_floor": args.conf,
            "class_confidence": CLASS_CONFIDENCE,
            "duplicate_iou": args.iou,
        },
        "counts": {name: counts[name] for name in CLASS_NAMES},
        "expected_normal_counts": NORMAL_CLASS_COUNTS,
        "detections": detections,
        "raw_candidates_after_duplicate_suppression": len(candidates),
        "visualization": str(image_output),
    }
    report_output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for latest, target in (
        (args.output / "s22_parts_seg_latest.png", image_output),
        (args.output / "s22_parts_seg_latest.json", report_output),
    ):
        latest.unlink(missing_ok=True)
        latest.symlink_to(target.resolve())
    print(f"S22_SEG_DETECTIONS={len(detections)}")
    print(f"S22_SEG_COUNTS={json.dumps(report['counts'])}")
    print(f"S22_SEG_VISUALIZATION={image_output}")
    print(f"S22_SEG_REPORT={report_output}")
    print("S22_SEG_AUTHORITY=ADVISORY_ONLY")


if __name__ == "__main__":
    main()
