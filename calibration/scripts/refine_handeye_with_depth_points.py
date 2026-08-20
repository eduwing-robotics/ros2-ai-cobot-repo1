#!/usr/bin/env python3
"""Refine active camera->flange extrinsic from fixed-marker depth points."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def tf(rotation, translation):
    out = np.eye(4)
    out[:3, :3] = rotation
    out[:3, 3] = translation
    return out


def solve(samples, initial, convention):
    initial_r = Rotation.from_matrix(initial[:3, :3]).as_rotvec()
    initial_t = initial[:3, 3]
    base_flange, camera_points = [], []
    for sample in samples:
        robot = sample["robot"]
        base_flange.append(tf(
            Rotation.from_euler(convention, robot["flange_abc_deg"], degrees=True).as_matrix(),
            np.asarray(robot["flange_xyz_mm"], float) / 1000.0,
        ))
        camera_points.append(np.r_[sample["depth_camera_xyz_m"], 1.0])
    initial_points = np.asarray([(a @ initial @ p)[:3] for a, p in zip(base_flange, camera_points)])
    marker0 = np.median(initial_points, axis=0)
    x0 = np.r_[initial_r, initial_t, marker0]

    def residual(x):
        candidate = tf(Rotation.from_rotvec(x[:3]).as_matrix(), x[3:6])
        marker = x[6:9]
        return np.concatenate([(a @ candidate @ p)[:3] - marker for a, p in zip(base_flange, camera_points)])

    rot_bound = np.deg2rad(5.0)
    lower = np.r_[initial_r-rot_bound, initial_t-0.03, marker0-0.05]
    upper = np.r_[initial_r+rot_bound, initial_t+0.03, marker0+0.05]
    result = least_squares(residual, x0, bounds=(lower, upper), loss="soft_l1", f_scale=0.001)
    candidate = tf(Rotation.from_rotvec(result.x[:3]).as_matrix(), result.x[3:6])
    points = np.asarray([(a @ candidate @ p)[:3] for a, p in zip(base_flange, camera_points)])
    center = np.median(points, axis=0)
    errors = np.linalg.norm(points-center, axis=1)*1000.0
    return candidate, center, points, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--active-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    samples = json.loads(args.samples.read_text(encoding="utf-8"))["samples"]
    active_payload = json.loads(args.active_result.read_text(encoding="utf-8"))
    best = active_payload["best"]
    initial = tf(np.asarray(best["camera_to_flange"]["rotation_matrix"]), np.asarray(best["camera_to_flange"]["translation_m"]))
    candidate, center, points, errors = solve(samples, initial, best["euler_convention"])
    before_points=[]
    for s in samples:
        r=s["robot"]
        bf=tf(Rotation.from_euler(best["euler_convention"],r["flange_abc_deg"],degrees=True).as_matrix(),np.asarray(r["flange_xyz_mm"])/1000)
        before_points.append((bf@initial@np.r_[s["depth_camera_xyz_m"],1])[:3])
    before_points=np.asarray(before_points); before_center=np.median(before_points,axis=0)
    before_errors=np.linalg.norm(before_points-before_center,axis=1)*1000
    correction = np.linalg.inv(initial) @ candidate
    output = {
        "status":"candidate_not_active_depth_point_refinement",
        "created_at":datetime.now(timezone.utc).isoformat(),
        "source_samples":str(args.samples),
        "source_active_result":str(args.active_result),
        "sample_count":len(samples),
        "best":dict(best),
        "fixed_marker_base_median_m":center.tolist(),
        "before_error_mm":{"mean":float(before_errors.mean()),"max":float(before_errors.max()),"per_sample":before_errors.tolist()},
        "after_error_mm":{"mean":float(errors.mean()),"max":float(errors.max()),"per_sample":errors.tolist()},
        "correction":{"rotation_deg":Rotation.from_matrix(correction[:3,:3]).as_rotvec(degrees=True).tolist(),"translation_mm":(correction[:3,3]*1000).tolist()},
    }
    output["best"]["camera_to_flange"]={"rotation_matrix":candidate[:3,:3].tolist(),"translation_m":candidate[:3,3].tolist()}
    args.output.write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(f"Samples: {len(samples)}")
    print(f"Before mean/max [mm]: {before_errors.mean():.3f}/{before_errors.max():.3f}")
    print(f"After  mean/max [mm]: {errors.mean():.3f}/{errors.max():.3f}")
    print("Correction rotation rotvec [deg]:",np.round(Rotation.from_matrix(correction[:3,:3]).as_rotvec(degrees=True),4).tolist())
    print("Correction translation [mm]:",np.round(correction[:3,3]*1000,3).tolist())
    print("Candidate camera->flange translation [mm]:",np.round(candidate[:3,3]*1000,3).tolist())
    print("Saved candidate:",args.output)


if __name__ == "__main__":
    main()
