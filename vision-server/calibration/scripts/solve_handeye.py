#!/usr/bin/env python3
"""Solve an FR5 eye-in-hand *candidate* from captured samples.

The active result is deliberately not the default output.  A candidate must be
independently validated before it is promoted for robot motion.
"""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

from charuco_common import detect_charuco, detector_parameters, load_config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "handeye_samples.json"
DEFAULT_OUTPUT = ROOT / "data" / "handeye_result_candidate.json"
ACTIVE_OUTPUT = ROOT / "data" / "handeye_result.json"
DEFAULT_MIN_CHARUCO_CORNERS = 12
DEFAULT_MIN_SAMPLES = 20


def image_quality_ok(sample, data_file, min_charuco_corners):
    image = data_file.parent / sample.get("image", "")
    if not image.is_file():
        return True, None
    frame = cv2.imread(str(image))
    if frame is None:
        return False, "unreadable image"
    config, dictionary, board = load_config()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, marker_ids, _, charuco_ids, _ = detect_charuco(
        gray, dictionary, board, detector_parameters()
    )
    marker_values = [] if marker_ids is None else marker_ids.flatten().tolist()
    if len(marker_values) != len(set(marker_values)):
        return False, "duplicate marker IDs"
    configured_ids = set(int(value) for value in board.ids.flatten())
    if any(int(value) not in configured_ids for value in marker_values):
        return False, "unknown marker IDs"
    corners = 0 if charuco_ids is None else len(charuco_ids)
    if corners < min_charuco_corners:
        return False, f"only {corners} corners"
    return True, None


def validate_camera_contract(samples):
    """Reject mixed new-format camera contracts and describe legacy data."""
    contracts = [sample.get("camera") for sample in samples]
    present = [contract for contract in contracts if contract is not None]
    if not present:
        return "legacy_samples_without_recorded_intrinsics"
    if len(present) != len(samples):
        raise SystemExit(
            "Dataset mixes samples with and without recorded CameraInfo. "
            "Split or reprocess the dataset before solving."
        )

    reference = present[0]
    reference_size = (
        int(reference["image_width"]),
        int(reference["image_height"]),
    )
    reference_k = np.asarray(reference["camera_matrix"], dtype=float)
    reference_d = np.asarray(reference["distortion_coefficients"], dtype=float)
    for index, contract in enumerate(present[1:], start=2):
        size = (int(contract["image_width"]), int(contract["image_height"]))
        same_k = np.allclose(
            np.asarray(contract["camera_matrix"], dtype=float),
            reference_k,
            rtol=0.0,
            atol=1e-9,
        )
        same_d = np.allclose(
            np.asarray(contract["distortion_coefficients"], dtype=float),
            reference_d,
            rtol=0.0,
            atol=1e-9,
        )
        if size != reference_size or not same_k or not same_d:
            raise SystemExit(
                f"Camera contract differs at sample {index}; mixed resolution or "
                "intrinsics are not allowed in one Hand-Eye solve."
            )
    return {
        "image_width": reference_size[0],
        "image_height": reference_size[1],
        "camera_matrix": reference_k.tolist(),
        "distortion_model": reference.get("distortion_model", ""),
        "distortion_coefficients": reference_d.tolist(),
        "image_frame_id": reference.get("image_frame_id", ""),
    }

METHODS = {
    "TSAI": cv2.CALIB_HAND_EYE_TSAI,
    "PARK": cv2.CALIB_HAND_EYE_PARK,
    "HORAUD": cv2.CALIB_HAND_EYE_HORAUD,
    "ANDREFF": cv2.CALIB_HAND_EYE_ANDREFF,
    "DANIILIDIS": cv2.CALIB_HAND_EYE_DANIILIDIS,
}


def transform(r, t):
    out = np.eye(4)
    out[:3, :3] = r
    out[:3, 3] = np.asarray(t).reshape(3)
    return out


def rotation_angle_deg(r):
    value = np.clip((np.trace(r) - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(value)))


