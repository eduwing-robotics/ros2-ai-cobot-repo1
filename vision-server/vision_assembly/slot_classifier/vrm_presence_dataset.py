#!/usr/bin/env python3
"""Archive explicitly labelled S22 VRM-slot crops.

The whole-board segmentation model cannot learn an empty VRM socket when all
training masks describe occupied sockets.  This collector records the exact
empty-slot manifest together with native-resolution fixed-slot crops so a
presence classifier can be trained without guessing labels from an image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[2]
INSPECTION_DIR = PROJECT_DIR / "vision_assembly/inspection"
if str(INSPECTION_DIR) not in sys.path:
    sys.path.insert(0, str(INSPECTION_DIR))

from full_board_inspector import slot_geometry  # noqa: E402
from layout_overrides import apply_component_slot_overrides  # noqa: E402


DEFAULT_IMAGE = PROJECT_DIR / "runtime/inspection/s22_inspection_roi_latest.png"
DEFAULT_OUTPUT = (
    PROJECT_DIR / "vision_assembly/slot_classifier/datasets/vrm_presence_v1"
)
DEFAULT_CONFIG = PROJECT_DIR / "vision_assembly/config/full_board_inspection.json"
EXPECTED_IMAGE_SIZE = (1600, 1266)
OUTPUT_SIZE = (256, 256)
LABELS = {"empty", "present"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_vrm_slots(config_path: Path, image_shape: tuple[int, ...]) -> list[dict]:
    config = _load_json(config_path)
    layout = _load_json(_resolve(config["board_layout"]))
    physical = _load_json(_resolve(config["physical_board"]))
    layout, _ = apply_component_slot_overrides(layout, physical)
    board = layout["board"]["size_mm"]
    board_size = (float(board["x"]), float(board["y"]))
    return [
        {
            "slot_id": str(placement["slot_id"]),
            "geometry": slot_geometry(
                placement,
                image_shape,
                board_size,
                config["coordinate_mapping"],
            ),
        }
        for placement in layout["placements"]
        if placement["component_type"] == "VRM"
    ]


def crop_slot(
    image: np.ndarray,
    geometry: tuple[float, float, float, float],
    margin_ratio: float,
) -> np.ndarray:
    center_x, center_y, size_x, size_y = geometry
    width = max(24, int(round(size_x * (1.0 + 2.0 * margin_ratio))))
    height = max(24, int(round(size_y * (1.0 + 2.0 * margin_ratio))))
    crop = cv2.getRectSubPix(
        image,
        (width, height),
        (float(center_x), float(center_y)),
    )
    return cv2.resize(crop, OUTPUT_SIZE, interpolation=cv2.INTER_CUBIC)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Save all five VRM slot crops with an explicit present/empty label. "
            "Every unlisted VRM slot is recorded as present."
        )
    )
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--empty",
        nargs="*",
        default=None,
        metavar="SLOT_ID",
        help="exact empty VRM slots, for example: --empty vrm_05",
    )
    parser.add_argument(
        "--all-present",
        action="store_true",
        help="confirm that all five VRM slots contain a correctly seated VRM",
    )
    parser.add_argument(
        "--scene",
        help="physical scene identifier; generated from the capture time by default",
    )
    parser.add_argument("--margin-ratio", type=float, default=0.24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.all_present == (args.empty is not None):
        raise RuntimeError("Choose exactly one of --all-present or --empty SLOT_ID...")

    image_path = args.image.expanduser().resolve()
    output = args.output.expanduser().resolve()
    config_path = args.config.expanduser().resolve()
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Cannot decode S22 inspection ROI: {image_path}")
    actual_size = (image.shape[1], image.shape[0])
    if actual_size != EXPECTED_IMAGE_SIZE:
        raise RuntimeError(
            f"Expected rectified ROI {EXPECTED_IMAGE_SIZE}, got {actual_size}: {image_path}"
        )

    slots = load_vrm_slots(config_path, image.shape)
    known_slots = {slot["slot_id"] for slot in slots}
    empty_slots = set(args.empty or [])
    invalid = sorted(empty_slots - known_slots)
    if invalid:
        raise RuntimeError(f"Unknown VRM slots: {invalid}; valid={sorted(known_slots)}")

    source_hash = image_sha256(image_path)
    manifest_path = output / "manifest.jsonl"
    if manifest_path.is_file():
        for row in manifest_path.read_text(encoding="utf-8").splitlines():
            if row and json.loads(row).get("source_sha256") == source_hash:
                raise RuntimeError(
                    "This exact ROI was already archived. Capture a fresh image after "
                    "changing or reseating the physical VRM state."
                )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    scene_id = args.scene or f"vrm_scene_{timestamp}"
    source_dir = output / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_copy = source_dir / f"{timestamp}.png"
    if not cv2.imwrite(str(source_copy), image, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
        raise RuntimeError(f"Cannot save source image: {source_copy}")

    preview = image.copy()
    records = []
    for slot in slots:
        slot_id = slot["slot_id"]
        label = "empty" if slot_id in empty_slots else "present"
        if label not in LABELS:
            raise AssertionError(label)
        crop = crop_slot(image, slot["geometry"], args.margin_ratio)
        crop_dir = output / "crops" / label
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop_path = crop_dir / f"{timestamp}__{slot_id}.png"
        if not cv2.imwrite(str(crop_path), crop, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
            raise RuntimeError(f"Cannot save VRM crop: {crop_path}")

        center_x, center_y, size_x, size_y = slot["geometry"]
        color = (30, 40, 245) if label == "empty" else (55, 210, 75)
        half_w = size_x * (0.5 + args.margin_ratio)
        half_h = size_y * (0.5 + args.margin_ratio)
        p0 = (int(round(center_x - half_w)), int(round(center_y - half_h)))
        p1 = (int(round(center_x + half_w)), int(round(center_y + half_h)))
        cv2.rectangle(preview, p0, p1, color, 3, cv2.LINE_AA)
        cv2.putText(
            preview,
            f"{slot_id}:{label}",
            (p0[0], max(24, p0[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
        records.append(
            {
                "schema_version": 1,
                "scene_id": scene_id,
                "captured_at": timestamp,
                "source_image": str(source_copy.relative_to(output)),
                "source_sha256": source_hash,
                "slot_id": slot_id,
                "label": label,
                "crop_image": str(crop_path.relative_to(output)),
                "image_frame": "S22 rectified board ROI 1600x1266",
                "margin_ratio": args.margin_ratio,
                "robot_command_sent": False,
                "conveyor_command_sent": False,
            }
        )

    preview_dir = output / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"{timestamp}.jpg"
    if not cv2.imwrite(str(preview_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 94]):
        raise RuntimeError(f"Cannot save labelled preview: {preview_path}")
    with manifest_path.open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    counts = {label: sum(row["label"] == label for row in records) for label in LABELS}
    print(f"VRM_PRESENCE_SCENE={scene_id}")
    print(f"VRM_PRESENCE_COUNTS={json.dumps(counts, sort_keys=True)}")
    print(f"VRM_PRESENCE_PREVIEW={preview_path}")
    print(f"VRM_PRESENCE_MANIFEST={manifest_path}")
    print("DATA_AUTHORITY=EXPLICIT_USER_CONTROLLED_LABEL")


if __name__ == "__main__":
    main()

