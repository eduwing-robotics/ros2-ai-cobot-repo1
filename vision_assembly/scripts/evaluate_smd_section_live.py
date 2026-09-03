#!/usr/bin/env python3
"""Evaluate learned SMD masks over multiple close-view frames; never moves the robot."""
import argparse
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from detect_smd_section import register_clean_section


SMD_CLASS_ID = 2


def axis_angle(points):
    (_, _), (width, height), angle = cv2.minAreaRect(points.astype(np.float32))
    if height > width:
        angle += 90.0
    return (float(angle) + 90.0) % 180.0 - 90.0


def wrapped_delta(values, reference):
    values = np.asarray(values, dtype=float)
    return (values - reference + 90.0) % 180.0 - 90.0


def frame_detections(image, config, config_path, model, args):
    section, registration = register_clean_section(image, config, config_path)
    width, height = map(int, config["canonical_size"])
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    homography = cv2.getPerspectiveTransform(section.astype(np.float32), destination)
    rectified = cv2.warpPerspective(image, homography, (width, height), flags=cv2.INTER_CUBIC)
    prediction = model.predict(
        rectified, imgsz=args.image_size, conf=args.confidence, iou=args.iou,
        device=args.device, retina_masks=True, verbose=False,
    )[0]
    candidates = []
    if prediction.masks is not None and prediction.boxes is not None:
        for confidence, class_id, polygon in zip(
            prediction.boxes.conf.cpu().tolist(),
            prediction.boxes.cls.cpu().tolist(),
            prediction.masks.xy,
        ):
            points = np.asarray(polygon, dtype=np.float32)
            if int(class_id) != SMD_CLASS_ID or len(points) < 3:
                continue
            moments = cv2.moments(points)
            if abs(moments["m00"]) < 1e-6:
                continue
            center = np.array([moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]])
            candidates.append({
                "confidence": float(confidence), "center": center,
                "angle": axis_angle(points), "polygon": points,
            })
    accepted = []
    for candidate in sorted(candidates, key=lambda item: item["confidence"], reverse=True):
        if any(np.linalg.norm(candidate["center"] - old["center"]) < args.duplicate_radius for old in accepted):
            continue
        accepted.append(candidate)
    if len(accepted) < 10:
        raise RuntimeError(f"learned SMD detection requires at least 10 masks; got {len(accepted)}")
    # The tray recipe guarantees a 2x5 SMD section. Keep the ten strongest
    # spatially distinct learned masks; multi-frame gates reject false choices.
    accepted = accepted[:10]
    by_y = sorted(accepted, key=lambda item: item["center"][1])
    ordered = []
    for start in (0, 5):
        ordered.extend(sorted(by_y[start:start + 5], key=lambda item: item["center"][0]))
    return registration, rectified, ordered


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=root / "data/smd_section_live_frames")
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--model", type=Path, default=root / "models/tray_segmentation/pilot_06/weights/best.pt")
    parser.add_argument("--output", type=Path, default=root / "data/smd_section_live_evaluation.json")
    parser.add_argument("--overlay", type=Path, default=root / "data/smd_section_live_overlay.jpg")
    parser.add_argument("--image-size", type=int, default=1280)
    parser.add_argument("--confidence", type=float, default=0.10)
    parser.add_argument("--iou", type=float, default=0.99)
    parser.add_argument("--device", default="0")
    parser.add_argument("--duplicate-radius", type=float, default=20.0)
    parser.add_argument("--max-center-span-px", type=float, default=3.5)
    parser.add_argument("--max-angle-span-deg", type=float, default=3.5)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths = sorted(args.frames.glob("*.jpg"))
    if len(paths) < 6:
        raise RuntimeError(f"at least 6 frames required; got {len(paths)}")
    model = YOLO(str(args.model))
    samples = [[] for _ in range(10)]
    registrations = []
    last_rectified = None
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"cannot read {path}")
        registration, last_rectified, detections = frame_detections(image, config, args.config, model, args)
        registrations.append({"frame": str(path), **registration})
        for index, detection in enumerate(detections):
            samples[index].append(detection)

    results = []
    stable = True
    for index, items in enumerate(samples, 1):
        centers = np.asarray([item["center"] for item in items], dtype=float)
        angles = np.asarray([item["angle"] for item in items], dtype=float)
        reference = float(np.median(angles))
        unwrapped = reference + wrapped_delta(angles, reference)
        center_span = np.ptp(centers, axis=0)
        angle_span = float(np.ptp(unwrapped))
        item_stable = float(np.max(center_span)) <= args.max_center_span_px and angle_span <= args.max_angle_span_deg
        stable = stable and item_stable
        results.append({
            "instance_index": index,
            "center_canonical_pixel_median": np.round(np.median(centers, axis=0), 3).tolist(),
            "center_span_pixel": np.round(center_span, 3).tolist(),
            "long_axis_canonical_deg_median": round(float(np.median(unwrapped)), 4),
            "angle_span_deg": round(angle_span, 4),
            "confidence_median": round(float(np.median([item["confidence"] for item in items])), 4),
            "stable": item_stable,
        })

    annotated = last_rectified.copy()
    for item in results:
        center = np.rint(item["center_canonical_pixel_median"]).astype(int)
        angle = math.radians(item["long_axis_canonical_deg_median"])
        direction = np.array([math.cos(angle), math.sin(angle)])
        cv2.circle(annotated, tuple(center), 5, (0, 0, 255), -1)
        cv2.line(annotated, tuple(np.rint(center - direction * 28).astype(int)),
                 tuple(np.rint(center + direction * 28).astype(int)), (255, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(annotated, str(item["instance_index"]), tuple(center + [8, -8]),
                    cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 255, 255), 2, cv2.LINE_AA)
    payload = {
        "schema_version": 1, "mode": "learned_multiframe_smd_section_evaluation",
        "timestamp_unix": time.time(), "robot_motion_authorized": False,
        "tape_required": False, "model": str(args.model), "frame_count": len(paths),
        "confidence_threshold": args.confidence, "image_size": args.image_size,
        "stability_limits": {"max_center_span_px": args.max_center_span_px,
                             "max_angle_span_deg": args.max_angle_span_deg},
        "all_parts_stable": stable, "registrations": registrations, "detections": results,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cv2.imwrite(str(args.overlay), annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(json.dumps(payload, indent=2))
    if not stable:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
