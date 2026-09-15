#!/usr/bin/env python3
"""Compute a part Base-XY target from registered tray-plane coordinates.

This is the tray equivalent of the ChArUco board-plane method used by the
vision-robot-conveyor-control branch.  It never commands the robot.  An
independently taught calibration with at least three non-collinear points is
required; Hand-Eye-derived detections must not be used as calibration points.
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np


def fit_affine(points):
    source = np.asarray([p["reference_pixel"] for p in points], dtype=float)
    target = np.asarray([p["base_xy_mm"] for p in points], dtype=float)
    design = np.c_[source, np.ones(len(source))]
    if np.linalg.matrix_rank(design) < 3:
        raise RuntimeError("calibration points are collinear or duplicated")
    matrix, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
    predicted = design @ matrix
    residual = np.linalg.norm(predicted - target, axis=1)
    return matrix, residual


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--detections", type=Path, default=root / "data/tray_detections_last.json")
    parser.add_argument("--calibration", type=Path, default=root / "config/tray_base_plane_calibration.json")
    parser.add_argument("--part-type", default="hbm")
    parser.add_argument("--instance-index", type=int, default=1)
    parser.add_argument("--max-residual-mm", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=root / "data/tray_plane_pick_target.json")
    args = parser.parse_args()

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    points = calibration.get("points", [])
    if calibration.get("status") != "VALIDATED" or len(points) < 3:
        raise RuntimeError(
            "tray plane is not VALIDATED: independently teach at least three "
            "widely separated reference_pixel/base_xy_mm points first"
        )
    matrix, residual = fit_affine(points)
    if float(np.max(residual)) > args.max_residual_mm:
        raise RuntimeError(
            f"tray-plane calibration residual {np.max(residual):.3f} mm exceeds "
            f"{args.max_residual_mm:.3f} mm"
        )

    payload = json.loads(args.detections.read_text(encoding="utf-8"))
    if payload.get("tray_registration") != "TRACKING":
        raise RuntimeError("tray registration is not TRACKING")
    matches = [d for d in payload.get("stable_detections", [])
               if d.get("part_type") == args.part_type
               and int(d.get("instance_index", -1)) == args.instance_index]
    if len(matches) != 1:
        raise RuntimeError(f"expected one stable target, found {len(matches)}")
    detection = matches[0]
    uv = np.asarray(detection["reference_center_pixel"], dtype=float)
    xy = np.r_[uv, 1.0] @ matrix
    if not np.all(np.isfinite(xy)):
        raise RuntimeError("computed target is not finite")
    result = {
        "schema_version": 1,
        "timestamp_unix": time.time(),
        "mode": "registered_tray_plane_no_robot_motion",
        "part_type": args.part_type,
        "instance_index": args.instance_index,
        "reference_center_pixel": uv.tolist(),
        "part_center_base_xy_mm": xy.tolist(),
        "long_axis_angle_base_deg": detection.get("long_axis_angle_base_deg"),
        "calibration_point_count": len(points),
        "calibration_residual_max_mm": float(np.max(residual)),
        "affine_reference_pixel_to_base_xy": matrix.tolist(),
        "z_source": "not_computed_use_validated_part_recipe_or_tray_plane_height",
        "robot_motion_authorized": false
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
