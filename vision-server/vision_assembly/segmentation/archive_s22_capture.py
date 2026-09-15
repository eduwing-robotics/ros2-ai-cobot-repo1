#!/usr/bin/env python3
"""Archive one fresh, rectified S22 PCB image for segmentation labelling."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import cv2

from common import NORMAL_CLASS_COUNTS


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if not cleaned:
        raise ValueError("scene must contain at least one letter or digit")
    return cleaned


def parse_args() -> argparse.Namespace:
    project = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=project / "runtime/inspection/s22_inspection_roi_latest.png",
    )
    parser.add_argument(
        "--source-metadata",
        type=Path,
        default=project / "runtime/inspection/s22_inspection_roi_latest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "s22_source",
    )
    parser.add_argument("--scene", required=True)
    parser.add_argument(
        "--board-state",
        choices=("normal", "controlled_defect", "print_variation", "unknown"),
        required=True,
    )
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--notes", default="")
    parser.add_argument("--allow-duplicate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"S22 rectified ROI does not exist: {source}")
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot decode S22 ROI: {source}")
    height, width = image.shape[:2]
    if (width, height) != (1600, 1266):
        raise RuntimeError(
            f"Expected the canonical 1600x1266 S22 ROI, received {width}x{height}"
        )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    digest = file_sha256(source)
    source_metadata = {}
    if args.source_metadata.is_file():
        source_metadata = json.loads(args.source_metadata.read_text(encoding="utf-8"))
    expected_count = args.expected_count
    if expected_count is None and args.board_state in ("normal", "print_variation"):
        expected_count = sum(NORMAL_CLASS_COUNTS.values())
    if expected_count is not None and not 0 <= expected_count <= 25:
        raise ValueError("--expected-count must be between 0 and 25")
    if (
        args.board_state in ("normal", "print_variation")
        and expected_count != 25
    ):
        raise ValueError("normal and print_variation captures must contain 25 visible parts")

    output = args.output.resolve()
    image_dir = output / "images"
    metadata_dir = output / "metadata"
    image_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    existing_hashes = set()
    for item in metadata_dir.glob("*.json"):
        try:
            existing_hashes.add(json.loads(item.read_text(encoding="utf-8"))["sha256"])
        except (KeyError, json.JSONDecodeError):
            continue
    if digest in existing_hashes and not args.allow_duplicate:
        raise RuntimeError(
            "This exact ROI is already archived; take a fresh photo or pass "
            "--allow-duplicate intentionally."
        )

    scene = slug(args.scene)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = f"s22seg_{timestamp}_{scene}"
    destination = image_dir / f"{stem}.png"
    if not cv2.imwrite(
        str(destination), image, [cv2.IMWRITE_PNG_COMPRESSION, 2]
    ):
        raise RuntimeError(f"Cannot save segmentation source: {destination}")

    metadata = {
        "schema_version": 1,
        "status": "UNLABELED",
        "camera": "S22 optical still",
        "image": str(destination),
        "source_roi": str(source),
        "source_roi_metadata": str(args.source_metadata.resolve()),
        "sha256": digest,
        "width": width,
        "height": height,
        "sharpness_laplacian_variance": sharpness,
        "scene": scene,
        "board_state": args.board_state,
        "expected_visible_instances": expected_count,
        "notes": args.notes,
        "source_capture": source_metadata,
    }
    metadata_path = metadata_dir / f"{stem}.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (output / "manifest.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(metadata, ensure_ascii=False) + "\n")
    print(f"S22_SEG_IMAGE={destination}")
    print(f"S22_SEG_METADATA={metadata_path}")
    print(f"S22_SEG_SHARPNESS={sharpness:.2f}")


if __name__ == "__main__":
    main()
