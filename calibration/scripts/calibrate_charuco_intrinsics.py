#!/usr/bin/env python3
"""Calibrate D435 color intrinsics from dedicated ChArUco images."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from charuco_common import detect_charuco, detector_parameters, load_config


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "intrinsic_1920_images.json"
DEFAULT_OUTPUT = ROOT / "data" / "camera_intrinsics_1920x1080_dedicated_candidate.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-images", type=int, default=20)
    args = parser.parse_args()
    payload = json.loads(args.data_file.read_text(encoding="utf-8"))
    config, dictionary, board = load_config()
    parameters = detector_parameters()
    corners, ids, indices = [], [], []
    image_size = None
    for sample in payload["samples"]:
        image = cv2.imread(str(args.data_file.parent / sample["image"]))
        if image is None:
            continue
        size = (image.shape[1], image.shape[0])
        if image_size is not None and image_size != size:
            raise SystemExit("Mixed image resolutions are not allowed")
        image_size = size
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, _, current_corners, current_ids, _ = detect_charuco(
            gray, dictionary, board, parameters
        )
        if current_ids is not None and len(current_ids) >= 12:
            corners.append(current_corners)
            ids.append(current_ids)
            indices.append(sample["index"])
    if len(corners) < args.min_images:
        raise SystemExit(f"Need at least {args.min_images} valid images; found {len(corners)}")
    rms, K, D, _, _, _, _, per_view = cv2.aruco.calibrateCameraCharucoExtended(
        corners, ids, board, image_size, None, None
    )
    per_view = np.asarray(per_view).reshape(-1)
    output = {
        "status": "candidate_not_active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_data": str(args.data_file),
        "used_sample_indices": indices,
        "image_width": image_size[0],
        "image_height": image_size[1],
        "camera_matrix": K.tolist(),
        "distortion_model": "plumb_bob",
        "distortion_coefficients": D.reshape(-1).tolist(),
        "calibration_rms_px": float(rms),
        "per_view_errors_px": per_view.tolist(),
        "per_view_error_median_px": float(np.median(per_view)),
        "per_view_error_max_px": float(np.max(per_view)),
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Images used: {len(corners)}")
    print(f"Calibration RMS: {rms:.4f} px")
    print(f"Per-view median/max: {np.median(per_view):.4f}/{np.max(per_view):.4f} px")
    print("K:\n", np.array2string(K, precision=6))
    print("D:", np.round(D.reshape(-1), 8).tolist())
    print(f"Saved candidate: {args.output}")


if __name__ == "__main__":
    main()
