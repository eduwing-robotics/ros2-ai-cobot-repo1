#!/usr/bin/env python3
"""Build the locked S22 VRM FLAT/SEATING dataset from audited scenes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import cv2


PROJECT_DIR = Path(__file__).resolve().parents[2]
HYBRID_DIR = PROJECT_DIR / "vision_assembly/hybrid_inspection"
if str(HYBRID_DIR) not in sys.path:
    sys.path.insert(0, str(HYBRID_DIR))

from preprocessor_and_cropper import FixedSlotCropper  # noqa: E402
from vrm_seating_common import (  # noqa: E402
    VRM_SEATING_CROP_PIPELINE,
    crop_vrm_seating_slot,
)


DEFAULT_SPEC = PROJECT_DIR / "vision_assembly/config/vrm_seating_ground_truth_v1.json"
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
DEFAULT_OUTPUT = PROJECT_DIR / "vision_assembly/slot_classifier/datasets/vrm_seating_v3"
LABELS = {"FLAT", "SEATING"}
SPLITS = {"train", "validation", "holdout"}
EXPECTED_SLOTS = {f"vrm_{index:02d}" for index in range(1, 6)}


def _resolve(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    return candidate.resolve() if candidate.is_absolute() else (PROJECT_DIR / candidate).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("task") != "vrm_fixed_slot_seating":
        raise ValueError("Ground-truth task must be vrm_fixed_slot_seating")
    if spec.get("crop_pipeline") != VRM_SEATING_CROP_PIPELINE:
        raise ValueError("Ground-truth crop pipeline does not match runtime")
    physical_splits: dict[str, str] = {}
    seen_scene_ids: set[str] = set()
    holdout_has_seating = False
    for scene in spec.get("registered_scenes", []):
        scene_id = str(scene.get("scene_id", ""))
        physical_id = str(scene.get("physical_scene_id", ""))
        split = str(scene.get("split", ""))
        labels = scene.get("labels", {})
        if not scene_id or scene_id in seen_scene_ids:
            raise ValueError(f"Missing or duplicate scene_id: {scene_id!r}")
        seen_scene_ids.add(scene_id)
        if not physical_id or split not in SPLITS:
            raise ValueError(f"Invalid physical scene/split in {scene_id}")
        previous = physical_splits.setdefault(physical_id, split)
        if previous != split:
            raise ValueError(
                f"Physical scene leakage: {physical_id} occurs in {previous} and {split}"
            )
        if set(labels) != EXPECTED_SLOTS:
            raise ValueError(f"{scene_id} must explicitly label all five VRM slots")
        invalid = {str(value).upper() for value in labels.values()} - LABELS
        if invalid:
            raise ValueError(f"Invalid labels in {scene_id}: {sorted(invalid)}")
        holdout_has_seating |= split == "holdout" and any(
            str(value).upper() == "SEATING" for value in labels.values()
        )
    if not holdout_has_seating:
        raise ValueError("A locked SEATING holdout is required")


def _copy_crop(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build_dataset(spec_path: Path, config_path: Path, output: Path) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_spec(spec)
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(
            f"Output is not empty: {output}. Use a fresh versioned dataset directory."
        )
    output.mkdir(parents=True, exist_ok=True)
    spec_copy = output / "ground_truth_spec.json"
    spec_copy.write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    cropper = FixedSlotCropper(config_path)
    records: list[dict[str, Any]] = []

    imported = spec["import_flat_rows"]
    state_manifest = _resolve(imported["manifest"])
    for line in state_manifest.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        if str(row.get("label", "")).lower() != str(imported["source_label"]).lower():
            continue
        source_crop = state_manifest.parent / row["crop_image"]
        capture = str(row["captured_at"])
        slot_id = str(row["slot_id"])
        destination = output / "crops" / "flat" / f"state_{capture}__{slot_id}.png"
        _copy_crop(source_crop, destination)
        records.append(
            {
                "schema_version": 1,
                "task": "vrm_fixed_slot_seating",
                "scene_id": f"state_{row['scene_id']}_{capture}",
                "physical_scene_id": f"state::{row['scene_id']}",
                "split": str(imported["split"]),
                "slot_id": slot_id,
                "label": "flat",
                "crop_image": str(destination.relative_to(output)),
                "crop_sha256": _sha256(destination),
                "crop_pipeline": VRM_SEATING_CROP_PIPELINE,
                "illumination": row.get("illumination", "ambient"),
                "label_authority": imported["label_authority"],
                "source_reference": str(source_crop.resolve()),
                "robot_command_sent": False,
                "conveyor_command_sent": False,
            }
        )

    for scene in spec["registered_scenes"]:
        image_path = _resolve(scene["image"])
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Cannot decode registered board: {image_path}")
        if (image.shape[1], image.shape[0]) != (1600, 1266):
            raise RuntimeError(f"Expected registered board 1600x1266: {image_path}")
        source_destination = output / "source" / f"{scene['scene_id']}.png"
        _copy_crop(image_path, source_destination)
        slots = {
            slot.slot_id: slot
            for slot in cropper.fixed_slots(image)
            if slot.component_type == "VRM"
        }
        if set(slots) != EXPECTED_SLOTS:
            raise RuntimeError(f"Expected five VRM slots, got {sorted(slots)}")
        for slot_id in sorted(slots):
            label = str(scene["labels"][slot_id]).lower()
            crop = crop_vrm_seating_slot(image, slots[slot_id].geometry)
            destination = output / "crops" / label / f"{scene['scene_id']}__{slot_id}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(destination), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
                raise RuntimeError(f"Cannot write crop: {destination}")
            records.append(
                {
                    "schema_version": 1,
                    "task": "vrm_fixed_slot_seating",
                    "scene_id": scene["scene_id"],
                    "physical_scene_id": scene["physical_scene_id"],
                    "split": scene["split"],
                    "slot_id": slot_id,
                    "label": label,
                    "crop_image": str(destination.relative_to(output)),
                    "crop_sha256": _sha256(destination),
                    "crop_pipeline": VRM_SEATING_CROP_PIPELINE,
                    "illumination": "ambient",
                    "label_authority": scene["label_authority"],
                    "source_reference": str(image_path),
                    "source_sha256": _sha256(image_path),
                    "note": scene.get("note", ""),
                    "robot_command_sent": False,
                    "conveyor_command_sent": False,
                }
            )

    physical_splits: dict[str, set[str]] = {}
    for row in records:
        physical_splits.setdefault(row["physical_scene_id"], set()).add(row["split"])
    leaked = {key: value for key, value in physical_splits.items() if len(value) != 1}
    if leaked:
        raise RuntimeError(f"Physical-scene leakage in generated dataset: {leaked}")
    manifest = output / "manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )
    summary = {
        "schema_version": 1,
        "task": "vrm_fixed_slot_seating",
        "spec": str(spec_path),
        "spec_copy": str(spec_copy),
        "spec_sha256": _sha256(spec_copy),
        "crop_pipeline": VRM_SEATING_CROP_PIPELINE,
        "records": len(records),
        "counts": {
            split: {
                label: sum(
                    row["split"] == split and row["label"] == label
                    for row in records
                )
                for label in ("flat", "seating")
            }
            for split in ("train", "validation", "holdout")
        },
        "physical_scenes": {
            split: sorted(
                {
                    row["physical_scene_id"]
                    for row in records
                    if row["split"] == split
                }
            )
            for split in ("train", "validation", "holdout")
        },
        "excluded_scenes": spec.get("excluded_scenes", []),
        "authority": "EXPLICIT_USER_CONTROLLED_GROUND_TRUTH",
        "model_authority_ceiling": "ADVISORY_ONLY",
        "robot_command_sent": False,
        "conveyor_command_sent": False,
    }
    (output / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_dataset(
        args.spec.expanduser().resolve(),
        args.config.expanduser().resolve(),
        args.output.expanduser().resolve(),
    )
    print(f"VRM_SEATING_DATASET={args.output.expanduser().resolve()}")
    print(f"VRM_SEATING_COUNTS={json.dumps(summary['counts'], sort_keys=True)}")
    print("FIXED_REGRESSION_EXCLUDED_FROM_TRAINING=true")
    print("MODEL_AUTHORITY_CEILING=ADVISORY_ONLY")


if __name__ == "__main__":
    main()
