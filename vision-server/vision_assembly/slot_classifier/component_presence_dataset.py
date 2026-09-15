#!/usr/bin/env python3
"""Archive explicitly labelled PRESENT/EMPTY crops for 20 non-VRM slots."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import cv2


PROJECT_DIR = Path(__file__).resolve().parents[2]
HYBRID_DIR = PROJECT_DIR / "vision_assembly/hybrid_inspection"
if str(HYBRID_DIR) not in sys.path:
    sys.path.insert(0, str(HYBRID_DIR))

from preprocessor_and_cropper import FixedSlotCropper  # noqa: E402
from component_presence_common import (  # noqa: E402
    PRESENCE_CROP_PIPELINE,
    PRESENCE_MARGIN_BY_KEY,
    crop_component_presence_slot,
)
from vrm_presence_dataset import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_IMAGE,
    EXPECTED_IMAGE_SIZE,
    image_sha256,
)


DEFAULT_OUTPUT = (
    PROJECT_DIR / "vision_assembly/slot_classifier/datasets/component_presence_v1"
)
COLORS = {"empty": (45, 55, 245), "present": (60, 210, 80)}


def presence_labels(slot_ids: set[str], empty_slots: set[str]) -> dict[str, str]:
    invalid = sorted(empty_slots - slot_ids)
    if invalid:
        raise ValueError(
            f"Unknown non-VRM slots: {invalid}; valid={sorted(slot_ids)}"
        )
    return {
        slot_id: "empty" if slot_id in empty_slots else "present"
        for slot_id in sorted(slot_ids)
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Save 20 registered S22 non-VRM slot crops as PRESENT/EMPTY. "
            "Unlisted slots are PRESENT only after explicit confirmation."
        )
    )
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--empty", nargs="*", default=[], metavar="SLOT_ID")
    parser.add_argument(
        "--all-present",
        action="store_true",
        help="explicitly confirm that all 20 non-VRM slots contain a component",
    )
    parser.add_argument("--scene")
    parser.add_argument(
        "--illumination", choices=("ambient", "flash"), default="ambient"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.all_present and args.empty:
        raise RuntimeError("--all-present cannot be combined with --empty")
    if not args.all_present and not args.empty:
        raise RuntimeError("Provide --empty SLOT_ID..., or explicitly use --all-present")
    if args.illumination != "ambient":
        raise RuntimeError("Production presence collection is fixed to ambient/flash-off")

    image_path = args.image.expanduser().resolve()
    output = args.output.expanduser().resolve()
    config_path = args.config.expanduser().resolve()
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Cannot decode S22 inspection ROI: {image_path}")
    if (image.shape[1], image.shape[0]) != EXPECTED_IMAGE_SIZE:
        raise RuntimeError(
            f"Expected rectified ROI {EXPECTED_IMAGE_SIZE}, got "
            f"{(image.shape[1], image.shape[0])}: {image_path}"
        )

    cropper = FixedSlotCropper(config_path)
    registered = cropper.register(image)
    minimum_alignment = float(cropper.config["global_alignment"]["minimum_score"])
    if (
        registered.alignment_reason != "OK"
        or registered.alignment_score < minimum_alignment
    ):
        raise RuntimeError(
            "Presence capture registration is not trustworthy: "
            f"reason={registered.alignment_reason}, "
            f"score={registered.alignment_score:.4f}, "
            f"minimum={minimum_alignment:.4f}"
        )
    slots = [
        slot
        for slot in cropper.fixed_slots(registered.image_bgr)
        if slot.component_type != "VRM"
    ]
    if len(slots) != 20:
        raise RuntimeError(f"Expected 20 non-VRM slots, got {len(slots)}")
    labels = presence_labels({slot.slot_id for slot in slots}, set(args.empty))

    source_hash = image_sha256(image_path)
    manifest_path = output / "manifest.jsonl"
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if line and json.loads(line).get("source_sha256") == source_hash:
                raise RuntimeError(
                    "This exact ROI was already archived; capture a fresh physical scene."
                )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    scene_id = args.scene or f"component_presence_scene_{timestamp}"
    source_dir = output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_copy = source_dir / f"{timestamp}.png"
    if not cv2.imwrite(str(source_copy), image, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
        raise RuntimeError(f"Cannot save source image: {source_copy}")

    preview = registered.image_bgr.copy()
    records = []
    for slot in slots:
        label = labels[slot.slot_id]
        crop = crop_component_presence_slot(
            registered.image_bgr, slot.geometry, slot.component_key
        )
        crop_dir = output / "crops" / slot.component_key / label
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop_path = crop_dir / f"{timestamp}__{slot.slot_id}.png"
        if not cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
            raise RuntimeError(f"Cannot save presence crop: {crop_path}")

        center_x, center_y, size_x, size_y = slot.geometry
        margin = PRESENCE_MARGIN_BY_KEY[slot.component_key]
        half_w = size_x * (0.5 + margin)
        half_h = size_y * (0.5 + margin)
        p0 = (int(round(center_x - half_w)), int(round(center_y - half_h)))
        p1 = (int(round(center_x + half_w)), int(round(center_y + half_h)))
        color = COLORS[label]
        cv2.rectangle(preview, p0, p1, color, 2, cv2.LINE_AA)
        cv2.putText(
            preview,
            f"{slot.slot_id}:{label}",
            (p0[0], max(20, p0[1] - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )
        records.append(
            {
                "schema_version": 1,
                "task": "non_vrm_fixed_slot_presence",
                "scene_id": scene_id,
                "captured_at": timestamp,
                "source_image": str(source_copy.relative_to(output)),
                "source_sha256": source_hash,
                "slot_id": slot.slot_id,
                "component_type": slot.component_type,
                "component_key": slot.component_key,
                "label": label,
                "crop_image": str(crop_path.relative_to(output)),
                "illumination": args.illumination,
                "source_image_frame": "S22 rectified board ROI 1600x1266",
                "crop_image_frame": "globally registered board fixed slot",
                "crop_pipeline": PRESENCE_CROP_PIPELINE,
                "margin_ratio": PRESENCE_MARGIN_BY_KEY[slot.component_key],
                "alignment_score": registered.alignment_score,
                "alignment_reason": registered.alignment_reason,
                "label_scope": "presence_only_orientation_and_surface_ignored",
                "label_authority": "EXPLICIT_USER_CONTROLLED",
                "robot_command_sent": False,
                "conveyor_command_sent": False,
            }
        )

    preview_dir = output / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"{timestamp}.jpg"
    if not cv2.imwrite(str(preview_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise RuntimeError(f"Cannot save presence preview: {preview_path}")
    with manifest_path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    counts = {
        label: sum(record["label"] == label for record in records)
        for label in ("empty", "present")
    }
    print(f"COMPONENT_PRESENCE_SCENE={scene_id}")
    print(f"COMPONENT_PRESENCE_COUNTS={json.dumps(counts, sort_keys=True)}")
    print(f"COMPONENT_PRESENCE_PREVIEW={preview_path}")
    print(f"COMPONENT_PRESENCE_MANIFEST={manifest_path}")
    print("DATA_AUTHORITY=EXPLICIT_USER_CONTROLLED_LABEL")
    print("ROBOT_COMMAND_SENT=false")
    print("CONVEYOR_COMMAND_SENT=false")


if __name__ == "__main__":
    main()
