#!/usr/bin/env python3
"""Estimate the physical terminal-to-terminal axis of a small SMD.

The OBB model supplies only an ROI centre. These SMDs look nearly square at
1280x720, so an OBB may swap rectangle axes by 90 degrees between frames. The
coloured body and two low-chroma terminal bands provide a stable physical axis.
"""

from __future__ import annotations

import math

import cv2
import numpy as np


def canonical_axis_angle_deg(angle: float) -> float:
    """Normalize an unoriented line angle to ``[-90, 90)`` degrees."""
    return (float(angle) + 90.0) % 180.0 - 90.0


def unwrap_axis_angles_deg(values) -> np.ndarray:
    """Unwrap 180-degree-symmetric axes around their circular mean."""
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("SMD axis samples must be finite and non-empty")
    doubled = np.deg2rad(array * 2.0)
    cosine = float(np.mean(np.cos(doubled)))
    sine = float(np.mean(np.sin(doubled)))
    if math.hypot(cosine, sine) < 1e-6:
        raise ValueError("SMD axis samples have no unique 180-degree consensus")
    reference = math.degrees(0.5 * math.atan2(sine, cosine))
    return reference + (array - reference + 90.0) % 180.0 - 90.0


def terminal_axis_from_obb(
    points: np.ndarray,
    *,
    minimum_axis_ratio: float = 1.35,
) -> dict:
    """Extract the terminal-to-terminal long axis from four OBB corners."""
    polygon = np.asarray(points, dtype=np.float32)
    if polygon.shape != (4, 2) or not np.all(np.isfinite(polygon)):
        raise ValueError("SMD OBB must contain four finite 2D corners")
    center, (width, height), angle = cv2.minAreaRect(polygon)
    if width <= 0.0 or height <= 0.0:
        raise ValueError("SMD OBB has a degenerate side")
    if height > width:
        long_side, short_side = float(height), float(width)
        angle += 90.0
    else:
        long_side, short_side = float(width), float(height)
    axis_ratio = long_side / short_side
    if axis_ratio < float(minimum_axis_ratio):
        raise ValueError(
            f"SMD OBB is too square ({axis_ratio:.3f} < {minimum_axis_ratio:.3f})"
        )
    angle = canonical_axis_angle_deg(angle)
    theta = math.radians(angle)
    direction = np.asarray([math.cos(theta), math.sin(theta)], dtype=np.float32)
    center_array = np.asarray(center, dtype=np.float32)
    endpoints = np.asarray(
        [center_array - direction * long_side * 0.5,
         center_array + direction * long_side * 0.5],
        dtype=np.float32,
    )
    return {
        "angle_canonical_deg": float(angle),
        "endpoints_canonical_pixel": endpoints.tolist(),
        "axis_ratio": float(axis_ratio),
        "long_side_px": long_side,
        "short_side_px": short_side,
        "method": "trained_terminal_inclusive_obb",
    }