def solve(samples, convention, method_name, method):
    rg2b, tg2b, rt2c, tt2c = [], [], [], []
    for sample in samples:
        robot = sample["robot"]
        rg2b.append(Rotation.from_euler(convention, robot["flange_abc_deg"], degrees=True).as_matrix())
        tg2b.append(np.asarray(robot["flange_xyz_mm"], dtype=float) / 1000.0)
        target = sample["target_to_camera"]
        rt2c.append(np.asarray(target["rotation_matrix"], dtype=float))
        tt2c.append(np.asarray(target["translation_m"], dtype=float))

    rc2g, tc2g = cv2.calibrateHandEye(rg2b, tg2b, rt2c, tt2c, method=method)
    if not np.all(np.isfinite(rc2g)) or not np.all(np.isfinite(tc2g)):
        raise ValueError("non-finite solution")

    base_targets = []
    gtc = transform(rc2g, tc2g)
    for rg, tg, rt, tt in zip(rg2b, tg2b, rt2c, tt2c):
        base_targets.append(transform(rg, tg) @ gtc @ transform(rt, tt))

    xyz = np.asarray([t[:3, 3] for t in base_targets])
    center_xyz = np.median(xyz, axis=0)
    translation_errors_mm = np.linalg.norm(xyz - center_xyz, axis=1) * 1000.0
    center_rotation = Rotation.from_matrix([t[:3, :3] for t in base_targets]).mean().as_matrix()
    rotation_errors_deg = np.asarray([
        rotation_angle_deg(center_rotation.T @ t[:3, :3]) for t in base_targets
    ])
    return {
        "euler_convention": convention,
        "method": method_name,
        "camera_to_flange": {
            "rotation_matrix": rc2g.tolist(),
            "translation_m": np.asarray(tc2g).reshape(3).tolist(),
        },
        "fixed_target_in_base_median": {
            "rotation_matrix": center_rotation.tolist(),
            "translation_m": center_xyz.tolist(),
        },
        "validation": {
            "translation_median_mm": float(np.median(translation_errors_mm)),
            "translation_mean_mm": float(np.mean(translation_errors_mm)),
            "translation_max_mm": float(np.max(translation_errors_mm)),
            "rotation_median_deg": float(np.median(rotation_errors_deg)),
            "rotation_mean_deg": float(np.mean(rotation_errors_deg)),
            "rotation_max_deg": float(np.max(rotation_errors_deg)),
            "translation_errors_mm": translation_errors_mm.tolist(),
            "rotation_errors_deg": rotation_errors_deg.tolist(),
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Solve a non-active Eye-in-Hand candidate from ChArUco samples."
    )
    parser.add_argument("--samples", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument(
        "--min-charuco-corners", type=int, default=DEFAULT_MIN_CHARUCO_CORNERS
    )
    parser.add_argument(
        "--allow-active-overwrite",
        action="store_true",
        help=(
            "Explicitly allow writing handeye_result.json. A timestamped backup is "
            "created first; independent validation is still the operator's responsibility."
        ),
    )
    args = parser.parse_args()
    if args.min_samples < 5:
        parser.error("--min-samples must be at least 5")
    if not 6 <= args.min_charuco_corners <= 24:
        parser.error("--min-charuco-corners must be between 6 and 24")
    try:
        writes_active = args.output.resolve() == ACTIVE_OUTPUT.resolve()
    except FileNotFoundError:
        writes_active = args.output.absolute() == ACTIVE_OUTPUT.absolute()
    if writes_active and not args.allow_active_overwrite:
        parser.error(
            "Refusing to overwrite the active handeye_result.json. Write a candidate "
            "file, validate it independently, then use --allow-active-overwrite only "
            "for an intentional promotion."
        )
    return args, writes_active


def main():
    args, writes_active = parse_args()
    payload = json.loads(args.samples.read_text(encoding="utf-8"))
    all_samples = payload["samples"]
    camera_contract = validate_camera_contract(all_samples)
    samples = []
    excluded_reasons = {}
    for sample in all_samples:
        if (
            sample.get("detected_charuco_corners", args.min_charuco_corners)
            < args.min_charuco_corners
        ):
            excluded_reasons[sample["index"]] = "low saved corner count"
            continue
        valid, reason = image_quality_ok(
            sample, args.samples, args.min_charuco_corners
        )
        if not valid:
            excluded_reasons[sample["index"]] = reason
            continue
        samples.append(sample)
    excluded = sorted(excluded_reasons)
    if len(samples) < args.min_samples:
        raise SystemExit(
            f"Only {len(samples)} usable samples; --min-samples={args.min_samples}"
        )
    candidates = []
    for convention in ("xyz", "XYZ", "zyx", "ZYX"):
        for method_name, method in METHODS.items():
            try:
                result = solve(samples, convention, method_name, method)
                score = result["validation"]["translation_median_mm"]
                score += 2.0 * result["validation"]["rotation_median_deg"]
                result["score"] = score
                candidates.append(result)
            except (cv2.error, ValueError):
                pass
    candidates.sort(key=lambda x: x["score"])
    if not candidates:
        raise SystemExit("No finite Hand-Eye candidate could be solved")
    best = candidates[0]
    output = {
        "status": "candidate_not_active_no_robot_motion_until_approved",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Do not use for robot motion until independent validation passes.",
        "source_samples": str(args.samples),
        "source_samples_sha256": hashlib.sha256(args.samples.read_bytes()).hexdigest(),
        "camera_contract": camera_contract,
        "captured_sample_count": len(all_samples),
        "sample_count": len(samples),
        "minimum_charuco_corners": args.min_charuco_corners,
        "used_sample_indices": [sample["index"] for sample in samples],
        "excluded_sample_indices": excluded,
        "excluded_sample_reasons": excluded_reasons,
        "best": best,
        "candidate_summary": [
            {
                "euler_convention": c["euler_convention"],
                "method": c["method"],
                "translation_median_mm": c["validation"]["translation_median_mm"],
                "translation_max_mm": c["validation"]["translation_max_mm"],
                "rotation_median_deg": c["validation"]["rotation_median_deg"],
                "rotation_max_deg": c["validation"]["rotation_max_deg"],
            }
            for c in candidates
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if writes_active and args.output.exists():
        backup_dir = ROOT / "archive" / "solver_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{timestamp}_{args.output.name}"
        shutil.copy2(args.output, backup)
        print(f"Backed up previous active result: {backup}")
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    v = best["validation"]
    print(
        f"Samples: {len(samples)} used / {len(all_samples)} captured "
        f"(corners >= {args.min_charuco_corners})"
    )
    if excluded:
        print(f"Excluded samples: {excluded_reasons}")
    print(f"Best: Euler {best['euler_convention']}, method {best['method']}")
    print(f"Translation residual: median {v['translation_median_mm']:.2f} mm, max {v['translation_max_mm']:.2f} mm")
    print(f"Rotation residual: median {v['rotation_median_deg']:.2f} deg, max {v['rotation_max_deg']:.2f} deg")
    print("Camera->flange translation [m]:", best["camera_to_flange"]["translation_m"])
    print(f"Saved candidate: {args.output}")
    if not writes_active:
        print("Active handeye_result.json was not changed.")


if __name__ == "__main__":
    main()
