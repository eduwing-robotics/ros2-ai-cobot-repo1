#!/usr/bin/env python3
"""Build slot-normalized S22 component crops for anomaly inspection.

Only reviewed normal board images are eligible for PatchCore training.  The
legacy mixed-defect boards do not identify which slot is defective, so their
crops are exported as unverified inference samples rather than false anomaly
ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
from typing import Any

import cv2

from full_board_inspector import slot_geometry
from layout_overrides import apply_component_slot_overrides


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_DIR / "vision_assembly/inspection/datasets/pcb_anomaly_v1"
DEFAULT_OUTPUT = PROJECT_DIR / "vision_assembly/inspection/datasets/pcb_components_v1"
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
EXCLUDED_TYPES = {"SMD Capacitor"}
TYPE_DIRS = {
    "GPU": "gpu",
    "HBM": "hbm",
    "Power Module": "power_module",
    "VRM": "vrm",
    "Inductor": "inductor",
    "SMD Capacitor": "smd_capacitor",
}
OUTPUT_SIZE = {
    "GPU": (256, 384),
    "HBM": (224, 288),
    "Power Module": (384, 160),
    "VRM": (224, 224),
    "Inductor": (224, 224),
    "SMD Capacitor": (192, 128),
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def _crop_slot(
    image,
    geometry: tuple[float, float, float, float],
    margin_ratio: float,
    output_size: tuple[int, int],
):
    center_x, center_y, size_x, size_y = geometry
    crop_width = max(12, int(round(size_x * (1.0 + 2.0 * margin_ratio))))
    crop_height = max(12, int(round(size_y * (1.0 + 2.0 * margin_ratio))))
    crop = cv2.getRectSubPix(
        image, (crop_width, crop_height), (float(center_x), float(center_y))
    )
    rotated = False
    if crop.shape[0] > crop.shape[1]:
        crop = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
        rotated = True
    width, height = output_size
    resized = cv2.resize(crop, (width, height), interpolation=cv2.INTER_CUBIC)
    return resized, rotated, (crop_width, crop_height)


def build_dataset(
    source: Path,
    output: Path,
    config_path: Path,
    margin_ratio: float,
    include_smd: bool = False,
) -> dict[str, Any]:
    config = _load_json(config_path)
    layout = _load_json(_resolve(config["board_layout"]))
    physical = _load_json(_resolve(config["physical_board"]))
    layout, override_slots = apply_component_slot_overrides(layout, physical)
    board = layout["board"]["size_mm"]
    board_size = (float(board["x"]), float(board["y"]))

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    groups = {
        "train/good": "train/good",
        "test/good": "test/good",
        "test/mixed_defect": "unverified/mixed_defect",
    }
    rows: list[dict[str, Any]] = []
    counts: dict[str, dict[str, int]] = {}
    reference_shape = None

    for source_group, destination_group in groups.items():
        for image_path in sorted((source / source_group).glob("*.png")):
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Could not decode {image_path}")
            if reference_shape is None:
                reference_shape = list(image.shape)
            elif list(image.shape) != reference_shape:
                raise RuntimeError(
                    f"Rectified ROI size changed: {image_path} is {image.shape}, "
                    f"expected {tuple(reference_shape)}"
                )

            for placement in layout["placements"]:
                component_type = str(placement["component_type"])
                if component_type in EXCLUDED_TYPES and not include_smd:
                    continue
                type_dir = TYPE_DIRS[component_type]
                geometry = slot_geometry(
                    placement,
                    image.shape,
                    board_size,
                    config["coordinate_mapping"],
                )
                crop, rotated, source_crop_size = _crop_slot(
                    image,
                    geometry,
                    margin_ratio,
                    OUTPUT_SIZE[component_type],
                )
                destination_dir = output / type_dir / destination_group
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination = destination_dir / (
                    f"{image_path.stem}__{placement['slot_id']}.png"
                )
                if not cv2.imwrite(
                    str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]
                ):
                    raise RuntimeError(f"Could not save {destination}")
                counts.setdefault(type_dir, {}).setdefault(destination_group, 0)
                counts[type_dir][destination_group] += 1
                rows.append({
                    "component_type": component_type,
                    "component_dir": type_dir,
                    "slot_id": placement["slot_id"],
                    "source_group": source_group,
                    "dataset_group": destination_group,
                    "source_image": str(image_path.relative_to(source)),
                    "crop_image": str(destination.relative_to(output)),
                    "normal_training_allowed": destination_group in {
                        "train/good", "test/good"
                    },
                    "defect_location_verified": False,
                    "rotated_to_horizontal": rotated,
                    "source_crop_width_px": source_crop_size[0],
                    "source_crop_height_px": source_crop_size[1],
                    "output_width_px": crop.shape[1],
                    "output_height_px": crop.shape[0],
                })

    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "schema_version": 1,
        "source_dataset": str(source),
        "config": str(config_path),
        "excluded_component_types": [] if include_smd else sorted(EXCLUDED_TYPES),
        "margin_ratio": margin_ratio,
        "source_image_shape": reference_shape,
        "counts": counts,
        "physical_override_slots": override_slots,
        "policy": {
            "train_good": "reviewed normal board crops",
            "test_good": "held-out reviewed normal board crops",
            "unverified_mixed_defect": (
                "inference only; board-level defect labels do not identify bad slots"
            ),
        },
    }
    (output / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--margin-ratio", type=float, default=0.22)
    parser.add_argument("--include-smd", action="store_true")
    args = parser.parse_args()
    summary = build_dataset(
        args.source.expanduser().resolve(),
        args.output.expanduser().resolve(),
        args.config.expanduser().resolve(),
        args.margin_ratio,
        args.include_smd,
    )
    print(json.dumps(summary["counts"], indent=2))
    print(f"COMPONENT_DATASET={args.output.expanduser().resolve()}")


if __name__ == "__main__":
    main()
