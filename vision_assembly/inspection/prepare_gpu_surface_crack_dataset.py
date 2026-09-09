#!/usr/bin/env python3
"""Build a GPU package-interior anomaly dataset.

Only verified normal GPU captures enter training.  The two physical crack
captures are held out exclusively for blind evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import cv2

from build_component_patchcore_dataset import OUTPUT_SIZE, _crop_slot, _load_json, _resolve
from full_board_inspector import slot_geometry
from layout_overrides import apply_component_slot_overrides


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
NORMAL_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/gpu_normal_candidates"
INDEPENDENT_NORMAL_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/gpu_blind_normal_holdout"
CRACK_IMAGES = (
    PROJECT_DIR / "runtime/inspection/s22_inspection_roi_20260903_163649.png",
    PROJECT_DIR / "runtime/inspection/s22_inspection_roi_20260903_164340.png",
)
OUTPUT = PROJECT_DIR / "vision_assembly/inspection/datasets/gpu_surface_crack_v1"
INTERIOR_BOUNDS = (0.17, 0.12, 0.83, 0.88)
INTERIOR_SIZE = (320, 512)


def gpu_placement() -> tuple[dict, tuple[float, float], dict]:
    config = _load_json(CONFIG)
    layout = _load_json(_resolve(config["board_layout"]))
    physical = _load_json(_resolve(config["physical_board"]))
    layout, _ = apply_component_slot_overrides(layout, physical)
    placement = next(item for item in layout["placements"] if item["slot_id"] == "ai_gpu")
    size = layout["board"]["size_mm"]
    return placement, (float(size["x"]), float(size["y"])), config


def interior_crop(image_path: Path, placement: dict, board_size: tuple[float, float], config: dict):
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None or image.shape[:2] != (1266, 1600):
        raise RuntimeError(f"Invalid registered S22 ROI: {image_path}")
    geometry = slot_geometry(
        placement, image.shape, board_size, config["coordinate_mapping"]
    )
    package, _, _ = _crop_slot(image, geometry, 0.22, OUTPUT_SIZE["GPU"])
    height, width = package.shape[:2]
    x0, y0, x1, y1 = INTERIOR_BOUNDS
    interior = package[
        int(round(y0 * height)):int(round(y1 * height)),
        int(round(x0 * width)):int(round(x1 * width)),
    ]
    return cv2.resize(interior, INTERIOR_SIZE, interpolation=cv2.INTER_CUBIC)


def main() -> None:
    normals = sorted(NORMAL_ROOT.glob("**/roi/*.png"))
    independent = sorted(INDEPENDENT_NORMAL_ROOT.glob("**/roi/*.png"))
    if len(normals) != 18 or len(independent) != 5:
        raise RuntimeError(
            f"Expected 18 normal candidates and 5 independent normals; "
            f"found {len(normals)} and {len(independent)}"
        )
    if any(not path.is_file() for path in CRACK_IMAGES):
        raise RuntimeError("One or more physical crack holdouts are missing")
    placement, board_size, config = gpu_placement()
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)

    groups = {
        "train/good": normals[:14],
        "test/good": normals[14:] + independent,
        "test/crack": list(CRACK_IMAGES),
    }
    for group, paths in groups.items():
        directory = OUTPUT / "gpu" / group
        directory.mkdir(parents=True, exist_ok=True)
        for path in paths:
            crop = interior_crop(path, placement, board_size, config)
            destination = directory / f"{path.stem}__gpu_surface.png"
            if not cv2.imwrite(str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
                raise RuntimeError(f"Cannot save {destination}")

    summary = {
        "schema_version": 1,
        "status": "ADVISORY_ONLY",
        "task": "gpu_black_package_surface_anomaly",
        "input": "registered_original_s22_rgb",
        "interior_bounds_xyxy_relative_to_gpu_crop": INTERIOR_BOUNDS,
        "output_size_wh": INTERIOR_SIZE,
        "counts": {group: len(paths) for group, paths in groups.items()},
        "training_policy": "verified_normal_only",
        "crack_policy": "physical_crack_images_are_blind_test_only",
        "limitations": [
            "Only two physical crack images are available.",
            "No automatic PASS/FAIL authority is granted.",
        ],
    }
    (OUTPUT / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"GPU_SURFACE_DATASET={OUTPUT}")


if __name__ == "__main__":
    main()
