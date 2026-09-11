#!/usr/bin/env python3
"""Local OpenCV evidence for fixed PCB slots.

Only these local, explainable checks use grayscale CLAHE.  Their authority is
set by the caller after controlled validation; raw measurements are retained
even while the verdict remains advisory.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import cv2
import numpy as np


@dataclass
class CheckEvidence:
    name: str
    status: str
    authority: str
    confidence: float
    reason: str
    measured: dict[str, Any]
    limits: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clahe_gray(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def _angle_difference(a: float, b: float, period: float) -> float:
    return abs((a - b + period * 0.5) % period - period * 0.5)


def _white_components(image_bgr: np.ndarray) -> tuple[np.ndarray, list[dict[str, float]]]:
    gray = clahe_gray(image_bgr)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    light_floor = max(150, int(np.percentile(gray, 72)))
    mask = ((gray >= light_floor) & (hsv[..., 1] <= 115)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(image_bgr.shape[0] * image_bgr.shape[1])
    components = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not image_area * 0.00025 <= area <= image_area * 0.08:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        moments = cv2.moments(contour)
        if abs(float(moments["m00"])) < 1e-6:
            continue
        components.append(
            {
                "x": float(moments["m10"] / moments["m00"]),
                "y": float(moments["m01"] / moments["m00"]),
                "area": area,
                "circularity": float(
                    4.0 * math.pi * area / max(perimeter * perimeter, 1e-6)
                ),
            }
        )
    return mask, components


def check_gpu_hbm_dot(
    crop_bgr: np.ndarray,
    expected_corner: str = "lower_left",
    winner_margin_min: float = 0.04,
    authority: str = "ADVISORY_ONLY",
    suppress_pin_columns: bool = False,
    slot_inset_fraction: float = 0.0,
) -> CheckEvidence:
    """Determine 0/180 orientation from the package's white corner dot.

    White side pins are retained as evidence but a corner score favours the
    larger, rounder dot component instead of treating every white pixel alike.
    """
    _, components = _white_components(crop_bgr)
    height, width = crop_bgr.shape[:2]
    corner_centres = {
        "upper_left": (0.18 * width, 0.18 * height),
        "upper_right": (0.82 * width, 0.18 * height),
        "lower_left": (0.18 * width, 0.82 * height),
        "lower_right": (0.82 * width, 0.82 * height),
    }
    image_area = float(width * height)
    diagonal = max(1.0, math.hypot(width, height))
    scores = {name: 0.0 for name in corner_centres}
    selected = {name: None for name in corner_centres}
    for component in components:
        area_ratio = component["area"] / image_area
        # The package dot is a compact circular island.  Pin rows can be bright
        # and circular too, but their individual blobs are consistently
        # smaller; logos are larger and remain outside the corner quadrants.
        if not 0.00035 <= area_ratio <= 0.020 or component["circularity"] < 0.55:
            continue
        # Fixed crop padding contains neighbouring parts, not package dots.
        # Do not move/rotate the crop to excuse slot-relative pose errors.
        if not (slot_inset_fraction * width <= component['x'] <= (1-slot_inset_fraction)*width
                and slot_inset_fraction * height <= component['y'] <= (1-slot_inset_fraction)*height):
            continue
        if suppress_pin_columns:
            # Count comparable blobs, not every object sharing an x coordinate.
            # Otherwise the larger printed dot is removed with small pins,
            # while a damaged column of only three remaining pins survives.
            # The rule is symmetric: never prefer the expected corner.
            vertical_peers = sum(
                abs(other["x"] - component["x"]) <= 0.06 * width
                and 0.5 * component["area"] <= other["area"] <= 2.0 * component["area"]
                for other in components
            )
            in_edge_column = (
                component["x"] <= 0.25 * width
                or component["x"] >= 0.75 * width
            )
            if in_edge_column and vertical_peers >= 3:
                continue
        for name, centre in corner_centres.items():
            is_left = name.endswith("left")
            is_upper = name.startswith("upper")
            if is_left and not 0.05 * width <= component["x"] <= 0.42 * width:
                continue
            if not is_left and not 0.58 * width <= component["x"] <= 0.95 * width:
                continue
            if is_upper and not 0.05 * height <= component["y"] <= 0.38 * height:
                continue
            if not is_upper and not 0.62 * height <= component["y"] <= 0.95 * height:
                continue
            distance = math.hypot(component["x"] - centre[0], component["y"] - centre[1])
            proximity = max(0.0, 1.0 - distance / (0.30 * diagonal))
            # Do not cap size at one: the printed corner dot is deliberately
            # larger than an individual side pin.  Capping made a nearby end
            # pin beat the true dot on otherwise normal HBM crops.
            size = area_ratio / 0.0045
            roundness = float(np.clip(component["circularity"], 0.0, 1.0))
            score = proximity * size * roundness
            if score > scores[name]:
                scores[name] = score
                selected[name] = {
                    "center_px": [component["x"], component["y"]],
                    "area_px": component["area"],
                    "area_ratio": area_ratio,
                    "circularity": component["circularity"],
                }

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, winner_score = ranked[0]
    runner_score = ranked[1][1]
    margin = winner_score - runner_score
    area_scores = {name: value["area_px"] for name, value in selected.items()
                   if value is not None}
    largest_area = max(area_scores.values(), default=0.0)
    area_winners = [name for name, area in area_scores.items() if area == largest_area]
    # Disagreement is ambiguity, not permission to pick the expected corner.
    # Apply symmetrically to both potential PASS and FAIL outcomes.
    ranking_conflict = suppress_pin_columns and bool(area_winners) and area_winners != [winner]
    # A large end pin can win size/proximity while a different corner has
    # the stronger round-dot shape. Keep that disagreement as uncertainty;
    # never choose the expected corner to resolve it.
    shape_scores = {name: value["area_px"] * value["circularity"]
                    for name, value in selected.items() if value is not None}
    strongest_shape = max(shape_scores.values(), default=0.0)
    shape_winners = [name for name, score in shape_scores.items()
                     if score == strongest_shape]
    shape_conflict = (suppress_pin_columns and bool(shape_winners)
                      and shape_winners != [winner])
    if winner_score < 0.05 or margin < winner_margin_min:
        status = "UNKNOWN"
        reason = "WHITE_DOT_NOT_UNAMBIGUOUS"
    elif ranking_conflict:
        status = "UNKNOWN"
        reason = "WHITE_DOT_SIZE_POSITION_CONFLICT"
    elif shape_conflict:
        status = "UNKNOWN"
        reason = "WHITE_DOT_SHAPE_POSITION_CONFLICT"
    elif winner == expected_corner:
        status = "PASS"
        reason = "WHITE_DOT_AT_EXPECTED_CORNER"
    else:
        status = "FAIL"
        reason = f"WHITE_DOT_AT_{winner.upper()}"

    side_pin_counts = {
        "left": sum(component["x"] < width * 0.30 for component in components),
        "right": sum(component["x"] > width * 0.70 for component in components),
    }
    confidence = float(np.clip(winner_score * 0.7 + max(0.0, margin) * 0.6, 0.0, 1.0))
    return CheckEvidence(
        "gpu_hbm_white_dot",
        status,
        authority,
        confidence,
        reason,
        {
            "corner_scores": scores,
            "winner": winner,
            "winner_margin": margin,
            "selected_corner_components": selected,
            "area_winning_corners": area_winners,
            "size_position_conflict": ranking_conflict,
            "shape_winning_corners": shape_winners,
            "shape_position_conflict": shape_conflict,
            "recapture_recommended": status == "UNKNOWN",
            "white_component_count": len(components),
            "side_pin_component_counts": side_pin_counts,
        },
        {
            "expected_corner": expected_corner,
            "winner_margin_min": winner_margin_min,
            "suppress_pin_columns": suppress_pin_columns,
            "slot_inset_fraction": slot_inset_fraction,
            "pin_column_min_comparable_blobs": 3,
            "pin_column_area_ratio_range": [0.5, 2.0],
        },
    )


def check_inductor_marker(
    crop_bgr: np.ndarray,
    expected_angle_deg: float = 180.0,
    tolerance_deg: float = 50.0,
    minimum_contrast: float = 7.0,
    authority: str = "ADVISORY_ONLY",
    axis_tolerance_deg: float = 10.0,
    expected_inner_edge_deg: float | None = None,
) -> CheckEvidence:
    """Locate the black asymmetric mark inside the white inductor top."""
    raw_gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    gray = clahe_gray(crop_bgr)
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    bright_floor = max(135, int(np.percentile(gray, 67)))
    # CLAHE can brighten the dark plastic base into the white-top candidate.
    # Require raw brightness too; otherwise the inflated circle samples the
    # base/rim and its texture is incorrectly measured as a rotated marker.
    bright = ((gray >= bright_floor) & (raw_gray >= 135) &
              (hsv[..., 1] <= 125)).astype(np.uint8) * 255
    bright = cv2.morphologyEx(
        bright, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2
    )
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return CheckEvidence(
            "inductor_black_marker", "UNKNOWN", authority, 0.0,
            "WHITE_TOP_NOT_FOUND", {}, {"expected_angle_deg": expected_angle_deg},
        )
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    if area < crop_bgr.shape[0] * crop_bgr.shape[1] * 0.04:
        return CheckEvidence(
            "inductor_black_marker", "UNKNOWN", authority, 0.0,
            "WHITE_TOP_TOO_SMALL", {"white_top_area_px": area},
            {"expected_angle_deg": expected_angle_deg},
        )
    (center_x, center_y), radius = cv2.minEnclosingCircle(contour)
    yy, xx = np.ogrid[:gray.shape[0], :gray.shape[1]]
    inner = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= (radius * 0.78) ** 2
    values = gray[inner]
    raw_values = raw_gray[inner]
    if values.size < 20:
        return CheckEvidence(
            "inductor_black_marker", "UNKNOWN", authority, 0.0,
            "INDUCTOR_INTERIOR_TOO_SMALL", {}, {"expected_angle_deg": expected_angle_deg},
        )
    median = float(np.median(values))
    raw_median = float(np.median(raw_values))
    dark_limit = median - minimum_contrast
    # CLAHE is the primary local feature, while raw grayscale prevents a
    # nearly uniform bright top from saturating an entire tile and erasing a
    # physically strong black marker contrast.
    raw_dark_limit = raw_median - max(12.0, minimum_contrast * 2.0)
    dark = inner & ((gray <= dark_limit) | (raw_gray <= raw_dark_limit))
    dark_y, dark_x = np.nonzero(dark)
    if len(dark_x) < max(8, int(values.size * 0.015)):
        return CheckEvidence(
            "inductor_black_marker", "UNKNOWN", authority, 0.0,
            "BLACK_MARKER_NOT_FOUND",
            {
                "clahe_local_contrast": median - float(values.min()),
                "raw_local_contrast": raw_median - float(raw_values.min()),
            },
            {"minimum_contrast": minimum_contrast},
        )
    marker_x = float(np.mean(dark_x))
    marker_y = float(np.mean(dark_y))
    dx, dy = marker_x - center_x, marker_y - center_y
    radial = math.hypot(dx, dy) / max(radius, 1e-6)
    angle = math.degrees(math.atan2(dy, dx)) % 360.0
    difference = _angle_difference(angle, expected_angle_deg, 360.0)
    if radial < 0.10:
        status, reason = "UNKNOWN", "BLACK_MARKER_DIRECTION_AMBIGUOUS"
    elif difference <= tolerance_deg:
        status, reason = "PASS", "BLACK_MARKER_DIRECTION_OK"
    else:
        status, reason = "FAIL", "BLACK_MARKER_DIRECTION_WRONG"
    from inductor_marker_geometry import measure_dark_mark
    strict = measure_dark_mark(crop_bgr, [center_x, center_y], radius)
    strict_valid = strict is not None and strict['elongation'] >= 3.0
    edge_error = None
    if strict_valid and expected_inner_edge_deg is not None and strict.get('diagnostic_inner_edge_axis_deg') is not None:
        edge_error = _angle_difference(strict['diagnostic_inner_edge_axis_deg'], expected_inner_edge_deg, 180.0)
    if strict_valid and strict['axis_error_deg'] > axis_tolerance_deg:
        status, reason = "FAIL", "BLACK_MARKER_AXIS_ROTATION_WRONG"
    elif edge_error is not None and edge_error > axis_tolerance_deg:
        status, reason = "FAIL", "BLACK_MARKER_INNER_EDGE_ROTATION_WRONG"
    elif status == "PASS" and not strict_valid:
        status, reason = "UNKNOWN", "BLACK_MARKER_FINE_AXIS_UNCERTAIN"
    confidence = float(np.clip(radial * (1.0 - min(difference, 180.0) / 360.0), 0.0, 1.0))
    return CheckEvidence(
        "inductor_black_marker",
        status,
        authority,
        confidence,
        reason,
        {
            "marker_angle_deg": angle,
            "strict_marker": strict,
            "inner_edge_error_deg": edge_error,
            "angle_error_deg": difference,
            "radial_ratio": radial,
            "circle_center_px": [center_x, center_y],
            "marker_center_px": [marker_x, marker_y],
            "white_top_radius_px": radius,
        },
        {
            "expected_angle_deg": expected_angle_deg,
            "tolerance_deg": tolerance_deg,
            "axis_tolerance_deg": axis_tolerance_deg,
            "axis_minimum_elongation": 3.0,
            "expected_inner_edge_deg": expected_inner_edge_deg,
            "minimum_contrast": minimum_contrast,
        },
    )


def _finite_pair(value: Any) -> np.ndarray:
    pair = np.asarray(value, np.float64)
    if pair.shape != (2,) or not np.isfinite(pair).all():
        raise ValueError("Expected a finite coordinate pair")
    return pair


def _pose_centers(item: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float]:
    evidence = item["evidence"]
    confidence = float(item.get("confidence", 0.0))
    if not np.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("Invalid auxiliary confidence")
    return _finite_pair(evidence["center_px"]), _finite_pair(evidence["expected_center_px"]), confidence


def check_auxiliary_pose(
    yolo_item: dict[str, Any] | None,
    expected_axis_deg: float,
    image_shape: tuple[int, ...],
    board_size_mm: tuple[float, float],
    position_tolerance_mm: float = 0.75,
    angle_tolerance_deg: float = 3.0,
    common_bias_mm: tuple[float, float] = (0.0, 0.0),
    slot_reference_offset_mm: tuple[float, float] = (0.0, 0.0),
    slot_reference_calibration_id: str | None = None,
    check_axis_angle: bool = True,
) -> CheckEvidence:
    """Measure slot-relative pose from an advisory segmentation polygon."""
    if yolo_item is None:
        return CheckEvidence(
            "auxiliary_pose", "UNKNOWN", "ADVISORY_ONLY", 0.0,
            "YOLO_AUXILIARY_CANDIDATE_MISSING", {}, {},
        )
    try:
        evidence = yolo_item.get("evidence", {})
        if not evidence.get("present", False):
            return CheckEvidence(
                "auxiliary_pose", "UNKNOWN", "ADVISORY_ONLY", 0.0,
                "YOLO_AUXILIARY_CANDIDATE_MISSING", {}, {},
            )
        center, expected, confidence = _pose_centers(yolo_item)
        board_size = _finite_pair(board_size_mm)
        image_size = _finite_pair((image_shape[1], image_shape[0]))
        if np.any(board_size <= 0) or np.any(image_size <= 0):
            raise ValueError("Invalid board dimensions")
        px_per_mm = image_size / board_size
        bias_mm = _finite_pair(common_bias_mm)
        reference_offset_mm = _finite_pair(slot_reference_offset_mm)
        measured_angle = float(evidence["long_axis_angle_deg_undirected"] if check_axis_angle
                               else evidence.get("long_axis_angle_deg_undirected", 0.0))
        if (not np.isfinite([expected_axis_deg, measured_angle, position_tolerance_mm, angle_tolerance_deg]).all()
                or position_tolerance_mm < 0 or angle_tolerance_deg < 0):
            raise ValueError("Invalid pose angle or tolerance")
        mask_area_px = evidence.get("mask_area_px")
        normalized_slot_distance = evidence.get("normalized_slot_distance")
        for value in (mask_area_px, normalized_slot_distance):
            if value is not None and (not np.isfinite(float(value)) or float(value) < 0):
                raise ValueError("Invalid auxiliary measurement")
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        return CheckEvidence(
            "auxiliary_pose", "UNKNOWN", "INVALID", 0.0,
            "YOLO_AUXILIARY_POSE_DATA_INVALID", {}, {},
        )
    raw_delta_mm = (center - expected) / px_per_mm
    # The segmentation centroid is not necessarily the physical part centre.
    # Legacy callers may remove a shared component-centroid bias. The fixed
    # reference profile passes ZERO common bias and a frozen raw-centroid
    # offset: inspecting a different set of parts cannot shift this reference.
    common_bias_corrected_mm = raw_delta_mm - bias_mm
    delta_mm = common_bias_corrected_mm - reference_offset_mm
    position_error = float(np.linalg.norm(delta_mm))
    axis_radians = np.deg2rad(expected_axis_deg)
    long_axis_unit = np.asarray(
        (np.cos(axis_radians), np.sin(axis_radians)), np.float64
    )
    transverse_axis_unit = np.asarray(
        (-np.sin(axis_radians), np.cos(axis_radians)), np.float64
    )
    longitudinal_offset = float(np.dot(delta_mm, long_axis_unit))
    transverse_offset = float(np.dot(delta_mm, transverse_axis_unit))
    angle_error = _angle_difference(measured_angle, expected_axis_deg, 180.0)
    angle_outside = check_axis_angle and angle_error > angle_tolerance_deg
    if position_error > position_tolerance_mm or angle_outside:
        status, reason = "FAIL", "AUXILIARY_POSE_OUTSIDE_LIMIT"
    else:
        status, reason = "PASS", "AUXILIARY_POSE_WITHIN_LIMIT"
    return CheckEvidence(
        "auxiliary_pose",
        status,
        "ADVISORY_ONLY",
        confidence,
        reason,
        {
            "center_px": center.tolist(),
            "expected_center_px": expected.tolist(),
            "raw_offset_mm": raw_delta_mm.tolist(),
            "common_bias_correction_mm": bias_mm.tolist(),
            "common_bias_corrected_offset_mm": common_bias_corrected_mm.tolist(),
            "slot_reference_correction_mm": reference_offset_mm.tolist(),
            "slot_reference_calibration_id": slot_reference_calibration_id,
            "offset_mm": delta_mm.tolist(),
            "position_error_mm": position_error,
            "longitudinal_offset_mm": longitudinal_offset,
            "transverse_offset_mm": transverse_offset,
            "absolute_longitudinal_offset_mm": abs(longitudinal_offset),
            "absolute_transverse_offset_mm": abs(transverse_offset),
            "mask_area_px": (
                float(mask_area_px) if mask_area_px is not None else None
            ),
            "normalized_slot_distance": (
                float(normalized_slot_distance)
                if normalized_slot_distance is not None
                else None
            ),
            "axis_angle_deg": measured_angle,
            "axis_angle_error_deg": angle_error,
            "axis_angle_checked": check_axis_angle,
        },
        {
            "position_tolerance_mm": position_tolerance_mm,
            "expected_axis_angle_deg": expected_axis_deg,
            "angle_tolerance_deg": angle_tolerance_deg,
            "slot_reference_calibration_id": slot_reference_calibration_id,
        },
    )


def estimate_common_projection_bias(
    yolo_items: dict[str, dict[str, Any]],
    image_shape: tuple[int, ...],
    board_size_mm: tuple[float, float],
    *,
    maximum_bias_mm: float = 1.5,
    minimum_candidates: int = 6,
    minimum_confidence: float = 0.50,
    diagnostic_only: bool = False,
) -> tuple[tuple[float, float], dict[str, Any]]:
    """Legacy component-centroid statistic, diagnostic-only in the fixed profile.

    A robust median is not an independent board-motion measurement: changed
    part membership or common real displacement can change it. Never use this
    statistic to update the frozen normal reference.
    """
    px_per_mm = np.asarray(
        (image_shape[1] / board_size_mm[0], image_shape[0] / board_size_mm[1]),
        np.float64,
    )
    offsets: list[np.ndarray] = []
    slot_ids: list[str] = []
    for slot_id, item in yolo_items.items():
        try:
            evidence = item.get("evidence", {})
            center, expected, confidence = _pose_centers(item)
            if not evidence.get("present", False) or confidence < minimum_confidence:
                continue
            offset = (center - expected) / px_per_mm
            if not np.isfinite(offset).all():
                continue
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            continue
        offsets.append(offset)
        slot_ids.append(slot_id)

    details: dict[str, Any] = {
        "applied": False,
        "candidate_count": len(offsets),
        "minimum_candidates": minimum_candidates,
        "maximum_bias_mm": maximum_bias_mm,
        "candidate_slots": slot_ids,
        "method": "component-wise median of shared YOLO segmentation centre offsets",
    }
    if len(offsets) < minimum_candidates:
        details["reason"] = "INSUFFICIENT_COMMON_BIAS_CANDIDATES"
        return (0.0, 0.0), details

    stacked = np.vstack(offsets)
    median = np.median(stacked, axis=0)
    magnitude = float(np.linalg.norm(median))
    details["estimated_bias_mm"] = median.tolist()
    details["estimated_bias_magnitude_mm"] = magnitude
    details["median_absolute_deviation_mm"] = np.median(
        np.abs(stacked - median), axis=0
    ).tolist()
    if diagnostic_only:
        details["reason"] = "COMPONENT_BIAS_DIAGNOSTIC_ONLY_USE_REGISTERED_BOARD"
        return (0.0, 0.0), details
    if magnitude > maximum_bias_mm:
        details["reason"] = "COMMON_BIAS_EXCEEDS_CONTRACT_LIMIT"
        return (0.0, 0.0), details

    details["applied"] = True
    details["reason"] = "COMMON_PROJECTION_BIAS_APPLIED"
    return (float(median[0]), float(median[1])), details
