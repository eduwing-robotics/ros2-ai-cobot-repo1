#!/usr/bin/env python3
"""Compare an SMD OBB model with manually clicked four-corner labels."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def axis_deg(points):
    (_, _), (w, h), angle = cv2.minAreaRect(points.astype(np.float32))
    if h > w:
        angle += 90.0
    return (float(angle) + 90.0) % 180.0 - 90.0


def angle_error(a, b):
    return abs((float(a) - float(b) + 90.0) % 180.0 - 90.0)


def ordered(items):
    by_y = sorted(items, key=lambda x: x["center"][1])
    result = []
    for start in (0, 5):
        result.extend(sorted(by_y[start:start + 5], key=lambda x: x["center"][0]))
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=root / "datasets/smd_obb_plus35_raw")
    parser.add_argument("--model", type=Path, default=root / "models/smd_obb/pilot_03/weights/best.pt")
    parser.add_argument("--output", type=Path, default=root / "data/smd_obb_pilot03_manual_evaluation.json")
    parser.add_argument("--review", type=Path, default=root / "data/smd_obb_pilot03_prediction_review.jpg")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--max-angle-error", type=float, default=5.0)
    args = parser.parse_args()
    model = YOLO(str(args.model))
    records, review = [], None
    for split in ("val", "train"):
        for image_path in sorted((args.dataset / "images" / split).glob("*.jpg")):
            image = cv2.imread(str(image_path))
            h, w = image.shape[:2]
            label_path = args.dataset / "labels" / split / (image_path.stem + ".txt")
            gt = []
            for line in label_path.read_text().splitlines():
                values = list(map(float, line.split()))
                pts = np.asarray(values[1:9], float).reshape(4, 2) * [w, h]
                gt.append({"center": pts.mean(axis=0), "angle": axis_deg(pts), "points": pts})
            pred_result = model.predict(image, imgsz=960, conf=args.confidence, device="0", verbose=False)[0]
            pred = []
            if pred_result.obb is not None:
                for pts, conf in zip(pred_result.obb.xyxyxyxy.cpu().numpy(), pred_result.obb.conf.cpu().numpy()):
                    pred.append({"center": pts.mean(axis=0), "angle": axis_deg(pts), "points": pts,
                                 "confidence": float(conf)})
            gt, pred = ordered(gt), ordered(pred) if len(pred) == 10 else pred
            errors = [angle_error(p["angle"], g["angle"]) for g, p in zip(gt, pred)] if len(pred) == 10 else []
            records.append({"frame": image_path.name, "split": split, "detection_count": len(pred),
                            "angle_errors_deg": [round(x, 3) for x in errors],
                            "max_angle_error_deg": round(max(errors), 3) if errors else None,
                            "mean_angle_error_deg": round(float(np.mean(errors)), 3) if errors else None})
            if review is None and len(pred) == 10:
                review = image.copy()
                for i, (g, p) in enumerate(zip(gt, pred), 1):
                    cv2.polylines(review, [np.int32(g["points"])], True, (0, 255, 0), 2)
                    cv2.polylines(review, [np.int32(p["points"])], True, (255, 0, 255), 2)
                    c = tuple(np.int32(p["center"]))
                    cv2.putText(review, f"{i}:{errors[i-1]:.1f}deg", c, cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 255, 255), 1, cv2.LINE_AA)
    valid = [r for r in records if r["detection_count"] == 10]
    all_errors = [e for r in valid for e in r["angle_errors_deg"]]
    passed = len(valid) == len(records) and bool(all_errors) and max(all_errors) <= args.max_angle_error
    payload = {"model": str(args.model), "frames": len(records), "all_frames_detect_10": len(valid) == len(records),
               "mean_angle_error_deg": round(float(np.mean(all_errors)), 3) if all_errors else None,
               "max_angle_error_deg": round(max(all_errors), 3) if all_errors else None,
               "limit_deg": args.max_angle_error, "passed": passed, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if review is not None:
        cv2.imwrite(str(args.review), review)
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
