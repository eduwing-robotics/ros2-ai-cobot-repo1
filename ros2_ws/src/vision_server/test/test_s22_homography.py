import math

import cv2
import numpy as np
import pytest

from vision_server.s22_homography import (
    normalize_image_points,
    polygon_base_pose,
    solve_normalized_image_to_base,
    transform_planar_points,
)


def test_pixel_normalization_is_resolution_independent():
    points = normalize_image_points([[0, 0], [1919, 1079]], [1920, 1080])
    assert np.allclose(points, [[0.0, 0.0], [1.0, 1.0]])


def test_homography_recovers_known_planar_mapping():
    matrix = np.asarray(
        [[620.0, 25.0, -410.0], [12.0, -430.0, 180.0], [0.08, -0.04, 1.0]],
        dtype=np.float64,
    )
    image = np.asarray(
        [
            [0.15, 0.20], [0.80, 0.18], [0.84, 0.78], [0.12, 0.82],
            [0.48, 0.33], [0.62, 0.60],
        ],
        dtype=np.float64,
    )
    base = transform_planar_points(image, matrix)
    solution = solve_normalized_image_to_base(image, base)

    assert solution.inliers.all()
    assert solution.rms_mm < 1e-4
    assert transform_planar_points([[0.4, 0.5]], solution.matrix) == pytest.approx(
        transform_planar_points([[0.4, 0.5]], matrix), abs=1e-5
    )


def test_polygon_pose_reports_center_size_and_yaw_modulo_180():
    center = np.asarray([-315.0, -25.0])
    yaw = math.radians(30.0)
    rotation = np.asarray(
        [[math.cos(yaw), -math.sin(yaw)], [math.sin(yaw), math.cos(yaw)]]
    )
    local = np.asarray(
        [[-69.5, -55.0], [69.5, -55.0], [69.5, 55.0], [-69.5, 55.0]]
    )
    base_polygon = local @ rotation.T + center
    base_to_image = cv2.getPerspectiveTransform(
        np.float32([[-500, -300], [0, -300], [0, 300], [-500, 300]]),
        np.float32([[0.1, 0.1], [0.9, 0.15], [0.85, 0.9], [0.08, 0.85]]),
    )
    image_polygon = transform_planar_points(base_polygon, base_to_image)
    image_to_base = np.linalg.inv(base_to_image)

    _, measured_center, measured_yaw, long_mm, short_mm = polygon_base_pose(
        image_polygon, image_to_base
    )

    assert measured_center == pytest.approx(center, abs=1e-3)
    assert math.degrees(measured_yaw) == pytest.approx(30.0, abs=1e-3)
    assert long_mm == pytest.approx(139.0, abs=1e-3)
    assert short_mm == pytest.approx(110.0, abs=1e-3)
