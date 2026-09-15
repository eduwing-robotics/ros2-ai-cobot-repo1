#!/usr/bin/env python3
"""Build a non-active 1920x1080 Hand-Eye candidate."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from charuco_common import detect_charuco, detector_parameters, load_config
from solve_handeye import METHODS, solve


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRAIN = DATA / "handeye_refinement_samples.json"
VALIDATION = DATA / "validation_1080_samples.json"
INTRINSIC_OUTPUT = DATA / "camera_intrinsics_1920x1080_candidate.json"
HANDEYE_OUTPUT = DATA / "handeye_result_1080_candidate.json"


def detections(payload, dictionary, board, parameters):
    values = []
    image_size = None
    for sample in payload["samples"]:
        image = cv2.imread(str(DATA / sample["image"]))
        if image is None:
            raise RuntimeError(f"Cannot read {sample['image']}")
        current_size = (image.shape[1], image.shape[0])
        if image_size is not None and image_size != current_size:
            raise RuntimeError("Mixed image resolutions are not allowed")
        image_size = current_size
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, _, corners, ids, _ = detect_charuco(
            gray, dictionary, board, parameters
        )
        if ids is None or len(ids) < 12:
            raise RuntimeError(f"Only {0 if ids is None else len(ids)} corners in {sample['image']}")
        values.append((sample, image, corners, ids))
    return values, image_size


def rebuild(values, board, camera_matrix, distortion):
    samples = []
    reprojection = []
    for sample, image, _, _ in values:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, _, corners, ids, _ = detect_charuco(
            gray, *load_config()[1:3], detector_parameters(),
            camera_matrix, distortion,
        )
        valid, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            corners, ids, board, camera_matrix, distortion, None, None
        )
        if not valid:
            raise RuntimeError(f"Pose failed for {sample['image']}")
        object_points = board.chessboardCorners[ids.flatten()]
        projected, _ = cv2.projectPoints(
            object_points, rvec, tvec, camera_matrix, distortion
        )
        reprojection.append(float(np.median(np.linalg.norm(
            projected.reshape(-1, 2) - corners.reshape(-1, 2), axis=1
        ))))
        rotation, _ = cv2.Rodrigues(rvec)
        rebuilt = dict(sample)
        rebuilt["target_to_camera"] = {
            "rotation_matrix": rotation.tolist(),
            "translation_m": np.asarray(tvec).reshape(3).tolist(),
        }
        samples.append(rebuilt)
    return samples, reprojection


def dispersion(best, samples):
    from scipy.spatial.transform import Rotation

    def transform(rotation, translation):
        value = np.eye(4)
        value[:3, :3] = rotation
        value[:3, 3] = np.asarray(translation).reshape(3)
        return value

    camera_to_flange = best["camera_to_flange"]
    flange_camera = transform(
        np.asarray(camera_to_flange["rotation_matrix"]),
        camera_to_flange["translation_m"],
    )
    points = []
    for sample in samples:
        robot = sample["robot"]
        base_flange = transform(
            Rotation.from_euler(
                best["euler_convention"], robot["flange_abc_deg"], degrees=True
            ).as_matrix(),
            np.asarray(robot["flange_xyz_mm"]) / 1000.0,
        )
        target = sample["target_to_camera"]
        camera_board = transform(
            np.asarray(target["rotation_matrix"]), target["translation_m"]
        )
        points.append((base_flange @ flange_camera @ camera_board)[:3, 3] * 1000.0)
    points = np.asarray(points)
    reference = np.median(points, axis=0)
    errors = np.linalg.norm(points - reference, axis=1)
    return {
        "mean_mm": float(np.mean(errors)),
        "median_mm": float(np.median(errors)),
        "max_mm": float(np.max(errors)),
        "axis_range_mm": np.ptp(points, axis=0).tolist(),
        "errors_mm": errors.tolist(),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-file", type=Path, default=TRAIN)
    parser.add_argument("--validation-file", type=Path, default=VALIDATION)
    parser.add_argument("--intrinsics-file", type=Path, default=None)
    parser.add_argument("--intrinsics-output", type=Path, default=INTRINSIC_OUTPUT)
    parser.add_argument("--handeye-output", type=Path, default=HANDEYE_OUTPUT)
    parser.add_argument("--method", choices=sorted(METHODS), default="DANIILIDIS")
    return parser.parse_args()


def main():
    args = parse_args()
    train_payload = json.loads(args.train_file.read_text(encoding="utf-8"))
    validation_payload = json.loads(args.validation_file.read_text(encoding="utf-8"))
    config, dictionary, board = load_config()
    parameters = detector_parameters()
    train_values, size = detections(train_payload, dictionary, board, parameters)
    validation_values, validation_size = detections(
        validation_payload, dictionary, board, parameters
    )
    if size != (1920, 1080) or validation_size != size:
        raise SystemExit(f"Expected only 1920x1080 images, got {size}/{validation_size}")

    if args.intrinsics_file is None:
        rms, camera_matrix, distortion, _, _, _, _, per_view = (
            cv2.aruco.calibrateCameraCharucoExtended(
                [value[2] for value in train_values],
                [value[3] for value in train_values],
                board, size, None, None,
            )
        )
        intrinsic_output = {
            "status": "candidate_not_active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_samples": str(args.train_file),
            "image_width": size[0],
            "image_height": size[1],
            "camera_matrix": camera_matrix.tolist(),
            "distortion_model": "plumb_bob",
            "distortion_coefficients": distortion.reshape(-1).tolist(),
            "calibration_rms_px": float(rms),
            "per_view_error_median_px": float(np.median(per_view)),
            "per_view_error_max_px": float(np.max(per_view)),
        }
        args.intrinsics_output.write_text(
            json.dumps(intrinsic_output, indent=2), encoding="utf-8"
        )
        intrinsic_file = args.intrinsics_output
    else:
        intrinsic_output = json.loads(args.intrinsics_file.read_text(encoding="utf-8"))
        if (intrinsic_output["image_width"], intrinsic_output["image_height"]) != size:
            raise SystemExit("Intrinsic file resolution does not match 1920x1080 samples")
        camera_matrix = np.asarray(intrinsic_output["camera_matrix"], dtype=float)
        distortion = np.asarray(
            intrinsic_output["distortion_coefficients"], dtype=float
        ).reshape(-1, 1)
        intrinsic_file = args.intrinsics_file
    train_samples, train_reprojection = rebuild(
        train_values, board, camera_matrix, distortion
    )
    validation_samples, validation_reprojection = rebuild(
        validation_values, board, camera_matrix, distortion
    )

    # FR5 ABC samples in this project are interpreted with fixed-axis xyz.
    best = solve(
        train_samples, "xyz", args.method, METHODS[args.method]
    )
    independent = dispersion(best, validation_samples)
    created = datetime.now(timezone.utc).isoformat()
    handeye_output = {
        "status": "candidate_not_active_no_robot_motion_until_approved",
        "created_at": created,
        "source_samples": str(args.train_file),
        "intrinsic_file": str(intrinsic_file),
        "sample_count": len(train_samples),
        "best": best,
        "independent_validation_1080": {
            "file": str(args.validation_file),
            "sample_count": len(validation_samples),
            "reprojection_median_px": float(np.median(validation_reprojection)),
            "reprojection_max_px": float(np.max(validation_reprojection)),
            **independent,
        },
    }
    args.handeye_output.write_text(
        json.dumps(handeye_output, indent=2), encoding="utf-8"
    )
    print(f"Intrinsic candidate: {intrinsic_file}")
    print(f"Hand-Eye candidate: {args.handeye_output}")
    print("Camera->flange [mm]:", np.round(
        np.asarray(best["camera_to_flange"]["translation_m"]) * 1000.0, 3
    ).tolist())
    print(
        "Independent validation mean/median/max [mm]: "
        f"{independent['mean_mm']:.3f}/"
        f"{independent['median_mm']:.3f}/"
        f"{independent['max_mm']:.3f}"
    )


if __name__ == "__main__":
    main()
