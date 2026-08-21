#!/usr/bin/env python3
"""Validate Eye-in-Hand calibration with independently captured fixed-board poses."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES = ROOT / "data" / "validation_samples.json"
DEFAULT_RESULT = ROOT / "data" / "handeye_result.json"


def transform(rotation, translation):
    value = np.eye(4, dtype=float)
    value[:3, :3] = np.asarray(rotation, dtype=float).reshape(3, 3)
    value[:3, 3] = np.asarray(translation, dtype=float).reshape(3)
    return value


def main():
    parser = argparse.ArgumentParser(
        description="Report fixed ChArUco board Base-frame errors for each validation pose."
    )
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()

    payload = json.loads(args.samples.read_text(encoding="utf-8"))
    samples = payload.get("samples", [])
    if len(samples) < 3:
        raise SystemExit("At least 3 independent validation poses are required")

    best = json.loads(args.result.read_text(encoding="utf-8"))["best"]
    convention = best["euler_convention"]
    camera_to_flange = best["camera_to_flange"]
    t_flange_camera = transform(
        camera_to_flange["rotation_matrix"],
        camera_to_flange["translation_m"],
    )

    poses = []
    for sample in samples:
        robot = sample["robot"]
        t_base_flange = transform(
            Rotation.from_euler(
                convention, robot["flange_abc_deg"], degrees=True
            ).as_matrix(),
            np.asarray(robot["flange_xyz_mm"], dtype=float) / 1000.0,
        )
        target = sample["target_to_camera"]
        t_camera_board = transform(
            target["rotation_matrix"], target["translation_m"]
        )
        poses.append(t_base_flange @ t_flange_camera @ t_camera_board)

    xyz_mm = np.asarray([pose[:3, 3] for pose in poses]) * 1000.0
    reference_mm = np.median(xyz_mm, axis=0)
    delta_mm = xyz_mm - reference_mm
    euclidean_mm = np.linalg.norm(delta_mm, axis=1)

    print("HAND-EYE VALIDATION - NO ROBOT MOTION")
    print("Transform convention: T_base_board = T_base_flange @ T_flange_camera @ T_camera_board")
    print("Reference board origin in Base [mm]:", np.round(reference_mm, 3).tolist())
    print("\nSample errors relative to component-wise median [mm]")
    print(" index        dX        dY        dZ      norm")
    for sample, delta, norm in zip(samples, delta_mm, euclidean_mm):
        print(
            f" {int(sample['index']):5d} "
            f"{delta[0]:9.3f} {delta[1]:9.3f} {delta[2]:9.3f} {norm:9.3f}"
        )
    print("\nAxis absolute error mean [mm]:", np.round(np.mean(np.abs(delta_mm), axis=0), 3).tolist())
    print("Axis absolute error max  [mm]:", np.round(np.max(np.abs(delta_mm), axis=0), 3).tolist())
    print(f"Euclidean error mean/median/max [mm]: {np.mean(euclidean_mm):.3f}/{np.median(euclidean_mm):.3f}/{np.max(euclidean_mm):.3f}")


if __name__ == "__main__":
    main()
