#!/usr/bin/env python3
"""Build reviewed fixed-slot PatchCore crops without false defect labels."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil

import cv2

from build_component_patchcore_dataset import (
    OUTPUT_SIZE,
    PROJECT_DIR,
    TYPE_DIRS,
    _crop_slot,
    _load_json,
    _resolve,
)
from full_board_inspector import slot_geometry
from layout_overrides import apply_component_slot_overrides


SOURCE_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/strict_normal_candidates"
INDUCTOR_NORMAL_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/inductor_normal_candidates"
INDUCTOR_DEFECT_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/controlled_inductor_defects"
GPU_NORMAL_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/gpu_normal_candidates"
GPU_DEFECT_ROOT = PROJECT_DIR / "runtime/datasets/s22_aoi/controlled_gpu_defects"
DEFECT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_20260902_211811.png"
OUTPUT = PROJECT_DIR / "vision_assembly/inspection/datasets/pcb_components_strict_v4"
CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
HOLDOUT_STEMS = {
    "s22_inspection_roi_20260902_220737",
    "s22_inspection_roi_20260903_100758",
    "s22_inspection_roi_20260903_102613",
}
CONTROLLED_DEFECT_SLOTS = {
    "ai_gpu",
    "hbm_04", "hbm_06", "hbm_08",
    "power_module_03",
    "vrm_01", "vrm_05",
    "inductor_01", "inductor_02",
    "smd_capacitor_01",
}


def main() -> None:
    normal_images = sorted(SOURCE_ROOT.glob("**/roi/*.png"))
    if len(normal_images) != 14:
        raise RuntimeError(f"Expected 14 reviewed normal captures, found {len(normal_images)}")
    if not DEFECT_IMAGE.is_file():
        raise RuntimeError(f"Controlled-defect image is missing: {DEFECT_IMAGE}")

    config = _load_json(CONFIG)
    layout = _load_json(_resolve(config["board_layout"]))
    physical = _load_json(_resolve(config["physical_board"]))
    layout, override_slots = apply_component_slot_overrides(layout, physical)
    board = layout["board"]["size_mm"]
    board_size = (float(board["x"]), float(board["y"]))

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    rows: list[dict[str, object]] = []
    counts: dict[str, dict[str, int]] = {}

    def export(image_path: Path, group: str, allowed_slots: set[str] | None) -> None:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot decode {image_path}")
        if image.shape[:2] != (1266, 1600):
            raise RuntimeError(f"Unexpected registered ROI shape {image.shape}: {image_path}")
        for placement in layout["placements"]:
            slot_id = str(placement["slot_id"])
            if allowed_slots is not None and slot_id not in allowed_slots:
                continue
            component_type = str(placement["component_type"])
            component = TYPE_DIRS[component_type]
            geometry = slot_geometry(placement, image.shape, board_size, config["coordinate_mapping"])
            crop, rotated, source_size = _crop_slot(
                image, geometry, 0.22, OUTPUT_SIZE[component_type]
            )
            destination = OUTPUT / component / group / f"{image_path.stem}__{slot_id}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
                raise RuntimeError(f"Cannot save {destination}")
            counts.setdefault(component, {}).setdefault(group, 0)
            counts[component][group] += 1
            rows.append({
                "component_type": component_type,
                "component_dir": component,
                "slot_id": slot_id,
                "dataset_group": group,
                "source_image": str(image_path.relative_to(PROJECT_DIR)),
                "crop_image": str(destination.relative_to(OUTPUT)),
                "normal_training_allowed": group in {"train/good", "test/good"},
                "defect_location_verified": group == "test/controlled_defect",
                "rotated_to_horizontal": rotated,
                "source_crop_width_px": source_size[0],
                "source_crop_height_px": source_size[1],
            })

    for image_path in normal_images:
        group = "test/good" if image_path.stem in HOLDOUT_STEMS else "train/good"
        export(image_path, group, None)
    export(DEFECT_IMAGE, "test/controlled_defect", CONTROLLED_DEFECT_SLOTS)

    inductor_normals = sorted(INDUCTOR_NORMAL_ROOT.glob("**/roi/*.png"))
    if len(inductor_normals) != 5:
        raise RuntimeError(f"Expected 5 Inductor normal-variation captures, found {len(inductor_normals)}")
    for index, image_path in enumerate(inductor_normals):
        group = "test/good" if index == len(inductor_normals) - 1 else "train/good"
        export(image_path, group, {"inductor_01", "inductor_02"})

    inductor_defect_manifests = sorted(INDUCTOR_DEFECT_ROOT.glob("**/manifests/*.json"))
    for manifest_path in inductor_defect_manifests:
        manifest = _load_json(manifest_path)
        defects = manifest.get("board_annotation", {}).get("known_defects", [])
        if len(defects) != 1:
            raise RuntimeError(f"Expected one controlled Inductor defect in {manifest_path}")
        defect = str(defects[0])
        if defect.startswith("inductor_01_"):
            slot_id = "inductor_01"
        elif defect.startswith("inductor_02_"):
            slot_id = "inductor_02"
        else:
            raise RuntimeError(f"Unexpected Inductor defect tag {defect}")
        image_path = Path(manifest["archived_files"]["roi"])
        export(image_path, "test/controlled_defect", {slot_id})

    gpu_normals = sorted(GPU_NORMAL_ROOT.glob("**/roi/*.png"))
    if len(gpu_normals) < 10:
        raise RuntimeError(f"Expected at least 10 GPU normal-variation captures, found {len(gpu_normals)}")
    gpu_holdout_count = max(4, len(gpu_normals) // 5)
    for index, image_path in enumerate(gpu_normals):
        group = "test/good" if index >= len(gpu_normals) - gpu_holdout_count else "train/good"
        export(image_path, group, {"ai_gpu"})

    gpu_defect_manifests = sorted(GPU_DEFECT_ROOT.glob("**/manifests/*.json"))
    if not gpu_defect_manifests:
        raise RuntimeError("No controlled GPU defect manifests were found")
    for manifest_path in gpu_defect_manifests:
        manifest = _load_json(manifest_path)
        defects = manifest.get("board_annotation", {}).get("known_defects", [])
        if len(defects) != 1 or not str(defects[0]).startswith("gpu_01_"):
            raise RuntimeError(f"Unexpected controlled GPU tag in {manifest_path}: {defects}")
        image_path = Path(manifest["archived_files"]["roi"])
        export(image_path, "test/controlled_defect", {"ai_gpu"})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema_version": 1,
        "status": "ADVISORY_ONLY",
        "crop_contract": "fixed_slot_rgb_margin_0.22_no_pose_normalization",
        "normal_source_count": len(normal_images),
        "train_normal_boards": 11,
        "holdout_normal_boards": 3,
        "controlled_defect_source": str(DEFECT_IMAGE.relative_to(PROJECT_DIR)),
        "controlled_defect_slots": sorted(CONTROLLED_DEFECT_SLOTS),
        "inductor_normal_variation_boards": len(inductor_normals),
        "inductor_controlled_defect_boards": len(inductor_defect_manifests),
        "gpu_normal_variation_boards": len(gpu_normals),
        "gpu_normal_variation_holdout_boards": gpu_holdout_count,
        "gpu_controlled_defect_boards": len(gpu_defect_manifests),
        "counts": counts,
        "physical_override_slots": override_slots,
        "limitations": [
            "Only one controlled-defect scene is available.",
            "Thresholds cannot become authoritative until more independent defect scenes are captured.",
        ],
    }
    (OUTPUT / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(counts, indent=2, ensure_ascii=False))
    print(f"STRICT_COMPONENT_DATASET={OUTPUT}")


if __name__ == "__main__":
    main()