def terminal_axis_from_source_obb(points, inverse_homography, *, minimum_axis_ratio=1.35):
    """Undo display stretching before selecting/measuring the physical image axis.

    Returned canonical endpoints retain the downstream coordinate contract.
    Source-image pixel aspect is used; this is not a claim of metric 3D shape.
    """
    polygon=np.asarray(points,dtype=float)
    inverse=np.asarray(inverse_homography,dtype=float)
    if polygon.shape!=(4,2) or not np.isfinite(polygon).all():
        raise ValueError('SMD OBB must contain four finite 2D corners')
    if inverse.shape!=(3,3) or not np.isfinite(inverse).all():
        raise ValueError('invalid inverse section homography')
    try: forward=np.linalg.inv(inverse)
    except np.linalg.LinAlgError as error:raise ValueError('singular section homography') from error
    def project(vertices,matrix):
        homogeneous=np.c_[vertices,np.ones(len(vertices))]@matrix.T
        if np.any(np.abs(homogeneous[:,2])<1e-9):
            raise ValueError('section homography crosses infinity')
        result=homogeneous[:,:2]/homogeneous[:,2,None]
        if not np.isfinite(result).all():raise ValueError('non-finite projected axis')
        return result
    source=project(polygon,inverse)
    physical=terminal_axis_from_obb(source,minimum_axis_ratio=minimum_axis_ratio)
    source_ends=np.asarray(physical['endpoints_canonical_pixel'],float)
    canonical_ends=project(source_ends,forward)
    delta=canonical_ends[1]-canonical_ends[0]
    angle=canonical_axis_angle_deg(math.degrees(math.atan2(delta[1],delta[0])))
    return dict(physical, angle_canonical_deg=angle,
                endpoints_canonical_pixel=canonical_ends.tolist(),
                endpoints_source_pixel=source_ends.tolist(),
                angle_source_image_deg=physical['angle_canonical_deg'],
                axis_ratio_frame='source_image',
                method='trained_terminal_inclusive_obb_source_geometry_v1')


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order])
    if cumulative[-1] <= 0.0:
        raise ValueError("SMD colour-axis weights are empty")
    index = int(np.searchsorted(cumulative, float(quantile) * cumulative[-1]))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def terminal_axis_from_bgr(
    image: np.ndarray,
    center_xy: list[float] | np.ndarray,
    *,
    roi_radius_px: int = 55,
    body_saturation_floor: float = 30.0,
    minimum_axis_ratio: float = 1.15,
    maximum_center_offset_px: float = 18.0,
) -> dict:
    """Return an unoriented terminal axis in ``[-90, 90)`` image degrees."""
    frame = np.asarray(image)
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError("SMD terminal-axis input must be a uint8 BGR image")
    center = np.asarray(center_xy, dtype=float)
    if center.shape != (2,) or not np.all(np.isfinite(center)):
        raise ValueError("SMD terminal-axis centre must contain two finite values")
    radius = int(roi_radius_px)
    if radius < 30:
        raise ValueError("SMD terminal-axis ROI is too small")
    x, y = np.rint(center).astype(int)
    if (
        x - radius < 0
        or y - radius < 0
        or x + radius >= frame.shape[1]
        or y + radius >= frame.shape[0]
    ):
        raise ValueError("SMD terminal-axis ROI leaves the rectified image")

    roi = frame[y - radius : y + radius + 1, x - radius : x + radius + 1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).astype(float)
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    hue, saturation, value = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    body_gate = (
        (hue >= 3.0)
        & (hue <= 35.0)
        & (value > 65.0)
        & (value < 190.0)
        & (xx * xx + yy * yy < 48 * 48)
    )
    weights = np.maximum(saturation - float(body_saturation_floor), 0.0) * body_gate
    weight_sum = float(weights.sum())
    if weight_sum < 10000.0 or int(np.count_nonzero(weights)) < 350:
        raise ValueError("SMD coloured body has insufficient support")

    mean_x = float((weights * xx).sum() / weight_sum)
    mean_y = float((weights * yy).sum() / weight_sum)
    center_offset = math.hypot(mean_x, mean_y)
    if center_offset > float(maximum_center_offset_px):
        raise ValueError(f"SMD colour centre offset is too large ({center_offset:.2f}px)")
    dx, dy = xx - mean_x, yy - mean_y
    covariance = np.array(
        [
            [(weights * dx * dx).sum(), (weights * dx * dy).sum()],
            [(weights * dx * dy).sum(), (weights * dy * dy).sum()],
        ],
        dtype=float,
    ) / weight_sum
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues[0] <= 1e-6:
        raise ValueError("SMD colour-axis covariance is degenerate")
    axis_ratio = math.sqrt(float(eigenvalues[1] / eigenvalues[0]))
    if axis_ratio < float(minimum_axis_ratio):
        raise ValueError(f"SMD coloured body is too square ({axis_ratio:.3f})")
    axis = eigenvectors[:, 1]
    angle = (
        math.degrees(math.atan2(float(axis[1]), float(axis[0]))) + 90.0
    ) % 180.0 - 90.0

    along = dx * axis[0] + dy * axis[1]
    across = -dx * axis[1] + dy * axis[0]
    flat_weights = weights.ravel()
    low = _weighted_quantile(along.ravel(), flat_weights, 0.03)
    high = _weighted_quantile(along.ravel(), flat_weights, 0.97)
    body_half_length = min(abs(low), abs(high))
    if body_half_length < 14.0:
        raise ValueError("SMD coloured body is too short")

    core = (np.abs(along) < body_half_length * 0.45) & (np.abs(across) < 12.0)
    if int(np.count_nonzero(core)) < 100:
        raise ValueError("SMD body core is incomplete")
    core_saturation = float(np.median(saturation[core]))
    terminal_saturations = []
    terminal_pixel_counts = []
    for sign, edge in ((-1.0, low), (1.0, high)):
        start = edge + sign * 4.0
        stop = edge + sign * 17.0
        signed_along = along * sign
        band = (
            (signed_along >= min(start * sign, stop * sign))
            & (signed_along <= max(start * sign, stop * sign))
            & (np.abs(across) < 16.0)
        )
        count = int(np.count_nonzero(band))
        if count < 250:
            raise ValueError("SMD terminal band is incomplete")
        terminal_pixel_counts.append(count)
        terminal_saturations.append(float(np.median(saturation[band])))
    maximum_terminal_saturation = max(35.0, core_saturation * 0.60)
    if any(item > maximum_terminal_saturation for item in terminal_saturations):
        raise ValueError(
            "SMD two-sided white terminal check failed "
            f"(core={core_saturation:.1f}, terminals={terminal_saturations})"
        )

    return {
        "angle_canonical_deg": float(angle),
        "axis_ratio": float(axis_ratio),
        "colour_center_offset_px": float(center_offset),
        "body_core_saturation_median": core_saturation,
        "terminal_saturation_medians": terminal_saturations,
        "terminal_pixel_counts": terminal_pixel_counts,
        "method": "two_white_terminals_colour_weighted_axis",
    }
