#!/usr/bin/env python3
"""Solve the fixed S22 image-to-FR5 Base work-plane homography; no motion."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import numpy as np

from vision_server.s22_homography import (
    normalize_image_points,
    solve_normalized_image_to_base,
)


def normalized_point(entry):
    if 'image_normalized' in entry:
        return np.asarray(entry['image_normalized'], dtype=float)
    return normalize_image_points(
        [entry['image_px']], entry['image_size_px']
    )[0]


def main():
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--points-file', type=Path,
        default=project_root / 'vision_assembly/data/s22_plane_points.json',
    )
    parser.add_argument(
        '--output-file', type=Path,
        default=project_root / 'vision_assembly/data/s22_plane_calibration.json',
    )
    parser.add_argument('--ransac-threshold-mm', type=float, default=1.5)
    parser.add_argument('--max-rms-mm', type=float, default=2.0)
    parser.add_argument('--max-error-mm', type=float, default=5.0)
    parser.add_argument('--min-coverage-area', type=float, default=0.03)
    args = parser.parse_args()

    payload = json.loads(args.points_file.read_text(encoding='utf-8'))
    points = payload.get('points', [])
    if len(points) < 4:
        raise RuntimeError('At least four S22/Base point pairs are required')

    image_points = np.asarray([normalized_point(item) for item in points])
    base_xyz_mm = np.asarray([item['base_tcp_xyz_mm'] for item in points], dtype=float)
    solution = solve_normalized_image_to_base(
        image_points,
        base_xyz_mm[:, :2],
        ransac_threshold_mm=args.ransac_threshold_mm,
    )
    inverse = np.linalg.inv(solution.matrix)
    plane_z_mm = float(np.median(base_xyz_mm[solution.inliers, 2]))
    plane_z_std_mm = float(np.std(base_xyz_mm[solution.inliers, 2]))
    coverage_hull = cv2.convexHull(
        image_points[solution.inliers].astype(np.float32)
    ).reshape(-1, 2)
    coverage_area = float(cv2.contourArea(coverage_hull))
    passed = bool(
        solution.rms_mm <= args.max_rms_mm
        and solution.max_mm <= args.max_error_mm
        and plane_z_std_mm <= args.max_rms_mm
        and coverage_area >= args.min_coverage_area
    )

    result = {
        'schema_version': 1,
        'calibration_type': 'normalized_s22_image_to_fr5_base_plane',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'robot_motion_sent': False,
        'image_topic': payload.get(
            'image_topic', '/camera2/image_raw/compressed'
        ),
        'coordinate_units': {
            'image': 'normalized_0_to_1',
            'base_xy': 'mm',
            'plane_z': 'mm',
        },
        'homography_normalized_image_to_base_mm': solution.matrix.tolist(),
        'homography_base_mm_to_normalized_image': inverse.tolist(),
        'plane_z_mm': plane_z_mm,
        'coverage_hull_normalized': coverage_hull.tolist(),
        'quality': {
            'passed': passed,
            'point_count': len(points),
            'inlier_count': int(np.count_nonzero(solution.inliers)),
            'rms_mm': solution.rms_mm,
            'max_error_mm': solution.max_mm,
            'plane_z_std_mm': plane_z_std_mm,
            'coverage_area_normalized': coverage_area,
            'limits': {
                'max_rms_mm': args.max_rms_mm,
                'max_error_mm': args.max_error_mm,
                'min_coverage_area': args.min_coverage_area,
            },
        },
        'points': [
            {
                'label': item.get('label', f'point_{index + 1}'),
                'image_normalized': image_points[index].tolist(),
                'base_tcp_xyz_mm': base_xyz_mm[index].tolist(),
                'inlier': bool(solution.inliers[index]),
                'error_mm': float(solution.residuals_mm[index]),
            }
            for index, item in enumerate(points)
        ],
    }
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )

    print('S22 PLANAR CALIBRATION - ROBOT DID NOT MOVE')
    print(f'Points/inliers: {len(points)}/{np.count_nonzero(solution.inliers)}')
    print(f'XY residual RMS/max [mm]: {solution.rms_mm:.3f}/{solution.max_mm:.3f}')
    print(f'Plane Z median/std [mm]: {plane_z_mm:.3f}/{plane_z_std_mm:.3f}')
    print(f'Normalized image coverage area: {coverage_area:.4f}')
    print('Quality:', 'PASS' if passed else 'FAIL - do not use for robot motion')
    print('Saved:', args.output_file)


if __name__ == '__main__':
    main()
