#!/usr/bin/env python3
"""Evaluate SMD close-view OBB center/angle repeatability; never moves the robot."""
import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from detect_smd_section import register_clean_section


def normalize_axis(angle):
    return (float(angle) + 90.0) % 180.0 - 90.0


def box_axis(points):
    (_, _), (width, height), angle = cv2.minAreaRect(points.astype(np.float32))
    if height > width:
        angle += 90.0
    return normalize_axis(angle)


def wrapped(values, reference):
    return (np.asarray(values, float) - reference + 90.0) % 180.0 - 90.0


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=root / "data/smd_section_holdout_1920")
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--model", type=Path, default=root / "models/smd_obb/pilot_01/weights/best.pt")
    parser.add_argument("--output", type=Path, default=root / "data/smd_obb_holdout_evaluation.json")
    parser.add_argument("--confidence", type=float, default=.50)
    parser.add_argument("--image-size", type=int, default=960)
    parser.add_argument("--max-center-span-px", type=float, default=3.5)
    parser.add_argument("--max-angle-span-deg", type=float, default=1.5)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    width, height = map(int, config["canonical_size"])
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    model = YOLO(str(args.model))
    samples = [[] for _ in range(10)]
    frame_results = []
    paths = sorted(args.frames.glob("*.jpg"))
    if len(paths) < 6:
        raise RuntimeError(f"at least 6 frames required, got {len(paths)}")
    for path in paths:
        image = cv2.imread(str(path))
        section, registration = register_clean_section(image, config, args.config)
        transform = cv2.getPerspectiveTransform(section.astype(np.float32), destination)
        rectified = cv2.warpPerspective(image, transform, (width, height), flags=cv2.INTER_CUBIC)
        result = model.predict(rectified, imgsz=args.image_size, conf=args.confidence,
                               device="0", verbose=False)[0]
        candidates = []
        if result.obb is not None:
            boxes = result.obb.xyxyxyxy.cpu().numpy()
            scores = result.obb.conf.cpu().numpy()
            for points, score in zip(boxes, scores):
                candidates.append({"center": points.mean(axis=0), "angle": box_axis(points),
                                   "confidence": float(score)})
        if len(candidates) != 10:
            raise RuntimeError(f"{path.name}: OBB requires exactly 10 detections, got {len(candidates)}")
        by_y = sorted(candidates, key=lambda item: item["center"][1])
        ordered = []
        for start in (0, 5):
            ordered.extend(sorted(by_y[start:start + 5], key=lambda item: item["center"][0]))
        for index, item in enumerate(ordered):
            samples[index].append(item)
        frame_results.append({"frame": str(path), "registration_inliers": registration["inliers"],
                              "detection_count": len(ordered)})
    detections = []
    all_stable = True
    for index, items in enumerate(samples, 1):
        centers = np.asarray([item["center"] for item in items], float)
        angles = np.asarray([item["angle"] for item in items], float)
        reference = float(np.median(angles))
        unwrapped = reference + wrapped(angles, reference)
        center_span = np.ptp(centers, axis=0)
        angle_span = float(np.ptp(unwrapped))
        stable = float(center_span.max()) <= args.max_center_span_px and angle_span <= args.max_angle_span_deg
        all_stable &= stable
        detections.append({"instance_index": index,
                           "center_canonical_pixel_median": np.round(np.median(centers, axis=0), 3).tolist(),
                           "center_span_pixel": np.round(center_span, 3).tolist(),
                           "long_axis_canonical_deg_median": round(float(np.median(unwrapped)), 4),
                           "angle_samples_deg": np.round(unwrapped, 4).tolist(),
                           "angle_span_deg": round(angle_span, 4),
                           "confidence_median": round(float(np.median([item["confidence"] for item in items])), 4),
                           "stable": stable})
    payload = {"schema_version": 1, "mode": "smd_obb_multiframe_holdout",
               "timestamp_unix": time.time(), "robot_motion_authorized": False,
               "model": str(args.model), "frame_count": len(paths),
               "limits": {"max_center_span_px": args.max_center_span_px,
                          "max_angle_span_deg": args.max_angle_span_deg},
               "all_parts_stable": all_stable, "frames": frame_results, "detections": detections}
    args.output.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    if not all_stable:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
