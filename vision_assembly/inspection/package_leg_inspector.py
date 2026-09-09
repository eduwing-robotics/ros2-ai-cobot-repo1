#!/usr/bin/env python3
"""Inspect visible GPU/HBM white package legs in a rectified S22 image.

The board-plane homography removes the PCB perspective, but it cannot recover
component sidewalls hidden by parallax.  This inspector therefore compares
each left/right leg row with the corresponding row in a golden image.  A side
that was not sufficiently visible in the golden image is explicitly routed to
a D435 recheck instead of being guessed as PASS.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/package_leg_inspection.json"
DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "runtime/inspection/package_legs"

STATUS_COLORS = {
    "PASS": (72, 220, 118),
    "RECHECK": (35, 190, 255),
    "FAIL": (65, 72, 245),
}


@dataclass
class SideResult:
    side: str
    status: str
    reason: str
    reference_peaks: int
    minimum_reference_peaks: int
    profile_correlation: float
    profile_deficit: float
    missing_indices: list[int]
    weak_indices: list[int]
    illumination_scale: float
    strip_px: list[int]
    missing_points_px: list[list[int]]


@dataclass
class ComponentResult:
    slot_id: str
    component_type: str
    status: str
    local_match_score: float
    local_offset_px: list[int]
    center_px: list[int]
    sides: list[SideResult]


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


def _status_for(items: list[str]) -> str:
    if "FAIL" in items:
        return "FAIL"
    if "RECHECK" in items:
        return "RECHECK"
    return "PASS"


def slot_geometry(
    placement: dict[str, Any],
    image_shape: tuple[int, ...],
    board_size_mm: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Return expected component centre and nominal size in canonical pixels."""
    height, width = image_shape[:2]
    board_width, board_height = board_size_mm
    center = placement["center_board_mm"]
    size = placement["nominal_size_mm"]
    center_x = (float(center["x"]) / board_width + 0.5) * width
    center_y = (float(center["y"]) / board_height + 0.5) * height
    size_x = float(size["x"]) / board_width * width
    size_y = float(size["y"]) / board_height * height
    return center_x, center_y, size_x, size_y


def _gray_float(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32) / 255.0


