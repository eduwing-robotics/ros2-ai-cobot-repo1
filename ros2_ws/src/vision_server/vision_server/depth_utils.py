"""Small, ROS-independent helpers for aligned RGB-D observations."""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class CameraPoint:
    x_m: float
    y_m: float
    z_m: float


def robust_box_depth(
    depth: np.ndarray,
    box_xywh: Sequence[int],
    *,
    scale_m_per_unit: float,
    roi_fraction: float = 0.35,
    min_depth_m: float = 0.02,
    max_depth_m: float = 2.0,
) -> Optional[Tuple[float, float, float]]:
    """Return ``(u, v, median_depth_m)`` from the center of a detection box.

    The depth image must already be aligned to the color image. Invalid zeros,
    NaNs and values outside the configured working range are discarded.
    """
    array = np.asarray(depth)
    if array.ndim != 2 or array.size == 0:
        return None
    x, y, width, height = [int(value) for value in box_xywh]
    if width <= 0 or height <= 0 or scale_m_per_unit <= 0.0:
        return None
    fraction = float(np.clip(roi_fraction, 0.05, 1.0))
    center_u = float(x) + float(width) / 2.0
    center_v = float(y) + float(height) / 2.0
    roi_width = max(1, int(round(width * fraction)))
    roi_height = max(1, int(round(height * fraction)))
    left = max(0, int(round(center_u - roi_width / 2.0)))
    right = min(array.shape[1], left + roi_width)
    top = max(0, int(round(center_v - roi_height / 2.0)))
    bottom = min(array.shape[0], top + roi_height)
    if left >= right or top >= bottom:
        return None

    values_m = array[top:bottom, left:right].astype(np.float64) * float(
        scale_m_per_unit
    )
    valid = values_m[
        np.isfinite(values_m)
        & (values_m >= float(min_depth_m))
        & (values_m <= float(max_depth_m))
    ]
    if valid.size == 0:
        return None
    return center_u, center_v, float(np.median(valid))


def deproject_pixel(
    u: float,
    v: float,
    depth_m: float,
    camera_matrix: np.ndarray,
) -> Optional[CameraPoint]:
    """Deproject one aligned color pixel using the pinhole camera model."""
    matrix = np.asarray(camera_matrix, dtype=float).reshape(3, 3)
    fx, fy = float(matrix[0, 0]), float(matrix[1, 1])
    cx, cy = float(matrix[0, 2]), float(matrix[1, 2])
    if (
        not np.all(np.isfinite([u, v, depth_m, fx, fy, cx, cy]))
        or depth_m <= 0.0
        or fx <= 0.0
        or fy <= 0.0
    ):
        return None
    return CameraPoint(
        x_m=(float(u) - cx) * float(depth_m) / fx,
        y_m=(float(v) - cy) * float(depth_m) / fy,
        z_m=float(depth_m),
    )
