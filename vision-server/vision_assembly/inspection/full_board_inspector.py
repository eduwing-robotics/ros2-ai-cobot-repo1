#!/usr/bin/env python3
"""Inspect all 25 assembled PCB components in a rectified S22 image.

The inspector deliberately separates physical assembly checks from exact
surface appearance.  The project parts are 3D printed, so harmless changes in
blob size, rounded corners, and texture are not treated as defects.  Unity
socket clearances define placement tolerances; a verified normal S22 image
provides the camera-specific projection and appearance reference.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

from package_leg_inspector import align_board, reference_peaks, set_reference
from layout_overrides import apply_component_slot_overrides


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "runtime/inspection/full_board"

STATUS_COLORS = {
    "PASS": (82, 222, 126),
    "RECHECK": (45, 194, 255),
    "FAIL": (66, 72, 244),
    "NOT_INSPECTABLE": (175, 180, 190),
    "PENDING_D435": (35, 190, 255),
}
TYPE_COLORS = {
    "GPU": (255, 145, 44),
    "HBM": (236, 80, 224),
    "Power Module": (30, 190, 255),
    "VRM": (65, 80, 245),
    "Inductor": (35, 225, 235),
    "SMD Capacitor": (75, 220, 90),
}
TYPE_LABELS = {
    "GPU": "G",
    "HBM": "H",
    "Power Module": "P",
    "VRM": "V",
    "Inductor": "I",
    "SMD Capacitor": "S",
}


@dataclass
class Pose:
    valid: bool
    center_px: list[float]
    angle_deg: float
    score: float
    area_px: float
    reason: str


@dataclass
class Check:
    name: str
    status: str
    reason: str
    measured: Any
    limit: Any


@dataclass
class LegSide:
    side: str
    status: str
    reason: str
    reference_peaks: int
    expected_peaks: int
    missing_indices: list[int]
    uncertain_indices: list[int]
    fallen_indices: list[int]
    lateral_shift_mm: list[float]
    strip_px: list[int]
    defect_points_px: list[list[int]]
    profile_shift_px: int = 0
    profile_alignment_score: float = 0.0
    evidence_ratio: list[float] = field(default_factory=list)
    local_peak_shift_px: list[int] = field(default_factory=list)
    raw_lateral_shift_mm: list[float] = field(default_factory=list)
    lateral_baseline_mm: list[float] = field(default_factory=list)


def _project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"OpenCV could not decode image: {path}")
    return image


def _atomic_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target.resolve())
    temporary.replace(link)


def _aggregate(statuses: list[str]) -> str:
    visible = [status for status in statuses if status != "NOT_INSPECTABLE"]
    if "FAIL" in visible:
        return "FAIL"
    if "RECHECK" in visible:
        return "RECHECK"
    return "PASS"


def _bounded_rect(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    image_shape: tuple[int, ...],
) -> tuple[int, int, int, int]:
    image_height, image_width = image_shape[:2]
    x0 = max(0, int(round(center_x - width * 0.5)))
    y0 = max(0, int(round(center_y - height * 0.5)))
    x1 = min(image_width, int(round(center_x + width * 0.5)))
    y1 = min(image_height, int(round(center_y + height * 0.5)))
    return x0, y0, x1, y1


def slot_geometry(
    placement: dict[str, Any],
    image_shape: tuple[int, ...],
    board_size_mm: tuple[float, float],
    mapping: dict[str, Any],
) -> tuple[float, float, float, float]:
    """Return centre and oriented nominal size in canonical S22 pixels."""
    height, width = image_shape[:2]
    board_width, board_height = board_size_mm
    center = placement["center_board_mm"]
    size = placement["nominal_size_mm"]
    sign_x = float(mapping.get("image_x_from_board_x_sign", 1.0))
    sign_y = float(mapping.get("image_y_from_board_y_sign", 1.0))
    center_x = (sign_x * float(center["x"]) / board_width + 0.5) * width
    center_y = (sign_y * float(center["y"]) / board_height + 0.5) * height
    size_x = float(size["x"]) / board_width * width
    size_y = float(size["y"]) / board_height * height
    return center_x, center_y, size_x, size_y


def _gray_feature(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(4, 4)).apply(gray)
    gx = cv2.Sobel(clahe, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(clahe, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    magnitude = cv2.GaussianBlur(magnitude, (3, 3), 0.55)
    maximum = float(magnitude.max())
    if maximum > 1.0e-6:
        magnitude /= maximum
    return magnitude


def _rotation_grid(limit: float, step: float) -> list[float]:
    if limit <= 0.0:
        return [0.0]
    count = max(1, int(math.ceil(limit / max(step, 0.1))))
    values = np.linspace(-limit, limit, 2 * count + 1)
    return [float(value) for value in values]


def template_pose(
    reference: np.ndarray,
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    type_settings: dict[str, Any],
    px_per_mm: tuple[float, float],
    search_settings: dict[str, Any],
) -> Pose:
    """Estimate small translation/rotation from edge structure, not texture."""
    center_x, center_y, size_x, size_y = geometry
    scale = type_settings.get("template_scale", [0.9, 0.9])
    template_width = max(12.0, size_x * float(scale[0]))
    template_height = max(12.0, size_y * float(scale[1]))
    tx0, ty0, tx1, ty1 = _bounded_rect(
        center_x, center_y, template_width, template_height, reference.shape
    )
    template = reference[ty0:ty1, tx0:tx1]
    if template.size == 0 or min(template.shape[:2]) < 8:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "EMPTY_TEMPLATE")

    margin_mm = float(
        type_settings.get(
            "search_margin_mm", search_settings.get("margin_mm", 2.0)
        )
    )
    margin_x = max(4, int(round(margin_mm * px_per_mm[0])))
    margin_y = max(4, int(round(margin_mm * px_per_mm[1])))
    sx0 = max(0, tx0 - margin_x)
    sy0 = max(0, ty0 - margin_y)
    sx1 = min(image.shape[1], tx1 + margin_x)
    sy1 = min(image.shape[0], ty1 + margin_y)
    search = image[sy0:sy1, sx0:sx1]
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "SEARCH_TOO_SMALL")

    search_feature = _gray_feature(search)
    limit = float(
        type_settings.get(
            "rotation_search_deg", search_settings.get("rotation_search_deg", 12.0)
        )
    )
    step = float(search_settings.get("rotation_step_deg", 1.0))
    template_center = ((template.shape[1] - 1) * 0.5, (template.shape[0] - 1) * 0.5)
    best_score = -1.0
    best_location = (0, 0)
    best_angle = 0.0
    for angle in _rotation_grid(limit, step):
        matrix = cv2.getRotationMatrix2D(template_center, angle, 1.0)
        rotated = cv2.warpAffine(
            template,
            matrix,
            (template.shape[1], template.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        feature = _gray_feature(rotated)
        if float(feature.std()) < 1.0e-5:
            continue
        scores = cv2.matchTemplate(search_feature, feature, cv2.TM_CCOEFF_NORMED)
        _, maximum, _, location = cv2.minMaxLoc(scores)
        if float(maximum) > best_score:
            best_score = float(maximum)
            best_location = location
            best_angle = angle

    if best_score < -0.5:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "NO_TEMPLATE_MATCH")
    found_x0 = sx0 + int(best_location[0])
    found_y0 = sy0 + int(best_location[1])
    found_center = [
        found_x0 + template.shape[1] * 0.5,
        found_y0 + template.shape[0] * 0.5,
    ]
    return Pose(True, found_center, best_angle, best_score, 0.0, "OK")


def _component_mask(image: np.ndarray, detector: str) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    if detector == "yellow_mask":
        mask = (
            (hsv[:, :, 0] >= 14)
            & (hsv[:, :, 0] <= 43)
            & (hsv[:, :, 1] >= 58)
            & (hsv[:, :, 2] >= 105)
        )
    elif detector == "white_mask":
        mask = (
            (lab[:, :, 0] >= 132)
            & (hsv[:, :, 1] <= 112)
            & (hsv[:, :, 2] >= 118)
        )
    elif detector == "dark_rect_mask":
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (0, 0), 2.8)
        _, result = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )
        result = cv2.morphologyEx(
            result, cv2.MORPH_CLOSE, np.ones((9, 9), dtype=np.uint8)
        )
        result = cv2.morphologyEx(
            result, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
        )
        return result
    else:
        raise ValueError(f"Unsupported mask detector: {detector}")
    result = mask.astype(np.uint8) * 255
    result = cv2.morphologyEx(
        result, cv2.MORPH_OPEN, np.ones((2, 2), dtype=np.uint8)
    )
    result = cv2.morphologyEx(
        result, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8)
    )
    return result


def circle_pose(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    px_per_mm: tuple[float, float],
    margin_mm: float,
    target_area_px: float | None = None,
) -> Pose:
    """Detect the inductor outer circle independently of its black mark."""
    center_x, center_y, size_x, size_y = geometry
    roi_width = size_x + 2.0 * margin_mm * px_per_mm[0]
    roi_height = size_y + 2.0 * margin_mm * px_per_mm[1]
    x0, y0, x1, y1 = _bounded_rect(
        center_x, center_y, roi_width, roi_height, image.shape
    )
    roi = image[y0:y1, x0:x1]
    if roi.size == 0:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "EMPTY_SEARCH")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    expected_radius = min(size_x, size_y) * 0.5
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.0,
        minDist=max(12.0, expected_radius * 0.7),
        param1=70.0, param2=22.0,
        minRadius=max(4, int(round(expected_radius * 0.68))),
        maxRadius=max(6, int(round(expected_radius * 1.22))),
    )
    if circles is None:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "NO_CIRCLE")
    local_expected = np.asarray([center_x - x0, center_y - y0], dtype=np.float32)
    candidates = []
    for circle in circles[0]:
        local_center = np.asarray(circle[:2], dtype=np.float32)
        radius = float(circle[2])
        distance = float(np.linalg.norm(local_center - local_expected)) / max(
            expected_radius, 1.0
        )
        radius_error = abs(math.log(max(radius, 1.0) / max(expected_radius, 1.0)))
        candidates.append((distance + 0.65 * radius_error, local_center, radius))
    _, local_center, radius = min(candidates, key=lambda item: item[0])
    area = math.pi * radius * radius
    if target_area_px:
        ratio = area / max(target_area_px, 1.0)
        score = min(ratio, 1.0 / max(ratio, 1.0e-6))
    else:
        expected_area = math.pi * expected_radius * expected_radius
        ratio = area / max(expected_area, 1.0)
        score = min(ratio, 1.0 / max(ratio, 1.0e-6))
    return Pose(
        True,
        [x0 + float(local_center[0]), y0 + float(local_center[1])],
        0.0, float(np.clip(score, 0.0, 1.0)), area, "OK",
    )


def circle_white_fraction(
    image: np.ndarray,
    center_px: list[float],
    area_px: float,
) -> float:
    """Measure the white inductor body independently of Hough radius jitter."""
    radius = math.sqrt(max(area_px, 1.0) / math.pi)
    half_size = max(6, int(math.ceil(radius * 0.86)))
    x0, y0, x1, y1 = _bounded_rect(
        float(center_px[0]), float(center_px[1]),
        half_size * 2.0, half_size * 2.0, image.shape,
    )
    roi = image[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0
    height, width = roi.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    local_cx = (width - 1) * 0.5
    local_cy = (height - 1) * 0.5
    inner = (
        (xx - local_cx) ** 2 + (yy - local_cy) ** 2
        <= max(radius * 0.82, 3.0) ** 2
    )
    if not np.any(inner):
        return 0.0
    lab_l = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)[:, :, 0]
    hsv_s = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 1]
    white = (lab_l >= 120) & (hsv_s <= 112)
    return float(np.mean(white[inner]))


def _rect_long_axis(rect: tuple[Any, Any, float]) -> float:
    box = cv2.boxPoints(rect)
    vectors = [box[(index + 1) % 4] - box[index] for index in range(4)]
    vector = max(vectors, key=lambda item: float(np.dot(item, item)))
    return float(math.degrees(math.atan2(float(vector[1]), float(vector[0]))) % 180.0)


def mask_pose(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    detector: str,
    px_per_mm: tuple[float, float],
    margin_mm: float,
    target_area_px: float | None = None,
) -> Pose:
    center_x, center_y, size_x, size_y = geometry
    roi_width = size_x + 2.0 * margin_mm * px_per_mm[0]
    roi_height = size_y + 2.0 * margin_mm * px_per_mm[1]
    x0, y0, x1, y1 = _bounded_rect(
        center_x, center_y, roi_width, roi_height, image.shape
    )
    roi = image[y0:y1, x0:x1]
    if roi.size == 0:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "EMPTY_SEARCH")
    mask = _component_mask(roi, detector)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    expected_area = max(1.0, size_x * size_y)
    target = float(target_area_px) if target_area_px else expected_area * 0.72
    candidates: list[tuple[float, np.ndarray, float, tuple[Any, Any, float]]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < expected_area * 0.055:
            continue
        rect = cv2.minAreaRect(contour)
        local_center = rect[0]
        distance = math.hypot(
            float(local_center[0]) - (center_x - x0),
            float(local_center[1]) - (center_y - y0),
        ) / max(size_x, size_y, 1.0)
        area_error = abs(math.log(max(area, 1.0) / max(target, 1.0)))
        candidates.append((area_error + 0.7 * distance, contour, area, rect))
    if not candidates:
        return Pose(False, [center_x, center_y], 0.0, 0.0, 0.0, "NO_FEATURE_CONTOUR")
    _, contour, area, rect = min(candidates, key=lambda item: item[0])
    moments = cv2.moments(contour)
    if abs(float(moments["m00"])) > 1.0e-6:
        local_center_x = float(moments["m10"] / moments["m00"])
        local_center_y = float(moments["m01"] / moments["m00"])
    else:
        local_center_x, local_center_y = map(float, rect[0])
    # The 3D-printed white/yellow ends may be slightly more bulbous on one
    # side.  A contour centroid would turn that harmless shape variation into
    # a false position shift; the fitted outer rectangle centre is stable.
    center = [x0 + float(rect[0][0]), y0 + float(rect[0][1])]
    angle = _rect_long_axis(rect)
    if target_area_px:
        ratio = area / max(float(target_area_px), 1.0)
        score = min(ratio, 1.0 / max(ratio, 1.0e-6))
    else:
        score = min(area / max(target, 1.0), target / max(area, 1.0))
    return Pose(True, center, angle, float(np.clip(score, 0.0, 1.0)), area, "OK")


def angle_delta_deg(sample: float, reference: float, period: float = 180.0) -> float:
    return float((sample - reference + period * 0.5) % period - period * 0.5)


def geometric_rotation_tolerance_deg(
    part_size: list[float], socket_size: list[float]
) -> float:
    """First positive angle at which a rectangular part no longer fits."""
    width, height = sorted(map(float, part_size))
    socket_width, socket_height = sorted(map(float, socket_size))
    previous = 0.0
    for angle in np.linspace(0.0, 45.0, 4501):
        radians = math.radians(float(angle))
        projected_width = width * math.cos(radians) + height * math.sin(radians)
        projected_height = width * math.sin(radians) + height * math.cos(radians)
        if projected_width > socket_width or projected_height > socket_height:
            return previous
        previous = float(angle)
    return 45.0


def _white_mask(image: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (
        (lab[:, :, 0] >= int(settings.get("lab_l_min", 130)))
        & (hsv[:, :, 1] <= int(settings.get("hsv_s_max", 105)))
    ).astype(np.uint8)
    kernel_size = max(1, int(settings.get("open_kernel_px", 2)))
    if kernel_size > 1:
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
    return mask


def _oriented_component_roi(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    angle_deg: float,
    scale: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a part-aligned crop and its local-to-image affine transform."""
    center_x, center_y, size_x, size_y = geometry
    output_width = max(12, int(round(size_x * scale)))
    output_height = max(12, int(round(size_y * scale)))
    image_to_rotated = cv2.getRotationMatrix2D(
        (float(center_x), float(center_y)), -float(angle_deg), 1.0
    )
    rotated = cv2.warpAffine(
        image, image_to_rotated, (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101,
    )
    roi = cv2.getRectSubPix(
        rotated, (output_width, output_height),
        (float(center_x), float(center_y)),
    )
    rotated_to_image = np.eye(3, dtype=np.float64)
    rotated_to_image[:2] = cv2.invertAffineTransform(image_to_rotated)
    local_to_rotated = np.asarray(
        [
            [1.0, 0.0, center_x - (output_width - 1) * 0.5],
            [0.0, 1.0, center_y - (output_height - 1) * 0.5],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return roi, rotated_to_image @ local_to_rotated


def _map_local_point(
    point: tuple[float, float], local_to_image: np.ndarray,
) -> list[float]:
    mapped = local_to_image @ np.asarray([point[0], point[1], 1.0])
    return [float(mapped[0]), float(mapped[1])]


def detect_polarity_dot(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    angle_deg: float,
    settings: dict[str, Any],
    px_per_mm: tuple[float, float],
    anchor_abs_xy: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Locate the actual circular polarity blob in a part-normalized ROI."""
    _, _, size_x, size_y = geometry
    scale = float(settings.get("dot_geometry_scale", 1.18))
    roi, local_to_image = _oriented_component_roi(
        image, geometry, angle_deg, scale
    )
    if roi.size == 0:
        return {"corner": None, "corner_scores": {}, "candidates": []}
    mask = _white_mask(roi, settings).astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    roi_center_x = (roi.shape[1] - 1) * 0.5
    roi_center_y = (roi.shape[0] - 1) * 0.5
    pixel_scale = max(1.0, (px_per_mm[0] + px_per_mm[1]) * 0.5)
    minimum_radius_mm = float(settings.get("dot_min_radius_mm", 0.42))
    candidates: list[dict[str, Any]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        local_x, local_y = map(float, centroids[label])
        normalized_x = (local_x - roi_center_x) / max(size_x * 0.5, 1.0)
        normalized_y = (local_y - roi_center_y) / max(size_y * 0.5, 1.0)
        # The dot lies at a body corner.  Central logos/text and side pins are
        # excluded before component size is compared.
        if not (
            0.10 <= abs(normalized_x) <= 0.90
            and 0.40 <= abs(normalized_y) <= 1.16
        ):
            continue
        component_mask = (labels == label).astype(np.uint8)
        distance = cv2.distanceTransform(component_mask, cv2.DIST_L2, 5)
        _, radius_px, _, maximum_location = cv2.minMaxLoc(distance)
        radius_mm = float(radius_px) / pixel_scale
        if radius_mm < minimum_radius_mm * 0.72:
            continue
        contours, _ = cv2.findContours(
            component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        perimeter = max(
            [float(cv2.arcLength(contour, True)) for contour in contours]
            or [0.0]
        )
        circularity = (
            float(np.clip(4.0 * math.pi * area / (perimeter * perimeter), 0.0, 1.0))
            if perimeter > 1.0e-6 else 0.0
        )
        corner = (
            ("upper" if normalized_y < 0.0 else "lower")
            + "_"
            + ("left" if normalized_x < 0.0 else "right")
        )
        anchor_error = (
            math.hypot(
                abs(normalized_x) - anchor_abs_xy[0],
                abs(normalized_y) - anchor_abs_xy[1],
            )
            if anchor_abs_xy else 0.0
        )
        rank_score = (
            radius_mm
            + 0.05 * circularity
            - float(settings.get("dot_anchor_penalty", 0.8)) * anchor_error
        )
        candidates.append({
            "corner": corner,
            "center_px": _map_local_point((local_x, local_y), local_to_image),
            "core_px": _map_local_point(
                (float(maximum_location[0]), float(maximum_location[1])),
                local_to_image,
            ),
            "normalized_xy": [round(normalized_x, 4), round(normalized_y, 4)],
            "radius_mm": round(radius_mm, 4),
            "area_px": area,
            "circularity": round(circularity, 4),
            "anchor_error": round(anchor_error, 4),
            "rank_score": round(rank_score, 4),
        })
    candidates.sort(
        key=lambda item: (
            float(item["rank_score"]), float(item["radius_mm"]),
            float(item["circularity"]),
        ),
        reverse=True,
    )
    corner_scores = {
        name: max(
            [float(item["radius_mm"]) for item in candidates if item["corner"] == name]
            or [0.0]
        )
        for name in ("upper_left", "upper_right", "lower_left", "lower_right")
    }
    winner = candidates[0] if candidates else None
    second_rank = float(candidates[1]["rank_score"]) if len(candidates) > 1 else 0.0
    return {
        "corner": winner["corner"] if winner else None,
        "center_px": winner["center_px"] if winner else None,
        "core_px": winner["core_px"] if winner else None,
        "normalized_xy": winner["normalized_xy"] if winner else None,
        "radius_mm": float(winner["radius_mm"]) if winner else 0.0,
        "circularity": float(winner["circularity"]) if winner else 0.0,
        "rank_score": float(winner["rank_score"]) if winner else 0.0,
        "winner_margin": (
            float(winner["rank_score"]) - second_rank if winner else 0.0
        ),
        "corner_scores": corner_scores,
        "candidates": candidates[:8],
    }


def _hbm_logo_color_pixels(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    angle_deg: float,
    settings: dict[str, Any],
) -> int:
    """Count the red/orange centre logo without counting white pins/dot."""
    _, _, size_x, size_y = geometry
    roi, _ = _oriented_component_roi(image, geometry, angle_deg, 1.0)
    if roi.size == 0:
        return 0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    height, width = roi.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    normalized_x = (xx - (width - 1) * 0.5) / max(size_x * 0.5, 1.0)
    normalized_y = (yy - (height - 1) * 0.5) / max(size_y * 0.5, 1.0)
    centre = (
        (np.abs(normalized_x) <= float(settings.get("hbm_logo_half_x", 0.42)))
        & (np.abs(normalized_y) <= float(settings.get("hbm_logo_half_y", 0.28)))
    )
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    hue_limit = int(settings.get("hbm_logo_hue_max", 42))
    logo_color = (
        ((hue <= hue_limit) | (hue >= 170))
        & (saturation >= int(settings.get("hbm_logo_s_min", 45)))
        & (value >= int(settings.get("hbm_logo_v_min", 45)))
    )
    return int(np.count_nonzero(centre & logo_color))


def inspect_hbm_presence(
    reference: np.ndarray,
    sample: np.ndarray,
    reference_geometry: tuple[float, float, float, float],
    sample_geometry: tuple[float, float, float, float],
    sample_angle_deg: float,
    settings: dict[str, Any],
    px_per_mm: tuple[float, float],
) -> Check:
    """Require both the polarity dot and centre logo for HBM presence."""
    reference_dot = detect_polarity_dot(
        reference, reference_geometry, 0.0, settings, px_per_mm
    )
    reference_candidates = [
        candidate for candidate in reference_dot["candidates"]
        if candidate["corner"] == "lower_left"
    ]
    reference_anchor = None
    if reference_candidates:
        anchor_candidate = max(
            reference_candidates,
            key=lambda candidate: float(candidate["radius_mm"]),
        )
        reference_anchor = (
            abs(float(anchor_candidate["normalized_xy"][0])),
            abs(float(anchor_candidate["normalized_xy"][1])),
        )
    sample_dot = detect_polarity_dot(
        sample,
        sample_geometry,
        sample_angle_deg,
        settings,
        px_per_mm,
        reference_anchor,
    )
    dot_minimum = float(settings.get("dot_min_radius_mm", 0.42))
    dot_present = float(sample_dot["radius_mm"]) >= dot_minimum
    reference_logo_pixels = _hbm_logo_color_pixels(
        reference, reference_geometry, 0.0, settings
    )
    sample_logo_pixels = _hbm_logo_color_pixels(
        sample, sample_geometry, sample_angle_deg, settings
    )
    logo_ratio = sample_logo_pixels / max(reference_logo_pixels, 1)
    logo_present_limit = float(settings.get("hbm_logo_present_ratio_min", 0.3))
    logo_missing_limit = float(settings.get("hbm_logo_missing_ratio_max", 0.08))
    logo_present = logo_ratio >= logo_present_limit
    logo_missing = logo_ratio <= logo_missing_limit
    if dot_present and logo_present:
        status, reason = "PASS", "HBM_DOT_AND_CENTER_LOGO_PRESENT"
    elif not dot_present and logo_missing:
        status, reason = "FAIL", "HBM_DOT_AND_CENTER_LOGO_ABSENT"
    else:
        status, reason = "RECHECK", "HBM_PRESENCE_FEATURES_DISAGREE"
    return Check(
        "presence",
        status,
        reason,
        {
            "dot_present": dot_present,
            "dot_radius_mm": round(float(sample_dot["radius_mm"]), 4),
            "dot_corner": sample_dot["corner"],
            "center_logo_pixels": sample_logo_pixels,
            "reference_center_logo_pixels": reference_logo_pixels,
            "center_logo_ratio": round(logo_ratio, 4),
        },
        {
            "dot_minimum_radius_mm": dot_minimum,
            "logo_present_ratio_min": logo_present_limit,
            "logo_missing_ratio_max": logo_missing_limit,
            "decision": "PASS_BOTH_PRESENT_FAIL_BOTH_ABSENT",
        },
    )


def _leg_white_mask(
    image: np.ndarray,
    settings: dict[str, Any],
    white_settings: dict[str, Any],
) -> np.ndarray:
    """Find printed white legs despite side-dependent illumination.

    The oblique S22 view makes the two package sides differ greatly in
    brightness.  A single global L threshold therefore rejects intact legs on
    the shaded side.  Otsu is evaluated inside each narrow side strip, then
    bounded so dark package texture cannot become a leg.
    """
    if "adaptive_lab_min" not in settings:
        return _white_mask(image, white_settings)
    lab_l = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)[:, :, 0]
    hsv_s = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 1]
    saturation_ok = hsv_s <= int(settings.get("adaptive_hsv_s_max", 130))
    values = lab_l[saturation_ok]
    if values.size < 16:
        return _white_mask(image, white_settings)
    threshold, _ = cv2.threshold(
        values.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )
    threshold = int(round(float(threshold))) + int(
        settings.get("adaptive_lab_offset", 5)
    )
    threshold = int(np.clip(
        threshold,
        int(settings.get("adaptive_lab_min", 40)),
        int(settings.get("adaptive_lab_max", 145)),
    ))
    mask = ((lab_l >= threshold) & saturation_ok).astype(np.uint8)
    kernel_size = max(1, int(white_settings.get("open_kernel_px", 2)))
    if kernel_size > 1:
        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN,
            np.ones((kernel_size, kernel_size), dtype=np.uint8),
        )
    return mask


def detect_dot_corner(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    settings: dict[str, Any],
    px_per_mm: tuple[float, float],
) -> tuple[str | None, dict[str, float]]:
    detection = detect_polarity_dot(
        image, geometry, 0.0, settings, px_per_mm
    )
    return detection["corner"], detection["corner_scores"]


def _strip_rect(
    geometry: tuple[float, float, float, float],
    side: str,
    half_width_px: int,
    image_shape: tuple[int, ...],
) -> tuple[int, int, int, int]:
    center_x, center_y, size_x, size_y = geometry
    sign = -1.0 if side == "left" else 1.0
    strip_center_x = int(round(center_x + sign * size_x * 0.5))
    y0 = max(0, int(round(center_y - size_y * 0.5)))
    y1 = min(image_shape[0], int(round(center_y + size_y * 0.5)))
    x0 = max(0, strip_center_x - half_width_px)
    x1 = min(image_shape[1], strip_center_x + half_width_px)
    return x0, y0, x1, y1


def inspect_inductor_mark(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    settings: dict[str, Any],
    circle_area_px: float = 0.0,
) -> Check:
    """Measure the black mark angle on the white disc in polar coordinates."""
    center_x, center_y, size_x, size_y = geometry
    # Hough radius varies when the black crescent breaks the outer white edge.
    # Unity diameter is stable, so only the detected centre comes from Hough.
    radius = min(size_x, size_y) * float(
        settings.get("inductor_mark_radius_scale", 0.48)
    )
    x0, y0, x1, y1 = _bounded_rect(
        center_x, center_y, radius * 2.05, radius * 2.05, image.shape
    )
    roi = image[y0:y1, x0:x1]
    if roi.size == 0 or min(roi.shape[:2]) < 8:
        return Check(
            "orientation_mark", "NOT_INSPECTABLE", "INDUCTOR_MARK_VIEW_UNAVAILABLE",
            None, {"expected_side": "left"},
        )
    lab_l = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
    height, width = lab_l.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    local_cx = float(center_x - x0)
    local_cy = float(center_y - y0)
    local_x = xx - local_cx
    local_y = yy - local_cy
    normalized_radius = np.sqrt(local_x * local_x + local_y * local_y) / max(
        radius, 1.0
    )
    angles = (
        np.degrees(np.arctan2(local_y, local_x)) + 360.0
    ) % 360.0
    radial_min = float(settings.get("inductor_mark_radial_min", 0.18))
    radial_max = float(settings.get("inductor_mark_radial_max", 0.72))
    bins = max(36, int(settings.get("inductor_mark_angle_bins", 72)))
    bin_width = 360.0 / bins
    profile = np.full(bins, np.nan, dtype=np.float32)
    annulus = (
        (normalized_radius >= radial_min)
        & (normalized_radius <= radial_max)
    )
    for index in range(bins):
        lower = index * bin_width
        region = annulus & (angles >= lower) & (angles < lower + bin_width)
        if np.any(region):
            profile[index] = float(np.mean(lab_l[region]))
    if int(np.count_nonzero(np.isfinite(profile))) < bins * 0.9:
        return Check(
            "orientation_mark", "NOT_INSPECTABLE", "INDUCTOR_MARK_VIEW_UNAVAILABLE",
            None, {"expected_side": "left"},
        )
    missing = ~np.isfinite(profile)
    profile[missing] = float(np.nanmedian(profile))
    kernel = np.asarray([1, 2, 3, 4, 5, 4, 3, 2, 1], dtype=np.float32)
    kernel /= float(kernel.sum())
    pad = len(kernel) // 2
    smooth = np.convolve(
        np.pad(profile, (pad, pad), mode="wrap"), kernel, mode="valid"
    )
    mark_index = int(np.argmin(smooth))
    mark_angle = (mark_index + 0.5) * bin_width
    if mark_angle > 180.0:
        mark_angle -= 360.0
    contrast = float(np.median(smooth) - smooth[mark_index])
    minimum = float(settings.get("inductor_mark_contrast_min", 7.0))
    expected_angle = float(settings.get("inductor_expected_mark_angle_deg", 180.0))
    tolerance = float(settings.get("inductor_mark_angle_tolerance_deg", 42.0))
    angle_error = angle_delta_deg(mark_angle, expected_angle, 360.0)
    side = "left" if math.cos(math.radians(mark_angle)) < 0.0 else "right"
    if contrast < minimum:
        status, reason, side = "RECHECK", "INDUCTOR_MARK_NOT_CLEAR", "uncertain"
    elif abs(angle_error) <= tolerance:
        status, reason = "PASS", "BLACK_MARK_ANGLE_CORRECT"
    else:
        status, reason = "FAIL", "BLACK_MARK_ANGLE_WRONG"
    mark_radius = radius * 0.55
    mark_point = [
        center_x + math.cos(math.radians(mark_angle)) * mark_radius,
        center_y + math.sin(math.radians(mark_angle)) * mark_radius,
    ]
    return Check(
        "orientation_mark", status, reason,
        {
            "detected_side": side,
            "mark_angle_deg": round(mark_angle, 3),
            "angle_error_deg": round(angle_error, 3),
            "mark_contrast_lab_l": round(contrast, 3),
            "mark_point_px": [round(value, 3) for value in mark_point],
        },
        {
            "expected_side": "left",
            "expected_angle_deg": expected_angle,
            "absolute_max_angle_error_deg": tolerance,
            "minimum_contrast": minimum,
        },
    )


def _leg_profile(mask: np.ndarray) -> np.ndarray:
    profile = mask.mean(axis=1).astype(np.float32)
    return cv2.GaussianBlur(profile.reshape(-1, 1), (1, 7), 1.1).ravel()


def _best_profile_shift(
    reference_profile: np.ndarray,
    sample_profile: np.ndarray,
    max_shift_px: int,
) -> tuple[int, float]:
    """Register the whole pin row before judging individual printed pins."""
    length = min(len(reference_profile), len(sample_profile))
    if length < 8 or max_shift_px <= 0:
        return 0, 0.0
    reference_profile = reference_profile[:length]
    sample_profile = sample_profile[:length]
    best_shift = 0
    best_score = -1.0
    for shift in range(-max_shift_px, max_shift_px + 1):
        if shift >= 0:
            reference_values = reference_profile[:length - shift or None]
            sample_values = sample_profile[shift:]
        else:
            reference_values = reference_profile[-shift:]
            sample_values = sample_profile[:length + shift]
        if len(reference_values) < 8:
            continue
        reference_values = reference_values - float(reference_values.mean())
        sample_values = sample_values - float(sample_values.mean())
        denominator = float(
            np.linalg.norm(reference_values) * np.linalg.norm(sample_values)
        )
        score = (
            float(np.dot(reference_values, sample_values)) / denominator
            if denominator > 1.0e-8 else -1.0
        )
        if score > best_score:
            best_shift = shift
            best_score = score
    return best_shift, best_score


def _local_white_geometry(
    mask: np.ndarray,
    center_y: int,
    radius: int,
    target_x: float | None = None,
) -> tuple[float, float]:
    y0 = max(0, center_y - radius)
    y1 = min(mask.shape[0], center_y + radius + 1)
    local = mask[y0:y1].astype(np.uint8)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        local, connectivity=8
    )
    candidates: list[tuple[float, float, int]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 2:
            continue
        xs = np.nonzero(labels == label)[1]
        if xs.size == 0:
            continue
        low, high = np.percentile(xs.astype(np.float32), [5.0, 95.0])
        candidates.append((
            float(centroids[label][0]),
            float(high - low + 1.0),
            area,
        ))
    if not candidates:
        return math.nan, 0.0
    if target_x is None:
        chosen = max(candidates, key=lambda item: item[2])
    else:
        chosen = min(
            candidates,
            key=lambda item: (abs(item[0] - target_x), -item[2]),
        )
    return chosen[0], chosen[1]


def _robust_lateral_baseline(
    values: list[float], enabled: bool,
) -> list[float]:
    """Estimate the side-wide perspective/rotation trend without outliers."""
    if not enabled:
        return [0.0] * len(values)
    valid = [
        (index, value)
        for index, value in enumerate(values)
        if math.isfinite(value)
    ]
    if len(valid) < 4:
        return [0.0] * len(values)
    slopes = [
        (right_value - left_value) / (right_index - left_index)
        for left_position, (left_index, left_value) in enumerate(valid)
        for right_index, right_value in valid[left_position + 1:]
        if right_index != left_index
    ]
    slope = float(np.median(slopes)) if slopes else 0.0
    intercept = float(np.median([
        value - slope * index for index, value in valid
    ]))
    return [intercept + slope * index for index in range(len(values))]


def inspect_leg_side(
    reference_strip: np.ndarray,
    sample_strip: np.ndarray,
    side: str,
    strip_rect: tuple[int, int, int, int],
    settings: dict[str, Any],
    white_settings: dict[str, Any],
    px_per_mm_x: float,
) -> LegSide:
    reference_mask = _leg_white_mask(
        reference_strip, settings, white_settings
    )
    sample_mask = _leg_white_mask(sample_strip, settings, white_settings)
    reference_profile = _leg_profile(reference_mask)
    sample_profile = _leg_profile(sample_mask)
    peaks = reference_peaks(reference_profile, side, settings)
    profile_shift, profile_alignment_score = _best_profile_shift(
        reference_profile,
        sample_profile,
        int(settings.get("max_profile_shift_px", 0)),
    )
    expected = int(settings["minimum_reference_peaks"])
    base = {
        "side": side,
        "reference_peaks": len(peaks),
        "expected_peaks": expected,
        "strip_px": list(strip_rect),
        "profile_shift_px": profile_shift,
        "profile_alignment_score": round(profile_alignment_score, 4),
    }
    if len(peaks) < expected:
        return LegSide(
            **base,
            status="NOT_INSPECTABLE",
            reason="S22_SIDE_HIDDEN",
            missing_indices=[],
            uncertain_indices=[],
            fallen_indices=[],
            lateral_shift_mm=[],
            defect_points_px=[],
        )

    reference_radius = int(settings.get("reference_peak_radius_px", 3))
    sample_radius = int(settings.get("sample_peak_radius_px", 5))
    missing_limit = float(settings.get("missing_evidence_ratio", 0.2))
    uncertain_limit = float(settings.get("uncertain_evidence_ratio", 0.3))
    peak_search_radius = int(settings.get(
        "sample_peak_search_radius_px", sample_radius
    ))
    lateral_limit = float(settings.get("maximum_lateral_shift_mm", 0.7))
    extra_width_limit = float(settings.get("maximum_extra_width_mm", 0.8))
    missing: list[int] = []
    uncertain: list[int] = []
    fallen: list[int] = []
    raw_lateral_shifts: list[float] = []
    evidence_ratios: list[float] = []
    local_peak_shifts: list[int] = []
    extra_widths_mm: list[float] = []
    fall_check_enabled: list[bool] = []
    pin_points: list[list[int]] = []
    points: list[list[int]] = []
    x0, y0, x1, _ = strip_rect

    for index, peak in enumerate(peaks, start=1):
        registered_sample_peak = int(np.clip(
            peak + profile_shift, 0, len(sample_profile) - 1
        ))
        search_y0 = max(0, registered_sample_peak - peak_search_radius)
        search_y1 = min(
            len(sample_profile),
            registered_sample_peak + peak_search_radius + 1,
        )
        sample_peak = (
            search_y0 + int(np.argmax(sample_profile[search_y0:search_y1]))
            if search_y1 > search_y0 else registered_sample_peak
        )
        local_peak_shifts.append(sample_peak - peak)
        reference_value = float(
            reference_profile[
                max(0, peak - reference_radius): peak + reference_radius + 1
            ].max()
        )
        sample_value = float(
            sample_profile[
                max(0, sample_peak - sample_radius):
                sample_peak + sample_radius + 1
            ].max()
        )
        ratio = sample_value / max(reference_value, 1.0e-6)
        evidence_ratios.append(round(ratio, 4))
        reference_x, reference_width = _local_white_geometry(
            reference_mask,
            peak,
            reference_radius + 2,
            reference_mask.shape[1] * 0.5,
        )
        sample_x, sample_width = _local_white_geometry(
            sample_mask,
            sample_peak,
            sample_radius + 2,
            reference_x if math.isfinite(reference_x) else None,
        )
        lateral = (
            (sample_x - reference_x) / max(px_per_mm_x, 1.0e-6)
            if math.isfinite(sample_x) and math.isfinite(reference_x)
            else math.nan
        )
        raw_lateral_shifts.append(float(lateral))
        point_x = int(round((x0 + x1) * 0.5))
        point_y = int(y0 + sample_peak)
        pin_points.append([point_x, point_y])
        extra_widths_mm.append(
            (sample_width - reference_width) / max(px_per_mm_x, 1.0e-6)
        )
        end_fraction = float(settings.get("fallen_end_ignore_fraction", 0.16))
        end_corner_zone = (
            peak <= int(round(len(reference_profile) * end_fraction))
            or peak >= int(round(len(reference_profile) * (1.0 - end_fraction)))
        )
        dot_corner_zone = (
            side == "left"
            and peak >= int(round(len(reference_profile) * 0.67))
        )
        fall_check_enabled.append(not end_corner_zone and not dot_corner_zone)
        if ratio < missing_limit or not math.isfinite(sample_x):
            missing.append(index)
            points.append([point_x, point_y])
            continue
        if ratio < uncertain_limit:
            uncertain.append(index)

    baseline_source = [
        value if evidence_ratios[index] >= uncertain_limit else math.nan
        for index, value in enumerate(raw_lateral_shifts)
    ]
    lateral_baseline = _robust_lateral_baseline(
        baseline_source,
        bool(settings.get("remove_common_lateral_trend", False)),
    )
    lateral_shifts = [
        value - lateral_baseline[index]
        if math.isfinite(value) else math.nan
        for index, value in enumerate(raw_lateral_shifts)
    ]
    fallen_recheck_limit = float(settings.get(
        "fallen_recheck_lateral_shift_mm", lateral_limit * 0.75
    ))
    for zero_index, lateral in enumerate(lateral_shifts):
        pin_index = zero_index + 1
        if (
            pin_index in missing
            or not fall_check_enabled[zero_index]
            or not math.isfinite(lateral)
        ):
            continue
        if (
            abs(lateral) > lateral_limit
            or (
                abs(lateral) > fallen_recheck_limit
                and extra_widths_mm[zero_index] > extra_width_limit
            )
        ):
            fallen.append(pin_index)
            points.append(pin_points[zero_index])

    if missing or fallen:
        status = "FAIL"
        reason = "MISSING_OR_FALLEN_WHITE_LEG"
    elif uncertain:
        status = "RECHECK"
        reason = "WHITE_LEG_EVIDENCE_UNCERTAIN"
    else:
        status = "PASS"
        reason = "VISIBLE_WHITE_LEGS_PRESENT_AND_ALIGNED"
    return LegSide(
        **base,
        status=status,
        reason=reason,
        missing_indices=missing,
        uncertain_indices=uncertain,
        fallen_indices=fallen,
        lateral_shift_mm=[
            round(float(value), 4) if math.isfinite(value) else math.nan
            for value in lateral_shifts
        ],
        defect_points_px=points,
        evidence_ratio=evidence_ratios,
        local_peak_shift_px=local_peak_shifts,
        raw_lateral_shift_mm=[
            round(float(value), 4) if math.isfinite(value) else math.nan
            for value in raw_lateral_shifts
        ],
        lateral_baseline_mm=[round(float(value), 4) for value in lateral_baseline],
    )


def _presence_check(score: float, type_settings: dict[str, Any], detector: str) -> Check:
    if detector == "edge_template":
        pass_limit = float(type_settings.get("presence_pass_score", 0.35))
        fail_limit = float(type_settings.get("presence_fail_score", 0.14))
        unit = "edge_match"
    elif detector == "circle_edge":
        pass_limit = float(type_settings.get("presence_pass_ratio", 0.45))
        fail_limit = float(type_settings.get("presence_fail_ratio", 0.14))
        unit = "white_disc_fraction"
    else:
        pass_limit = float(type_settings.get("presence_pass_ratio", 0.45))
        fail_limit = float(type_settings.get("presence_fail_ratio", 0.14))
        unit = "reference_area_ratio"
    if score >= pass_limit:
        status, reason = "PASS", "COMPONENT_PRESENT"
    elif score <= fail_limit:
        status, reason = "FAIL", "COMPONENT_MISSING"
    else:
        status, reason = "RECHECK", "COMPONENT_PRESENCE_UNCERTAIN"
    return Check(
        "presence", status, reason,
        {"score": round(float(score), 4), "metric": unit},
        {"pass_min": pass_limit, "fail_max": fail_limit},
    )


def _slot_label(slot_id: str, component_type: str) -> str:
    prefix = TYPE_LABELS[component_type]
    if slot_id == "ai_gpu":
        return prefix
    try:
        return f"{prefix}{int(slot_id.rsplit('_', 1)[1])}"
    except (ValueError, IndexError):
        return prefix


def inspect_component(
    placement: dict[str, Any],
    reference: np.ndarray,
    aligned: np.ndarray,
    geometry: tuple[float, float, float, float],
    config: dict[str, Any],
    clearance: dict[str, Any],
    px_per_mm: tuple[float, float],
) -> dict[str, Any]:
    component_type = str(placement["component_type"])
    type_settings = config["component_types"][component_type]
    detector = str(type_settings["detector"])
    reference_pose: Pose
    sample_pose: Pose
    if detector == "edge_template":
        # Match the reference against itself as well.  This removes sub-pixel
        # crop-rounding bias, so an unchanged normal image measures exactly
        # zero displacement instead of occasionally shifting a leg strip by
        # one pixel.
        reference_pose = template_pose(
            reference, reference, geometry, type_settings, px_per_mm,
            config["pose_search"],
        )
        sample_pose = template_pose(
            reference, aligned, geometry, type_settings, px_per_mm,
            config["pose_search"],
        )
    elif detector == "circle_edge":
        margin_mm = float(config["pose_search"].get("margin_mm", 2.0))
        reference_pose = circle_pose(
            reference, geometry, px_per_mm, margin_mm
        )
        sample_pose = circle_pose(
            aligned, geometry, px_per_mm, margin_mm,
            reference_pose.area_px if reference_pose.valid else None,
        )
        if reference_pose.valid:
            reference_pose.score = circle_white_fraction(
                reference, reference_pose.center_px, reference_pose.area_px
            )
        if sample_pose.valid:
            sample_pose.score = circle_white_fraction(
                aligned, sample_pose.center_px, sample_pose.area_px
            )
    else:
        margin_mm = float(config["pose_search"].get("margin_mm", 2.0))
        reference_pose = mask_pose(
            reference, geometry, detector, px_per_mm, margin_mm
        )
        sample_pose = mask_pose(
            aligned, geometry, detector, px_per_mm, margin_mm,
            reference_pose.area_px if reference_pose.valid else None,
        )

    score = sample_pose.score if sample_pose.valid else 0.0
    checks: list[Check] = [_presence_check(score, type_settings, detector)]
    center_delta_px = [0.0, 0.0]
    center_delta_mm = [0.0, 0.0]
    angle_delta = 0.0
    if sample_pose.valid and reference_pose.valid:
        center_delta_px = [
            sample_pose.center_px[0] - reference_pose.center_px[0],
            sample_pose.center_px[1] - reference_pose.center_px[1],
        ]
        center_delta_mm = [
            center_delta_px[0] / px_per_mm[0],
            center_delta_px[1] / px_per_mm[1],
        ]

    if component_type == "HBM":
        pose_trusted = (
            sample_pose.valid
            and score >= float(type_settings.get("presence_pass_score", 0.34))
        )
        hbm_feature_geometry = (
            (
                geometry[0] + center_delta_px[0],
                geometry[1] + center_delta_px[1],
                geometry[2],
                geometry[3],
            )
            if pose_trusted else geometry
        )
        checks[0] = inspect_hbm_presence(
            reference,
            aligned,
            geometry,
            hbm_feature_geometry,
            sample_pose.angle_deg if pose_trusted else 0.0,
            config["white_features"],
            px_per_mm,
        )

    socket = clearance["component_types"][component_type]
    mechanical = list(map(float, socket["center_tolerance_mm"]))
    measurement_margin = float(config["measurement_uncertainty"]["position_mm"])
    extra_position = type_settings.get("position_extra_tolerance_mm", [0.0, 0.0])
    if isinstance(extra_position, (int, float)):
        extra_position = [float(extra_position), float(extra_position)]
    else:
        extra_position = list(map(float, extra_position))
    allowed = [
        mechanical[0] + measurement_margin + extra_position[0],
        mechanical[1] + measurement_margin + extra_position[1],
    ]
    if checks[0].status != "PASS" or not sample_pose.valid or not reference_pose.valid:
        checks.append(Check(
            "position", "NOT_INSPECTABLE", "COMPONENT_POSE_UNAVAILABLE",
            None, {"x_mm": allowed[0], "y_mm": allowed[1]},
        ))
    else:
        position_ok = (
            abs(center_delta_mm[0]) <= allowed[0]
            and abs(center_delta_mm[1]) <= allowed[1]
        )
        checks.append(Check(
            "position",
            "PASS" if position_ok else "FAIL",
            "WITHIN_UNITY_SOCKET_CLEARANCE" if position_ok
            else "OUTSIDE_UNITY_SOCKET_CLEARANCE",
            {
                "delta_x_mm": round(center_delta_mm[0], 4),
                "delta_y_mm": round(center_delta_mm[1], 4),
            },
            {
                "x_mm": round(allowed[0], 4),
                "y_mm": round(allowed[1], 4),
                "mechanical_only_mm": mechanical,
                "vision_margin_mm": measurement_margin,
                "component_extra_margin_mm": extra_position,
            },
        ))

    orientation_mode = str(type_settings["orientation"])
    if orientation_mode == "left_black_mark":
        angle_delta = 0.0
        orientation_limit = None
        if checks[0].status != "PASS":
            orientation_status = "NOT_INSPECTABLE"
            orientation_reason = "COMPONENT_MISSING"
            mark_check = Check(
                "orientation_mark", orientation_status, orientation_reason,
                None, {"expected_side": "left"},
            )
        else:
            mark_check = inspect_inductor_mark(
                aligned, (
                    geometry[0] + center_delta_px[0],
                    geometry[1] + center_delta_px[1],
                    geometry[2], geometry[3],
                ), config["white_features"], sample_pose.area_px,
            )
            orientation_status = mark_check.status
            orientation_reason = mark_check.reason
        checks.append(mark_check)
    elif orientation_mode == "reference_mark":
        mark_settings = dict(type_settings)
        mark_settings["template_scale"] = [0.9, 0.9]
        mark_pose = template_pose(
            reference, aligned, geometry, mark_settings, px_per_mm,
            config["pose_search"],
        )
        angle_delta = mark_pose.angle_deg if mark_pose.valid else 0.0
        orientation_limit = float(type_settings["manual_orientation_tolerance_deg"])
        if not mark_pose.valid or checks[0].status != "PASS":
            orientation_status = "NOT_INSPECTABLE"
            orientation_reason = "ORIENTATION_MARK_UNAVAILABLE"
        elif abs(angle_delta) <= orientation_limit:
            orientation_status = "PASS"
            orientation_reason = "REFERENCE_MARK_DIRECTION_CORRECT"
        else:
            orientation_status = "FAIL"
            orientation_reason = "REFERENCE_MARK_DIRECTION_WRONG"
    else:
        if detector == "edge_template":
            angle_delta = sample_pose.angle_deg if sample_pose.valid else 0.0
        else:
            angle_delta = (
                angle_delta_deg(sample_pose.angle_deg, reference_pose.angle_deg)
                if sample_pose.valid and reference_pose.valid else 0.0
            )
        geometry_limit = geometric_rotation_tolerance_deg(
            socket["part_size_local_mm"], socket["socket_size_local_mm"]
        )
        orientation_limit = geometry_limit + float(
            config["measurement_uncertainty"]["axis_angle_deg"]
        ) + float(type_settings.get("axis_angle_extra_tolerance_deg", 0.0))
        if checks[0].status != "PASS" or not sample_pose.valid:
            orientation_status = "NOT_INSPECTABLE"
            orientation_reason = "COMPONENT_POSE_UNAVAILABLE"
        elif abs(angle_delta) <= orientation_limit:
            orientation_status = "PASS"
            orientation_reason = "LONG_AXIS_DIRECTION_CORRECT"
        else:
            orientation_status = "FAIL"
            orientation_reason = "LONG_AXIS_DIRECTION_WRONG"
    if orientation_mode != "left_black_mark":
        checks.append(Check(
            "orientation_axis", orientation_status, orientation_reason,
            {"delta_deg": round(angle_delta, 3)},
            {
                "absolute_max_deg": round(float(orientation_limit), 3),
                "observability": (
                    "POLARITY_CHECKED_SEPARATELY" if orientation_mode == "lower_left_white_dot"
                    else "MARK_BASED" if orientation_mode == "reference_mark"
                    else "AXIS_ONLY_180_DEG_AMBIGUOUS"
                ),
            },
        ))

    shifted_geometry = (
        geometry[0] + center_delta_px[0],
        geometry[1] + center_delta_px[1],
        geometry[2],
        geometry[3],
    )
    if orientation_mode == "lower_left_white_dot":
        reference_dot_detection = detect_polarity_dot(
            reference,
            geometry,
            reference_pose.angle_deg if reference_pose.valid else 0.0,
            config["white_features"],
            px_per_mm,
        )
        reference_lower_left = [
            candidate
            for candidate in reference_dot_detection["candidates"]
            if candidate["corner"] == "lower_left"
        ]
        reference_dot = max(
            reference_lower_left,
            key=lambda candidate: (
                float(candidate["radius_mm"]),
                float(candidate["circularity"]),
            ),
            default=None,
        )
        reference_anchor_abs_xy = (
            (
                abs(float(reference_dot["normalized_xy"][0])),
                abs(float(reference_dot["normalized_xy"][1])),
            )
            if reference_dot else None
        )
        dot_detection = detect_polarity_dot(
            aligned, shifted_geometry,
            sample_pose.angle_deg if sample_pose.valid else 0.0,
            config["white_features"], px_per_mm,
            reference_anchor_abs_xy,
        )
        corner = dot_detection["corner"]
        corner_scores = dot_detection["corner_scores"]
        dot_min = float(config["white_features"]["dot_min_radius_mm"])
        dot_margin = float(config["white_features"].get(
            "dot_rank_winner_margin_min",
            config["white_features"].get("dot_winner_margin_mm", 0.15),
        ))
        winner_radius = float(dot_detection["radius_mm"])
        winner_margin = float(dot_detection["winner_margin"])
        winner_clear = winner_margin >= dot_margin
        if checks[0].status != "PASS":
            dot_status, dot_reason = "NOT_INSPECTABLE", "COMPONENT_MISSING"
        elif corner == "lower_left" and winner_radius >= dot_min and winner_clear:
            dot_status, dot_reason = "PASS", "WHITE_DOT_AT_LOWER_LEFT"
        elif (
            corner is not None
            and winner_radius >= dot_min
            and winner_clear
        ):
            dot_status, dot_reason = "FAIL", "WHITE_DOT_IN_WRONG_CORNER"
        else:
            dot_status, dot_reason = "RECHECK", "WHITE_DOT_NOT_CLEAR"
        checks.append(Check(
            "polarity_dot", dot_status, dot_reason,
            {
                "detected_corner": corner,
                "corner_radius_mm": {
                    key: round(value, 4) for key, value in corner_scores.items()
                },
                "dot_center_px": dot_detection["center_px"],
                "dot_core_px": dot_detection["core_px"],
                "normalized_xy": dot_detection["normalized_xy"],
                "radius_mm": round(winner_radius, 4),
                "circularity": dot_detection["circularity"],
                "rank_score": dot_detection["rank_score"],
                "winner_margin": round(winner_margin, 4),
                "reference_anchor_abs_xy": (
                    [round(value, 4) for value in reference_anchor_abs_xy]
                    if reference_anchor_abs_xy else None
                ),
                "dot_candidates": dot_detection["candidates"],
            },
            {
                "expected_corner": "lower_left",
                "minimum_radius_mm": dot_min,
                "minimum_rank_winner_margin": dot_margin,
            },
        ))

    leg_sides: list[LegSide] = []
    secondary_required: list[str] = []
    axis_failed = any(
        check.name == "orientation_axis" and check.status == "FAIL"
        for check in checks
    )
    if (
        bool(type_settings.get("inspect_legs", False))
        and checks[0].status == "PASS"
        and not axis_failed
    ):
        leg_settings = config["leg_inspection"][component_type]
        half_width = max(
            7,
            int(round(float(leg_settings["strip_half_width_mm"]) * px_per_mm[0])),
        )
        for side in ("left", "right"):
            reference_rect = _strip_rect(geometry, side, half_width, reference.shape)
            sample_rect = _strip_rect(shifted_geometry, side, half_width, aligned.shape)
            rx0, ry0, rx1, ry1 = reference_rect
            sx0, sy0, sx1, sy1 = sample_rect
            reference_strip = reference[ry0:ry1, rx0:rx1]
            sample_strip = aligned[sy0:sy1, sx0:sx1]
            if reference_strip.size == 0 or sample_strip.size == 0:
                side_result = LegSide(
                    side=side,
                    status="NOT_INSPECTABLE",
                    reason="EMPTY_LEG_VIEW",
                    reference_peaks=0,
                    expected_peaks=int(leg_settings["minimum_reference_peaks"]),
                    missing_indices=[], uncertain_indices=[], fallen_indices=[],
                    lateral_shift_mm=[], strip_px=list(sample_rect), defect_points_px=[],
                )
            else:
                if sample_strip.shape != reference_strip.shape:
                    sample_strip = cv2.resize(
                        sample_strip,
                        (reference_strip.shape[1], reference_strip.shape[0]),
                        interpolation=cv2.INTER_LINEAR,
                    )
                side_result = inspect_leg_side(
                    reference_strip, sample_strip, side, sample_rect,
                    leg_settings, config["white_features"], px_per_mm[0],
                )
            leg_sides.append(side_result)
            checks.append(Check(
                f"white_legs_{side}", side_result.status, side_result.reason,
                {
                    "reference_peaks": side_result.reference_peaks,
                    "missing": side_result.missing_indices,
                    "fallen": side_result.fallen_indices,
                    "profile_shift_px": side_result.profile_shift_px,
                    "profile_alignment_score": (
                        side_result.profile_alignment_score
                    ),
                    "evidence_ratio": side_result.evidence_ratio,
                    "local_peak_shift_px": side_result.local_peak_shift_px,
                },
                {"minimum_visible_peaks": side_result.expected_peaks},
            ))
            if side_result.status == "NOT_INSPECTABLE":
                secondary_required.append(f"white_legs_{side}")
    elif bool(type_settings.get("inspect_legs", False)) and axis_failed:
        for side in ("left", "right"):
            checks.append(Check(
                f"white_legs_{side}", "NOT_INSPECTABLE",
                "COMPONENT_AXIS_OUTSIDE_LEG_VIEW",
                None, {"requires_pose_correction_first": True},
            ))

    visible_status = _aggregate([check.status for check in checks])
    return {
        "slot_id": str(placement["slot_id"]),
        "component_type": component_type,
        "label": _slot_label(str(placement["slot_id"]), component_type),
        "s22_visible_status": visible_status,
        "final_status": "PENDING_D435" if secondary_required and visible_status == "PASS" else visible_status,
        "detector": detector,
        "expected_center_px": [round(geometry[0], 2), round(geometry[1], 2)],
        "detected_center_px": [round(value, 2) for value in sample_pose.center_px],
        "center_delta_mm": [round(value, 4) for value in center_delta_mm],
        "angle_delta_deg": round(angle_delta, 3),
        "checks": [asdict(check) for check in checks],
        "leg_sides": [asdict(side) for side in leg_sides],
        "secondary_required": secondary_required,
        "nominal_box_px": [round(value, 2) for value in geometry],
    }


def apply_projection_and_visibility_policy(
    components: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, list[float]]:
    """Remove repeatable height/parallax bias without relaxing CAD limits.

    The S22 is oblique.  After board-plane rectification, elevated components
    of one type can all move by the same apparent amount when the conveyor stop
    changes by a few pixels.  A robust per-type common offset is camera bias,
    not assembly displacement.  It is subtracted before applying the unchanged
    Unity socket tolerance.  Single-instance GPU remains uncorrected.
    """
    maximum_bias = float(
        config["measurement_uncertainty"].get(
            "common_projection_bias_max_mm", 1.5
        )
    )
    biases: dict[str, list[float]] = {}
    component_types = sorted({item["component_type"] for item in components})
    for component_type in component_types:
        typed = [item for item in components if item["component_type"] == component_type]
        if len(typed) < 2 or component_type == "VRM":
            biases[component_type] = [0.0, 0.0]
            continue
        candidates = []
        for item in typed:
            presence = next(
                check for check in item["checks"] if check["name"] == "presence"
            )
            raw_norm = float(np.linalg.norm(
                np.asarray(item["center_delta_mm"], dtype=np.float32)
            ))
            if (
                presence["status"] == "PASS"
                and raw_norm <= maximum_bias
            ):
                candidates.append(item["center_delta_mm"])
        if len(candidates) < 2:
            biases[component_type] = [0.0, 0.0]
            continue
        array = np.asarray(candidates, dtype=np.float32)
        bias = np.median(array, axis=0)
        if float(np.linalg.norm(bias)) > maximum_bias:
            biases[component_type] = [0.0, 0.0]
        else:
            biases[component_type] = [float(bias[0]), float(bias[1])]

    for item in components:
        component_type = item["component_type"]
        bias = biases[component_type]
        raw = list(map(float, item["center_delta_mm"]))
        corrected = [raw[0] - bias[0], raw[1] - bias[1]]
        item["projection_common_bias_mm"] = [round(value, 4) for value in bias]
        item["corrected_center_delta_mm"] = [
            round(value, 4) for value in corrected
        ]
        position = next(
            check for check in item["checks"] if check["name"] == "position"
        )
        presence = next(
            check for check in item["checks"] if check["name"] == "presence"
        )
        if component_type == "VRM" and presence["status"] == "PASS":
            presence["status"] = "NOT_INSPECTABLE"
            presence["reason"] = "D435_REQUIRED_FOR_BLACK_ON_BLACK_PRESENCE"
            position["status"] = "NOT_INSPECTABLE"
            position["reason"] = "D435_REQUIRED_FOR_BLACK_ON_BLACK_SUB_MM_POSITION"
            position["measured"] = {
                "raw_s22_delta_mm": [round(value, 4) for value in raw]
            }
            if "presence_position_and_orientation" not in item["secondary_required"]:
                item["secondary_required"].append(
                    "presence_position_and_orientation"
                )
            for check in item["checks"]:
                if check["name"] == "orientation_axis":
                    check["status"] = "NOT_INSPECTABLE"
                    check["reason"] = "D435_REQUIRED_FOR_BLACK_ON_BLACK_ORIENTATION"
            item["angle_delta_deg"] = 0.0
        elif position["status"] != "NOT_INSPECTABLE" and presence["status"] == "PASS":
            allowed_x = float(position["limit"]["x_mm"])
            allowed_y = float(position["limit"]["y_mm"])
            position_ok = (
                abs(corrected[0]) <= allowed_x
                and abs(corrected[1]) <= allowed_y
            )
            position["status"] = "PASS" if position_ok else "FAIL"
            position["reason"] = (
                "WITHIN_UNITY_SOCKET_CLEARANCE" if position_ok
                else "OUTSIDE_UNITY_SOCKET_CLEARANCE"
            )
            position["measured"] = {
                "raw_delta_mm": [round(value, 4) for value in raw],
                "common_projection_bias_mm": [round(value, 4) for value in bias],
                "corrected_delta_x_mm": round(corrected[0], 4),
                "corrected_delta_y_mm": round(corrected[1], 4),
            }
        item["s22_visible_status"] = _aggregate(
            [check["status"] for check in item["checks"]]
        )
        item["final_status"] = (
            "PENDING_D435"
            if item["secondary_required"] and item["s22_visible_status"] == "PASS"
            else item["s22_visible_status"]
        )
    return {
        key: [round(value, 4) for value in values]
        for key, values in biases.items()
    }


def board_alignment_mask(
    layout: dict[str, Any],
    image_shape: tuple[int, ...],
    board_size_mm: tuple[float, float],
    mapping: dict[str, Any],
    exclusion_margin_mm: float,
) -> np.ndarray:
    """Keep invariant PCB/fixture texture and exclude all movable parts."""
    mask = np.full(image_shape[:2], 255, dtype=np.uint8)
    px_per_mm = (
        image_shape[1] / board_size_mm[0],
        image_shape[0] / board_size_mm[1],
    )
    for placement in layout["placements"]:
        center_x, center_y, size_x, size_y = slot_geometry(
            placement, image_shape, board_size_mm, mapping
        )
        x0, y0, x1, y1 = _bounded_rect(
            center_x,
            center_y,
            size_x + 2.0 * exclusion_margin_mm * px_per_mm[0],
            size_y + 2.0 * exclusion_margin_mm * px_per_mm[1],
            image_shape,
        )
        mask[y0:y1, x0:x1] = 0
    return mask


def inspect(
    reference: np.ndarray,
    image: np.ndarray,
    config: dict[str, Any],
    layout: dict[str, Any],
    clearance: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    board = layout["board"]["size_mm"]
    board_size_mm = (float(board["x"]), float(board["y"]))
    if len(layout["placements"]) != 25:
        raise RuntimeError(
            f"Expected 25 Unity placements, found {len(layout['placements'])}"
        )
    alignment_mask = board_alignment_mask(
        layout,
        reference.shape,
        board_size_mm,
        config["coordinate_mapping"],
        float(config["global_alignment"].get(
            "component_exclusion_margin_mm", 2.5
        )),
    )
    aligned, alignment_score, warp, alignment_reason = align_board(
        reference, image, config["global_alignment"], alignment_mask
    )
    alignment_valid = (
        alignment_reason == "OK"
        and alignment_score >= float(config["global_alignment"]["minimum_score"])
    )
    px_per_mm = (
        reference.shape[1] / board_size_mm[0],
        reference.shape[0] / board_size_mm[1],
    )
    components: list[dict[str, Any]] = []
    for placement in layout["placements"]:
        geometry = slot_geometry(
            placement, reference.shape, board_size_mm, config["coordinate_mapping"]
        )
        component = inspect_component(
            placement, reference, aligned, geometry, config, clearance, px_per_mm
        )
        if not alignment_valid:
            component["s22_visible_status"] = "RECHECK"
            component["final_status"] = "RECHECK"
            component["alignment_override"] = "BOARD_ALIGNMENT_UNCERTAIN"
        components.append(component)

    projection_biases = apply_projection_and_visibility_policy(components, config)

    s22_status = _aggregate(
        [component["s22_visible_status"] for component in components]
    )
    if not alignment_valid:
        s22_status = "RECHECK"
    d435_required = [
        f"{component['slot_id']}:{item}"
        for component in components
        for item in component["secondary_required"]
    ]
    if s22_status == "FAIL":
        final_status = "FAIL"
    elif s22_status == "RECHECK":
        final_status = "RECHECK"
    elif d435_required:
        final_status = "PENDING_D435"
    else:
        final_status = "PASS"

    expected_counts = dict(layout["expected_robot_part_counts"])
    count_summary: dict[str, dict[str, int]] = {}
    for component_type, expected in expected_counts.items():
        typed = [item for item in components if item["component_type"] == component_type]
        presence_statuses = [
            next(
                check for check in item["checks"]
                if check["name"] == "presence"
            )["status"]
            for item in typed
        ]
        confirmed_present = sum(status == "PASS" for status in presence_statuses)
        confirmed_missing = sum(status == "FAIL" for status in presence_statuses)
        uncertain = len(presence_statuses) - confirmed_present - confirmed_missing
        passed = sum(item["s22_visible_status"] == "PASS" for item in typed)
        count_summary[component_type] = {
            "expected": int(expected),
            "confirmed_present": int(confirmed_present),
            "confirmed_missing": int(confirmed_missing),
            "uncertain": int(uncertain),
            "present_or_uncertain": int(confirmed_present + uncertain),
            "s22_pass": int(passed),
        }

    failures = [
        f"{component['slot_id']}:{check['name']}:{check['reason']}"
        for component in components
        for check in component["checks"]
        if check["status"] == "FAIL"
    ]
    rechecks = [
        f"{component['slot_id']}:{check['name']}:{check['reason']}"
        for component in components
        for check in component["checks"]
        if check["status"] == "RECHECK"
    ]
    report = {
        "schema_version": 2,
        "status": final_status,
        "s22_visible_status": s22_status,
        "final_status": final_status,
        "inspection_scope": [
            "ALL_25_COMPONENTS_PRESENCE",
            "UNITY_SOCKET_POSITION_TOLERANCE",
            "ALL_COMPONENT_LONG_AXIS_OR_MARK_DIRECTION",
            "GPU_HBM_LOWER_LEFT_POLARITY_DOT",
            "GPU_HBM_VISIBLE_WHITE_LEG_PRESENCE_AND_FALLEN_LEG",
        ],
        "decision_policy": {
            "printed_shape_variation": "ALLOWED",
            "white_leg_blob_size_variation": "ALLOWED",
            "white_leg_missing_or_laterally_fallen": "FAIL",
            "hidden_side": "D435_REQUIRED_NOT_S22_RECHECK",
            "vrm_black_on_black_presence_pose": "D435_REQUIRED_NOT_S22_PASS",
            "axis_only_180_degree_flip": "NOT_OBSERVABLE_WITHOUT_A_POLARITY_MARK",
        },
        "alignment": {
            "status": alignment_reason,
            "score": alignment_score,
            "warp_reference_from_input": warp.astype(float).tolist(),
        },
        "pixel_scale": {"x_px_per_mm": px_per_mm[0], "y_px_per_mm": px_per_mm[1]},
        "projection_common_bias_mm": projection_biases,
        "counts": count_summary,
        "components": components,
        "d435_required": d435_required,
        "failures": failures,
        "rechecks": rechecks,
    }
    return report, draw_debug(aligned, report)


def _feature_point(
    center: list[float], size: tuple[float, float], feature: str,
) -> tuple[int, int]:
    horizontal = {
        "upper_left": -1.0, "lower_left": -1.0,
        "upper_right": 1.0, "lower_right": 1.0,
        "left": -1.0, "right": 1.0,
    }.get(feature, 0.0)
    vertical = {
        "upper_left": -1.0, "upper_right": -1.0,
        "lower_left": 1.0, "lower_right": 1.0,
    }.get(feature, 0.0)
    return (
        int(round(float(center[0]) + horizontal * size[0] * 0.34)),
        int(round(float(center[1]) + vertical * size[1] * 0.34)),
    )


def _draw_badge(
    canvas: np.ndarray,
    text: str,
    anchor: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.35
    text_size, baseline = cv2.getTextSize(text, font, scale, 1)
    x = max(3, min(canvas.shape[1] - text_size[0] - 7, anchor[0]))
    y = max(text_size[1] + 4, min(canvas.shape[0] - baseline - 3, anchor[1]))
    cv2.rectangle(
        canvas,
        (x - 3, y - text_size[1] - 3),
        (x + text_size[0] + 3, y + baseline + 2),
        (17, 20, 24), -1,
    )
    cv2.putText(canvas, text, (x, y), font, scale, color, 1, cv2.LINE_AA)


def draw_debug(image: np.ndarray, report: dict[str, Any]) -> np.ndarray:
    canvas = image.copy()
    for component in report["components"]:
        center_x, center_y, size_x, size_y = component["nominal_box_px"]
        x0, y0, x1, y1 = _bounded_rect(
            center_x, center_y, size_x, size_y, canvas.shape
        )
        status = component["final_status"]
        color = STATUS_COLORS[status]
        type_color = TYPE_COLORS[component["component_type"]]
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, 2, cv2.LINE_AA)
        detected = tuple(int(round(value)) for value in component["detected_center_px"])
        cv2.drawMarker(
            canvas, detected, type_color, cv2.MARKER_CROSS, 12, 2, cv2.LINE_AA
        )
        checks = {check["name"]: check for check in component["checks"]}
        failed_names = {
            name for name, check in checks.items() if check["status"] == "FAIL"
        }
        direction_names = {"orientation_axis", "orientation_mark", "polarity_dot"}
        tags: list[str] = []
        if "presence" in failed_names:
            tags.append("MISS")
        else:
            if "position" in failed_names:
                tags.append("POS")
            if failed_names & direction_names:
                tags.append("DIR")
            if failed_names & {"white_legs_left", "white_legs_right"}:
                tags.append("LEG")
        status_letter = {
            "PASS": "P", "FAIL": "F", "RECHECK": "R",
            "PENDING_D435": "D", "NOT_INSPECTABLE": "D",
        }.get(status, "?")
        label = (
            f"{component['label']} {'+'.join(tags)}"
            if tags else f"{component['label']} {status_letter}"
        )
        text_size, baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1
        )
        label_x = max(2, min(canvas.shape[1] - text_size[0] - 7, x0 + 2))
        label_y = max(text_size[1] + 5, y0 - 4)
        cv2.rectangle(
            canvas,
            (label_x - 3, label_y - text_size[1] - 3),
            (label_x + text_size[0] + 3, label_y + baseline + 2),
            (17, 20, 24), -1,
        )
        cv2.putText(
            canvas, label, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX,
            0.38, color, 1, cv2.LINE_AA,
        )

        polarity = checks.get("polarity_dot")
        if polarity and polarity["status"] == "FAIL":
            measured = polarity.get("measured") or {}
            limit = polarity.get("limit") or {}
            actual_corner = measured.get("detected_corner")
            expected_corner = limit.get("expected_corner", "lower_left")
            if actual_corner:
                box_size = (float(size_x), float(size_y))
                detected_dot = measured.get("dot_center_px")
                actual_point = (
                    tuple(int(round(value)) for value in detected_dot)
                    if detected_dot else _feature_point(
                        component["detected_center_px"], box_size, actual_corner
                    )
                )
                expected_point = _feature_point(
                    component["detected_center_px"], box_size, expected_corner
                )
                cv2.circle(
                    canvas, actual_point, 7, STATUS_COLORS["FAIL"], 2, cv2.LINE_AA
                )
                cv2.rectangle(
                    canvas,
                    (expected_point[0] - 6, expected_point[1] - 6),
                    (expected_point[0] + 6, expected_point[1] + 6),
                    STATUS_COLORS["PASS"], 2, cv2.LINE_AA,
                )
                cv2.arrowedLine(
                    canvas, actual_point, expected_point, STATUS_COLORS["FAIL"],
                    2, cv2.LINE_AA, tipLength=0.16,
                )
                abbreviations = {
                    "upper_left": "UL", "upper_right": "UR",
                    "lower_left": "LL", "lower_right": "LR",
                }
                _draw_badge(
                    canvas,
                    f"DOT {abbreviations.get(actual_corner, '?')}"
                    f">{abbreviations.get(expected_corner, '?')}",
                    (x0 + 4, y1 - 5), STATUS_COLORS["FAIL"],
                )

        mark = checks.get("orientation_mark")
        if mark and mark["status"] == "FAIL":
            measured = mark.get("measured") or {}
            actual_side = measured.get("detected_side")
            expected_side = (mark.get("limit") or {}).get("expected_side", "left")
            if actual_side in ("left", "right"):
                box_size = (float(size_x), float(size_y))
                mark_point = measured.get("mark_point_px")
                actual_point = (
                    tuple(int(round(value)) for value in mark_point)
                    if mark_point else _feature_point(
                        component["detected_center_px"], box_size, actual_side
                    )
                )
                expected_point = _feature_point(
                    component["detected_center_px"], box_size, expected_side
                )
                cv2.circle(
                    canvas, actual_point, 7, STATUS_COLORS["FAIL"], 2, cv2.LINE_AA
                )
                cv2.rectangle(
                    canvas,
                    (expected_point[0] - 6, expected_point[1] - 6),
                    (expected_point[0] + 6, expected_point[1] + 6),
                    STATUS_COLORS["PASS"], 2, cv2.LINE_AA,
                )
                cv2.arrowedLine(
                    canvas, actual_point, expected_point, STATUS_COLORS["FAIL"],
                    2, cv2.LINE_AA, tipLength=0.18,
                )
                _draw_badge(
                    canvas,
                    f"MARK {float(measured.get('mark_angle_deg', 0.0)):+.0f}deg",
                    (x0 + 4, y1 - 5), STATUS_COLORS["FAIL"],
                )

        axis = checks.get("orientation_axis")
        if (
            axis and axis["status"] == "FAIL"
            and not (polarity and polarity["status"] == "FAIL")
        ):
            delta = float((axis.get("measured") or {}).get("delta_deg", 0.0))
            _draw_badge(
                canvas, f"ROT {delta:+.1f}deg", (x0 + 4, y1 - 5),
                STATUS_COLORS["FAIL"],
            )

        for side in component["leg_sides"]:
            side_color = STATUS_COLORS[side["status"]]
            sx0, sy0, sx1, sy1 = side["strip_px"]
            edge_x = int(round((sx0 + sx1) * 0.5))
            cv2.line(canvas, (edge_x, sy0), (edge_x, sy1), side_color, 1, cv2.LINE_AA)
            for point in side["defect_points_px"]:
                cv2.circle(canvas, tuple(point), 8, STATUS_COLORS["FAIL"], 2, cv2.LINE_AA)

    hud_height = 126
    output = np.full(
        (canvas.shape[0] + hud_height, canvas.shape[1], 3),
        (17, 20, 24), dtype=np.uint8,
    )
    output[hud_height:] = canvas
    s22 = report["s22_visible_status"]
    final = report["final_status"]
    cv2.putText(
        output, f"FULL PCB INSPECTION | S22 {s22} | FINAL {final}",
        (24, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.82,
        STATUS_COLORS.get(final, STATUS_COLORS[s22]), 2, cv2.LINE_AA,
    )
    pieces = []
    for name in ("GPU", "HBM", "Power Module", "VRM", "Inductor", "SMD Capacitor"):
        item = report["counts"][name]
        if item["uncertain"]:
            count_text = (
                f"{item['confirmed_present']}/{item['expected']}"
                f" ?{item['uncertain']}"
            )
        else:
            count_text = f"{item['confirmed_present']}/{item['expected']}"
        pieces.append(f"{TYPE_LABELS[name]} {count_text}")
    cv2.putText(
        output, "   ".join(pieces), (24, 76), cv2.FONT_HERSHEY_SIMPLEX,
        0.58, (224, 229, 235), 1, cv2.LINE_AA,
    )
    summary = (
        f"FAIL {len(report['failures'])}   RECHECK {len(report['rechecks'])}   "
        f"D435 REQUIRED {len(report['d435_required'])}   "
        f"BOARD ALIGN {report['alignment']['score']:.3f}"
    )
    cv2.putText(
        output, summary, (24, 105), cv2.FONT_HERSHEY_SIMPLEX,
        0.51, (154, 164, 176), 1, cv2.LINE_AA,
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--set-reference", type=Path,
        help="store a verified normal rectified board image as the golden reference",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict-exit", action="store_true")
    args = parser.parse_args()

    config = _load_json(args.config.expanduser().resolve())
    reference_path = (
        args.reference.expanduser().resolve()
        if args.reference else _project_path(config["reference_image"])
    )
    if args.set_reference:
        saved = set_reference(args.set_reference.expanduser().resolve(), reference_path)
        print(f"Golden full-board reference saved: {saved}")
        return
    if not reference_path.is_file():
        raise RuntimeError(
            f"Golden reference is missing: {reference_path}\n"
            "Run once with --set-reference <verified-normal-rectified-ROI>."
        )

    image_path = args.image.expanduser().resolve()
    reference = _load_image(reference_path)
    image = _load_image(image_path)
    layout = _load_json(_project_path(config["board_layout"]))
    physical_board_path = _project_path(config["physical_board"])
    physical_board = _load_json(physical_board_path)
    layout, physical_override_slots = apply_component_slot_overrides(
        layout, physical_board
    )
    clearance = _load_json(_project_path(config["socket_clearance"]))
    report, debug = inspect(reference, image, config, layout, clearance)
    report["created_at"] = datetime.now().astimezone().isoformat()
    report["input_image"] = str(image_path)
    report["reference_image"] = str(reference_path)
    report["config"] = str(args.config.expanduser().resolve())
    report["physical_board"] = str(physical_board_path)
    report["physical_override_slots"] = physical_override_slots

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_path = output_dir / f"full_board_inspection_{timestamp}.png"
    report_path = output_dir / f"full_board_inspection_{timestamp}.json"
    if not cv2.imwrite(str(debug_path), debug, (cv2.IMWRITE_PNG_COMPRESSION, 2)):
        raise RuntimeError(f"Could not save debug image: {debug_path}")
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _atomic_symlink(debug_path, output_dir / "full_board_inspection_latest.png")
    _atomic_symlink(report_path, output_dir / "full_board_inspection_latest.json")
    print(f"S22 visible status: {report['s22_visible_status']}")
    print(f"Final status: {report['final_status']}")
    print(f"Debug image: {debug_path}")
    print(f"JSON report: {report_path}")
    if report["failures"]:
        print("Failures: " + ", ".join(report["failures"]))
    if report["rechecks"]:
        print("Rechecks: " + ", ".join(report["rechecks"]))
    if report["d435_required"]:
        print("D435 required: " + ", ".join(report["d435_required"]))

    if args.strict_exit:
        if report["final_status"] == "FAIL":
            sys.exit(3)
        if report["final_status"] in ("RECHECK", "PENDING_D435"):
            sys.exit(2)


if __name__ == "__main__":
    main()
