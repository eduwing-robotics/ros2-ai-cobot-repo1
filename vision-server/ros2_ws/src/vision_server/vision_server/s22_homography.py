"""Planar S22 image-to-robot coordinate conversion helpers."""

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class HomographySolution:
    matrix: np.ndarray
    inliers: np.ndarray
    residuals_mm: np.ndarray

    @property
    def rms_mm(self) -> float:
        values = self.residuals_mm[self.inliers]
        return float(np.sqrt(np.mean(np.square(values))))

    @property
    def max_mm(self) -> float:
        return float(np.max(self.residuals_mm[self.inliers]))


def normalize_image_points(image_points_px, image_size_px) -> np.ndarray:
    """Convert pixel coordinates to resolution-independent 0..1 coordinates."""
    points = np.asarray(image_points_px, dtype=np.float64).reshape(-1, 2)
    width, height = (int(value) for value in image_size_px)
    if width < 2 or height < 2:
        raise ValueError('image width and height must both be at least 2')
    scale = np.asarray([width - 1.0, height - 1.0], dtype=np.float64)
    return points / scale


def transform_planar_points(points_xy, matrix) -> np.ndarray:
    """Apply a 3x3 homography to an Nx2 point array."""
    points = np.asarray(points_xy, dtype=np.float64).reshape(-1, 1, 2)
    transform_matrix = np.asarray(matrix, dtype=np.float64).reshape(3, 3)
    if not np.all(np.isfinite(points)) or not np.all(np.isfinite(transform_matrix)):
        raise ValueError('homography inputs must be finite')
    transformed = cv2.perspectiveTransform(points, transform_matrix)
    return transformed.reshape(-1, 2)


def solve_normalized_image_to_base(
    image_points_normalized,
    base_points_mm,
    *,
    ransac_threshold_mm: float = 1.5,
) -> HomographySolution:
    """Estimate normalized-image -> robot-base XY millimetre homography."""
    image_points = np.asarray(
        image_points_normalized, dtype=np.float64
    ).reshape(-1, 2)
    base_points = np.asarray(base_points_mm, dtype=np.float64).reshape(-1, 2)
    if image_points.shape != base_points.shape:
        raise ValueError('image and base point arrays must have the same shape')
    if len(image_points) < 4:
        raise ValueError('at least four point pairs are required')
    if not np.all(np.isfinite(image_points)) or not np.all(np.isfinite(base_points)):
        raise ValueError('calibration points must be finite')
    if np.any(image_points < -0.01) or np.any(image_points > 1.01):
        raise ValueError('normalized image points must be within 0..1')

    matrix, mask = cv2.findHomography(
        image_points,
        base_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=float(ransac_threshold_mm),
    )
    if matrix is None or mask is None:
        raise RuntimeError('homography estimation failed')
    inliers = mask.reshape(-1).astype(bool)
    if int(np.count_nonzero(inliers)) < 4:
        raise RuntimeError('homography has fewer than four inliers')
    predicted = transform_planar_points(image_points, matrix)
    residuals = np.linalg.norm(predicted - base_points, axis=1)
    return HomographySolution(matrix, inliers, residuals)


def polygon_base_pose(polygon_normalized, image_to_base_mm):
    """Return center, long-axis yaw modulo 180 degrees, and side lengths."""
    polygon = np.asarray(polygon_normalized, dtype=np.float64).reshape(-1, 2)
    if len(polygon) != 4:
        raise ValueError('board polygon must contain exactly four points')
    base_polygon = transform_planar_points(polygon, image_to_base_mm)
    center = np.mean(base_polygon, axis=0)
    edges = np.roll(base_polygon, -1, axis=0) - base_polygon
    lengths = np.linalg.norm(edges, axis=1)
    if float(np.min(lengths)) <= 1e-6:
        raise ValueError('board polygon is degenerate')
    long_index = int(np.argmax(lengths))
    long_vector = edges[long_index]
    yaw = math.atan2(float(long_vector[1]), float(long_vector[0]))
    while yaw >= math.pi * 0.5:
        yaw -= math.pi
    while yaw < -math.pi * 0.5:
        yaw += math.pi
    ordered_lengths = np.sort(lengths)
    short_mm = float(np.mean(ordered_lengths[:2]))
    long_mm = float(np.mean(ordered_lengths[2:]))
    return base_polygon, center, yaw, long_mm, short_mm