def align_board(
    reference: np.ndarray,
    image: np.ndarray,
    settings: dict[str, Any],
    input_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, float, np.ndarray, str]:
    """Affinely register two already perspective-rectified board images."""
    if image.shape[:2] != reference.shape[:2]:
        image = cv2.resize(
            image,
            (reference.shape[1], reference.shape[0]),
            interpolation=cv2.INTER_LANCZOS4,
        )

    scale = float(settings.get("downscale", 0.35))
    reference_small = cv2.resize(
        _gray_float(reference), None, fx=scale, fy=scale,
        interpolation=cv2.INTER_AREA,
    )
    image_small = cv2.resize(
        _gray_float(image), None, fx=scale, fy=scale,
        interpolation=cv2.INTER_AREA,
    )
    reference_small = cv2.GaussianBlur(reference_small, (5, 5), 0.9)
    image_small = cv2.GaussianBlur(image_small, (5, 5), 0.9)
    mask_small = None
    if input_mask is not None:
        if input_mask.shape[:2] != reference.shape[:2]:
            raise ValueError("Alignment mask must match the reference image")
        mask_small = cv2.resize(
            input_mask.astype(np.uint8),
            (reference_small.shape[1], reference_small.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
    warp = np.eye(2, 3, dtype=np.float32)
    criteria = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
        int(settings.get("iterations", 90)),
        float(settings.get("epsilon", 1.0e-5)),
    )
    try:
        score, warp = cv2.findTransformECC(
            reference_small,
            image_small,
            warp,
            cv2.MOTION_AFFINE,
            criteria,
            mask_small,
            int(settings.get("gaussian_filter_size", 3)),
        )
    except cv2.error:
        return image.copy(), 0.0, np.eye(2, 3, dtype=np.float32), "ECC_FAILED"

    warp[:, 2] /= scale
    linear = warp[:, :2]
    determinant = float(np.linalg.det(linear))
    translation = float(np.linalg.norm(warp[:, 2]))
    max_translation = float(settings.get("max_translation_px", 45.0))
    determinant_range = settings.get("determinant_range", [0.94, 1.06])
    valid = (
        float(determinant_range[0]) <= determinant <= float(determinant_range[1])
        and translation <= max_translation
    )
    if not valid:
        return image.copy(), float(score), warp, "ALIGNMENT_OUT_OF_RANGE"

    aligned = cv2.warpAffine(
        image,
        warp,
        (reference.shape[1], reference.shape[0]),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return aligned, float(score), warp, "OK"


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


def local_component_offset(
    reference_gray: np.ndarray,
    image_gray: np.ndarray,
    geometry: tuple[float, float, float, float],
    settings: dict[str, Any],
) -> tuple[int, int, float]:
    """Find small residual translation using the package body, not its legs."""
    center_x, center_y, size_x, size_y = geometry
    body_width = size_x * float(settings.get("body_width_fraction", 0.62))
    body_height = size_y * float(settings.get("body_height_fraction", 0.72))
    x0, y0, x1, y1 = _bounded_rect(
        center_x, center_y, body_width, body_height, reference_gray.shape
    )
    template = reference_gray[y0:y1, x0:x1]
    margin = max(2, int(settings.get("local_search_px", 18)))
    sx0 = max(0, x0 - margin)
    sy0 = max(0, y0 - margin)
    sx1 = min(image_gray.shape[1], x1 + margin)
    sy1 = min(image_gray.shape[0], y1 + margin)
    search = image_gray[sy0:sy1, sx0:sx1]
    if (
        template.size == 0
        or search.shape[0] < template.shape[0]
        or search.shape[1] < template.shape[1]
    ):
        return 0, 0, 0.0
    scores = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, maximum, _, location = cv2.minMaxLoc(scores)
    target_x = sx0 + int(location[0])
    target_y = sy0 + int(location[1])
    return target_x - x0, target_y - y0, float(maximum)


def white_leg_mask(image: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (
        (lab[:, :, 0] >= int(settings.get("lab_l_min", 110)))
        & (hsv[:, :, 1] <= int(settings.get("hsv_s_max", 160)))
    ).astype(np.uint8)
    kernel_size = max(1, int(settings.get("open_kernel_px", 2)))
    if kernel_size > 1:
        kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def leg_profile(image: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    mask = white_leg_mask(image, settings)
    profile = mask.mean(axis=1).astype(np.float32)
    sigma = float(settings.get("profile_sigma_px", 1.2))
    kernel = max(3, int(round(sigma * 5.0)) | 1)
    return cv2.GaussianBlur(
        profile.reshape(-1, 1), (1, kernel), sigma
    ).reshape(-1)


def reference_peaks(
    profile: np.ndarray,
    side: str,
    settings: dict[str, Any],
) -> list[int]:
    """Find periodic visible leg centres in one golden-image side row."""
    signal = profile.copy()
    length = len(signal)
    signal[: max(2, int(round(length * 0.015)))] = 0.0
    signal[int(round(length * 0.96)) :] = 0.0
    # The large polarity dot is located at the lower-left package corner.
    if side == "left":
        signal[int(round(length * float(settings.get("left_keep_fraction", 0.90)))) :] = 0.0

    threshold = float(settings.get("peak_profile_min", 0.025))
    candidates = [
        index
        for index in range(1, length - 1)
        if signal[index] >= signal[index - 1]
        and signal[index] >= signal[index + 1]
        and signal[index] >= threshold
    ]
    minimum_distance = max(2, int(settings.get("peak_min_distance_px", 9)))
    selected: list[int] = []
    for index in sorted(candidates, key=lambda item: signal[item], reverse=True):
        if all(abs(index - previous) >= minimum_distance for previous in selected):
            selected.append(index)
    maximum = int(settings.get("maximum_reference_peaks", 0))
    if maximum > 0:
        selected = selected[:maximum]
    return sorted(selected)


def _profile_correlation(reference: np.ndarray, sample: np.ndarray) -> float:
    if reference.std() < 1.0e-6 or sample.std() < 1.0e-6:
        return 0.0
    return float(np.clip(np.corrcoef(reference, sample)[0, 1], -1.0, 1.0))


def inspect_side(
    reference_strip: np.ndarray,
    image_strip: np.ndarray,
    side: str,
    strip_rect: tuple[int, int, int, int],
    type_settings: dict[str, Any],
    white_settings: dict[str, Any],
    local_match_score: float,
) -> SideResult:
    reference_profile = leg_profile(reference_strip, white_settings)
    image_profile = leg_profile(image_strip, white_settings)
    peaks = reference_peaks(reference_profile, side, type_settings)
    minimum_peaks = int(type_settings["minimum_reference_peaks"])
    base = {
        "side": side,
        "reference_peaks": len(peaks),
        "minimum_reference_peaks": minimum_peaks,
        "strip_px": list(strip_rect),
    }

    if len(peaks) < minimum_peaks:
        return SideResult(
            **base,
            status="RECHECK",
            reason="REFERENCE_SIDE_NOT_VISIBLE",
            profile_correlation=0.0,
            profile_deficit=1.0,
            missing_indices=[],
            weak_indices=[],
            illumination_scale=1.0,
            missing_points_px=[],
        )

    if local_match_score < float(type_settings.get("minimum_local_match", 0.58)):
        return SideResult(
            **base,
            status="RECHECK",
            reason="LOCAL_ALIGNMENT_UNCERTAIN",
            profile_correlation=0.0,
            profile_deficit=1.0,
            missing_indices=[],
            weak_indices=[],
            illumination_scale=1.0,
            missing_points_px=[],
        )

    reference_values = []
    image_values = []
    reference_radius = int(type_settings.get("reference_peak_radius_px", 2))
    sample_radius = int(type_settings.get("sample_peak_radius_px", 4))
    for peak in peaks:
        reference_values.append(
            float(reference_profile[max(0, peak - reference_radius):
                                    peak + reference_radius + 1].max())
        )
        image_values.append(
            float(image_profile[max(0, peak - sample_radius):
                                peak + sample_radius + 1].max())
        )

    reference_values_array = np.asarray(reference_values, dtype=np.float32)
    image_values_array = np.asarray(image_values, dtype=np.float32)
    raw_ratios = image_values_array / np.maximum(reference_values_array, 1.0e-6)
    usable = raw_ratios[
        (raw_ratios >= float(type_settings.get("illumination_ratio_min", 0.35)))
        & (raw_ratios <= float(type_settings.get("illumination_ratio_max", 2.5)))
    ]
    illumination_scale = float(np.median(usable)) if usable.size else 1.0
    illumination_scale = float(np.clip(illumination_scale, 0.60, 1.60))
    normalized_profile = image_profile / illumination_scale
    ratios = raw_ratios / illumination_scale

    missing_threshold = float(type_settings.get("missing_peak_ratio", 0.38))
    weak_threshold = float(type_settings.get("weak_peak_ratio", 0.67))
    missing = [int(index + 1) for index, ratio in enumerate(ratios)
               if ratio < missing_threshold]
    weak = [int(index + 1) for index, ratio in enumerate(ratios)
            if missing_threshold <= ratio < weak_threshold]

    correlation = _profile_correlation(reference_profile, normalized_profile)
    deficit = float(
        np.maximum(reference_profile - normalized_profile, 0.0).sum()
        / max(float(reference_profile.sum()), 1.0e-6)
    )

    # A missing expected peak is direct evidence and may produce FAIL. A low
    # whole-row correlation alone is not direct evidence because elevated
    # packages change their apparent sidewall shape as the board moves under
    # an oblique camera. Route that case to the second D435 view instead.
    fail = len(missing) >= int(type_settings.get("fail_missing_count", 1))
    uncertain = (
        len(weak) > int(type_settings.get("maximum_weak_pass", 2))
        or correlation < float(type_settings.get("pass_profile_correlation", 0.78))
        or deficit > float(type_settings.get("pass_profile_deficit", 0.25))
    )
    if fail:
        status = "FAIL"
        reason = "LEG_PATTERN_DEFECT"
    elif uncertain:
        status = "RECHECK"
        reason = "LEG_PATTERN_UNCERTAIN"
    else:
        status = "PASS"
        reason = "VISIBLE_LEGS_MATCH"

    x0, y0, x1, _ = strip_rect
    center_x = int(round((x0 + x1) * 0.5))
    missing_points = [
        [center_x, int(y0 + peaks[index - 1])]
        for index in missing
    ]
    return SideResult(
        **base,
        status=status,
        reason=reason,
        profile_correlation=correlation,
        profile_deficit=deficit,
        missing_indices=missing,
        weak_indices=weak,
        illumination_scale=illumination_scale,
        missing_points_px=missing_points,
    )


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


def inspect(
    reference: np.ndarray,
    image: np.ndarray,
    config: dict[str, Any],
    layout: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    board_size = layout["board"]["size_mm"]
    board_size_mm = (float(board_size["x"]), float(board_size["y"]))
    aligned, alignment_score, warp, alignment_reason = align_board(
        reference, image, config["global_alignment"]
    )
    alignment_valid = (
        alignment_reason == "OK"
        and alignment_score >= float(
            config["global_alignment"].get("minimum_score", 0.88)
        )
    )
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    aligned_gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)

    placements = [
        placement for placement in layout["placements"]
        if placement["component_type"] in ("GPU", "HBM")
    ]
    component_results: list[ComponentResult] = []
    for placement in placements:
        component_type = placement["component_type"]
        settings = config["component_types"][component_type]
        geometry = slot_geometry(placement, reference.shape, board_size_mm)
        offset_x, offset_y, local_score = local_component_offset(
            reference_gray, aligned_gray, geometry, settings
        )
        shifted_geometry = (
            geometry[0] + offset_x,
            geometry[1] + offset_y,
            geometry[2],
            geometry[3],
        )
        scale_x = reference.shape[1] / board_size_mm[0]
        half_width = max(
            8,
            int(round(float(settings["strip_half_width_mm"]) * scale_x)),
        )
        sides: list[SideResult] = []
        for side in ("left", "right"):
            reference_rect = _strip_rect(
                geometry, side, half_width, reference.shape
            )
            image_rect = _strip_rect(
                shifted_geometry, side, half_width, aligned.shape
            )
            rx0, ry0, rx1, ry1 = reference_rect
            ix0, iy0, ix1, iy1 = image_rect
            reference_strip = reference[ry0:ry1, rx0:rx1]
            image_strip = aligned[iy0:iy1, ix0:ix1]
            if image_strip.shape != reference_strip.shape:
                image_strip = cv2.resize(
                    image_strip,
                    (reference_strip.shape[1], reference_strip.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                )
            result = inspect_side(
                reference_strip,
                image_strip,
                side,
                image_rect,
                settings,
                config["white_segmentation"],
                local_score,
            )
            sides.append(result)

        if not alignment_valid:
            for side in sides:
                side.status = "RECHECK"
                side.reason = "BOARD_ALIGNMENT_UNCERTAIN"
                side.missing_points_px = []
            component_status = "RECHECK"
        else:
            component_status = _status_for([side.status for side in sides])
        component_results.append(
            ComponentResult(
                slot_id=str(placement["slot_id"]),
                component_type=component_type,
                status=component_status,
                local_match_score=local_score,
                local_offset_px=[offset_x, offset_y],
                center_px=[
                    int(round(shifted_geometry[0])),
                    int(round(shifted_geometry[1])),
                ],
                sides=sides,
            )
        )

    overall = _status_for([item.status for item in component_results])
    if not alignment_valid:
        overall = "RECHECK"

    report = {
        "schema_version": 1,
        "status": overall,
        "inspection_scope": ["GPU_WHITE_LEGS", "HBM_WHITE_LEGS"],
        "alignment": {
            "status": alignment_reason,
            "score": alignment_score,
            "warp_reference_from_input": warp.astype(float).tolist(),
        },
        "components": [asdict(item) for item in component_results],
        "d435_recheck": [
            f"{item.slot_id}:{side.side}"
            for item in component_results
            for side in item.sides
            if side.status == "RECHECK"
        ],
        "failures": [
            f"{item.slot_id}:{side.side}:{side.reason}"
            for item in component_results
            for side in item.sides
            if side.status == "FAIL"
        ],
    }
    debug = draw_debug(aligned, component_results, report)
    return report, debug


def _component_label(slot_id: str) -> str:
    if slot_id == "ai_gpu":
        return "GPU"
    if slot_id.startswith("hbm_"):
        return "H" + str(int(slot_id.split("_")[-1]))
    return slot_id


def draw_debug(
    image: np.ndarray,
    results: list[ComponentResult],
    report: dict[str, Any],
) -> np.ndarray:
    canvas = image.copy()
    for component in results:
        color = STATUS_COLORS[component.status]
        center = tuple(component.center_px)
        cv2.circle(canvas, center, 5, color, -1, cv2.LINE_AA)
        for side in component.sides:
            side_color = STATUS_COLORS[side.status]
            x0, y0, x1, y1 = side.strip_px
            edge_x = int(round((x0 + x1) * 0.5))
            cv2.line(canvas, (edge_x, y0), (edge_x, y1), side_color, 2, cv2.LINE_AA)
            for point in side.missing_points_px:
                cv2.circle(canvas, tuple(point), 11, STATUS_COLORS["FAIL"], 3, cv2.LINE_AA)
        label = f"{_component_label(component.slot_id)} {component.status}"
        text_size, baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1
        )
        text_x = center[0] - text_size[0] // 2
        text_y = center[1] - 14
        cv2.rectangle(
            canvas,
            (text_x - 5, text_y - text_size[1] - 4),
            (text_x + text_size[0] + 5, text_y + baseline + 3),
            (18, 21, 25),
            -1,
        )
        cv2.putText(
            canvas, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX,
            0.46, color, 1, cv2.LINE_AA,
        )

    hud_height = 108
    output = np.full(
        (canvas.shape[0] + hud_height, canvas.shape[1], 3),
        (18, 21, 25),
        dtype=np.uint8,
    )
    output[hud_height:] = canvas
    status = str(report["status"])
    cv2.putText(
        output,
        f"PACKAGE LEG INSPECTION | {status}",
        (24, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.88,
        STATUS_COLORS[status],
        2,
        cv2.LINE_AA,
    )
    passes = sum(item.status == "PASS" for item in results)
    rechecks = sum(item.status == "RECHECK" for item in results)
    failures = sum(item.status == "FAIL" for item in results)
    summary = (
        f"COMPONENTS {len(results)} | PASS {passes} | "
        f"D435 RECHECK {rechecks} | FAIL {failures} | "
        f"BOARD ALIGN {report['alignment']['score']:.3f}"
    )
    cv2.putText(
        output, summary, (24, 76), cv2.FONT_HERSHEY_SIMPLEX,
        0.61, (222, 227, 232), 1, cv2.LINE_AA,
    )
    legend = "GREEN match   AMBER hidden/uncertain -> D435   RED missing/deformed"
    cv2.putText(
        output, legend, (24, 99), cv2.FONT_HERSHEY_SIMPLEX,
        0.45, (145, 154, 165), 1, cv2.LINE_AA,
    )
    return output


def set_reference(source: Path, destination: Path) -> Path:
    image = _load_image(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.png")
    if not cv2.imwrite(str(temporary), image, (cv2.IMWRITE_PNG_COMPRESSION, 2)):
        raise RuntimeError(f"Could not save golden reference: {temporary}")
    temporary.replace(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source.resolve()),
        "reference": str(destination.resolve()),
        "image_size_px": [image.shape[1], image.shape[0]],
        "sha256": digest,
        "note": "Use only a verified normal board captured at the final inspection stop.",
    }
    destination.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--set-reference",
        type=Path,
        help="store a verified normal rectified ROI as the local golden image",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--strict-exit", action="store_true")
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    config = _load_json(config_path)
    reference_path = (
        args.reference.expanduser().resolve()
        if args.reference
        else _project_path(config["reference_image"])
    )
    if args.set_reference:
        saved = set_reference(args.set_reference.expanduser().resolve(), reference_path)
        print(f"Golden package-leg reference saved: {saved}")
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
    report, debug = inspect(reference, image, config, layout)
    report["created_at"] = datetime.now().astimezone().isoformat()
    report["input_image"] = str(image_path)
    report["reference_image"] = str(reference_path)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_path = output_dir / f"package_leg_inspection_{timestamp}.png"
    report_path = output_dir / f"package_leg_inspection_{timestamp}.json"
    if not cv2.imwrite(str(debug_path), debug, (cv2.IMWRITE_PNG_COMPRESSION, 2)):
        raise RuntimeError(f"Could not save debug image: {debug_path}")
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _atomic_symlink(debug_path, output_dir / "package_leg_inspection_latest.png")
    _atomic_symlink(report_path, output_dir / "package_leg_inspection_latest.json")
    print(f"Package-leg status: {report['status']}")
    print(f"Debug image: {debug_path}")
    print(f"JSON report: {report_path}")
    if report["failures"]:
        print("Failures: " + ", ".join(report["failures"]))
    if report["d435_recheck"]:
        print("D435 recheck: " + ", ".join(report["d435_recheck"]))

    if args.strict_exit:
        if report["status"] == "FAIL":
            sys.exit(3)
        if report["status"] == "RECHECK":
            sys.exit(2)


if __name__ == "__main__":
    main()
