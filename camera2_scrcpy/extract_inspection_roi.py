#!/usr/bin/env python3
"""Detect and perspective-rectify the PCB body in an S22 inspection photo."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[1]
VISION_SOURCE = PROJECT_DIR / "ros2_ws" / "src" / "vision_server"
if str(VISION_SOURCE) not in sys.path:
    sys.path.insert(0, str(VISION_SOURCE))

from vision_server.conveyor_roi import BoardDetection, detect_dark_board  # noqa: E402


DEFAULT_INPUT = PROJECT_DIR / "runtime" / "inspection" / "s22_telephoto_latest.jpg"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "runtime" / "inspection"
THRESHOLDS = (45, 55, 70, 85, 100)


def _candidate_score(detection: BoardDetection, expected_aspect: float) -> float:
    aspect_error = abs(np.log(detection.aspect_ratio / expected_aspect))
    aspect_score = float(np.exp(-2.0 * aspect_error))
    return (
        detection.area_fraction
        * detection.rectangularity
        * (0.55 + 0.45 * aspect_score)
    )


def detect_board(image: np.ndarray, expected_aspect: float):
    candidates = []
    kernel = max(9, int(round(min(image.shape[:2]) * 0.008)) | 1)
    for threshold in THRESHOLDS:
        detection = detect_dark_board(
            image,
            search_bounds=(0.0, 1.0, 0.0, 1.0),
            dark_threshold=threshold,
            close_kernel_px=kernel,
            min_area_fraction=0.035,
            max_area_fraction=0.35,
            min_aspect_ratio=1.0,
            max_aspect_ratio=1.85,
            min_rectangularity=0.65,
            travel_direction="positive_x",
            body_span_ratio=0.75,
            body_extension_ratio=1.10,
            body_extension_fraction=0.12,
        )
        if detection is not None:
            candidates.append(
                (_candidate_score(detection, expected_aspect), threshold, detection)
            )
    if not candidates:
        raise RuntimeError(
            "PCB body was not detected; confirm that the complete board is visible "
            "in the optical inspection photo"
        )
    return max(candidates, key=lambda item: item[0])


def _cyclic_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32).reshape(4, 2)
    center = np.mean(points, axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    return points[np.argsort(angles)]


def canonical_source_corners(points: np.ndarray) -> np.ndarray:
    """Map the physical long board dimension to output image width.

    The selected long edge is the image-left edge when the board is vertical,
    or the image-top edge when it is horizontal. This keeps the fixed conveyor
    pose deterministic while allowing small translations and rotations.
    """
    points = _cyclic_points(points)
    edges = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(edges, axis=1)
    long_indices = np.argsort(lengths)[-2:]
    long_vector = edges[int(long_indices[-1])]
    vertical = abs(float(long_vector[1])) >= abs(float(long_vector[0]))

    def edge_rank(index: int):
        midpoint = (points[index] + points[(index + 1) % 4]) * 0.5
        return float(midpoint[0] if vertical else midpoint[1])

    edge_index = min((int(index) for index in long_indices), key=edge_rank)
    order = np.asarray(
        [points[(edge_index + offset) % 4] for offset in range(4)],
        dtype=np.float32,
    )
    direction = order[1] - order[0]
    forward = float(direction[1] if vertical else direction[0]) >= 0.0
    if not forward:
        order = np.asarray((order[1], order[0], order[3], order[2]), dtype=np.float32)
    return order


def operator_source_corners(points: np.ndarray) -> np.ndarray:
    """Return corners for an upright, non-mirrored operator ROI.

    ``canonical_source_corners`` follows the selected long edge in the
    opposite winding from the landscape destination rectangle. Reversing the
    winding keeps the intended quarter-turn while preventing the homography
    from introducing a left-right reflection.
    """
    return canonical_source_corners(points)[::-1].copy()


def atomic_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.tmp")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target.resolve())
    temporary.replace(link)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--upright-output", type=Path)
    parser.add_argument("--debug-output", type=Path)
    parser.add_argument("--metadata-output", type=Path)
    parser.add_argument("--board-width-mm", type=float, default=139.0)
    parser.add_argument("--board-height-mm", type=float, default=110.0)
    parser.add_argument("--output-long-px", type=int, default=1600)
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Inspection image does not exist: {input_path}")
    if args.board_width_mm <= 0.0 or args.board_height_mm <= 0.0:
        raise ValueError("Physical board dimensions must be positive")
    if args.output_long_px < 400:
        raise ValueError("--output-long-px must be at least 400")

    image = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"OpenCV could not decode: {input_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = DEFAULT_OUTPUT_DIR
    upright_path = (
        args.upright_output.expanduser().resolve()
        if args.upright_output
        else output_dir / f"s22_telephoto_upright_{timestamp}.png"
    )
    upright_path.parent.mkdir(parents=True, exist_ok=True)
    upright = cv2.rotate(image, cv2.ROTATE_180)
    if not cv2.imwrite(
        str(upright_path), upright, (cv2.IMWRITE_PNG_COMPRESSION, 2)
    ):
        raise RuntimeError(f"Could not save upright inspection photo: {upright_path}")
    atomic_symlink(
        upright_path, output_dir / "s22_telephoto_upright_latest.png"
    )

    long_mm = max(args.board_width_mm, args.board_height_mm)
    short_mm = min(args.board_width_mm, args.board_height_mm)
    expected_aspect = long_mm / short_mm
    score, threshold, detection = detect_board(image, expected_aspect)
    # Keep the board upright for the operator without changing handedness.
    # The previous cyclic roll retained the source polygon's opposite winding
    # and therefore produced a horizontally mirrored homography.
    source = operator_source_corners(detection.points)

    height, width = image.shape[:2]
    edge_margins = np.column_stack(
        (
            source[:, 0],
            source[:, 1],
            (width - 1.0) - source[:, 0],
            (height - 1.0) - source[:, 1],
        )
    )
    minimum_edge_margin = float(np.min(edge_margins))
    required_edge_margin = max(6.0, min(width, height) * 0.002)
    if minimum_edge_margin < required_edge_margin:
        raise RuntimeError(
            "PCB touches the optical photo boundary and is not valid for "
            "inspection; move the board fully into the optical frame "
            f"(edge margin {minimum_edge_margin:.1f}px)"
        )

    output_width = int(args.output_long_px)
    output_height = int(round(output_width * short_mm / long_mm))
    destination = np.asarray(
        (
            (0.0, 0.0),
            (output_width - 1.0, 0.0),
            (output_width - 1.0, output_height - 1.0),
            (0.0, output_height - 1.0),
        ),
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(source, destination)
    roi = cv2.warpPerspective(
        image,
        homography,
        (output_width, output_height),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )

    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else output_dir / f"s22_inspection_roi_{timestamp}.png"
    )
    debug_path = (
        args.debug_output.expanduser().resolve()
        if args.debug_output
        else output_dir / f"s22_inspection_roi_debug_{timestamp}.jpg"
    )
    metadata_path = (
        args.metadata_output.expanduser().resolve()
        if args.metadata_output
        else output_dir / f"s22_inspection_roi_{timestamp}.json"
    )
    for path in (output_path, debug_path, metadata_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(output_path), roi, (cv2.IMWRITE_PNG_COMPRESSION, 2)):
        raise RuntimeError(f"Could not save rectified ROI: {output_path}")

    debug = image.copy()
    polygon = np.rint(source).astype(np.int32)
    line_width = max(3, int(round(min(image.shape[:2]) * 0.0025)))
    cv2.polylines(debug, [polygon], True, (50, 230, 90), line_width, cv2.LINE_AA)
    for index, point in enumerate(polygon):
        cv2.circle(debug, tuple(point), line_width * 2, (30, 90, 255), -1, cv2.LINE_AA)
        cv2.putText(
            debug,
            str(index + 1),
            tuple(point + np.asarray((12, -12))),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (30, 90, 255),
            3,
            cv2.LINE_AA,
        )
    debug_scale = min(1.0, 1800.0 / max(debug.shape[:2]))
    if debug_scale < 1.0:
        debug = cv2.resize(debug, None, fx=debug_scale, fy=debug_scale,
                           interpolation=cv2.INTER_AREA)
    if not cv2.imwrite(str(debug_path), debug, (cv2.IMWRITE_JPEG_QUALITY, 92)):
        raise RuntimeError(f"Could not save ROI debug image: {debug_path}")

    normalized = source / np.asarray((width, height), dtype=np.float32)
    metadata = {
        "schema_version": 1,
        "input_image": str(input_path),
        "upright_full_image": str(upright_path),
        "rectified_roi": str(output_path),
        "debug_image": str(debug_path),
        "source_size_px": [width, height],
        "output_size_px": [output_width, output_height],
        "physical_board_size_mm": [args.board_width_mm, args.board_height_mm],
        "source_corners_px": source.astype(float).tolist(),
        "source_corners_normalized": normalized.astype(float).tolist(),
        "source_to_roi_homography": homography.astype(float).tolist(),
        "detector": {
            "dark_threshold": threshold,
            "score": float(score),
            "area_fraction": float(detection.area_fraction),
            "aspect_ratio_observed": float(detection.aspect_ratio),
            "rectangularity": float(detection.rectangularity),
            "long_axis_angle_deg": float(detection.long_axis_angle_deg),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    atomic_symlink(output_path, output_dir / "s22_inspection_roi_latest.png")
    atomic_symlink(debug_path, output_dir / "s22_inspection_roi_debug_latest.jpg")
    atomic_symlink(metadata_path, output_dir / "s22_inspection_roi_latest.json")
    print(f"S22 inspection ROI: {output_path}")
    print(f"S22 upright inspection photo: {upright_path}")
    print(f"S22 inspection ROI debug: {debug_path}")
    print(
        "Board detection: "
        f"threshold={threshold}, area={detection.area_fraction:.4f}, "
        f"rectangularity={detection.rectangularity:.3f}"
    )


if __name__ == "__main__":
    main()
