#!/usr/bin/env python3
"""Validate reviewed S22 polygons and build a leakage-resistant YOLO dataset."""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from common import (
    CLASS_NAMES,
    NORMAL_CLASS_COUNTS,
    class_counts,
    load_yolo_segments,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=root / "s22_source")
    parser.add_argument("--output", type=Path, default=root / "s22_parts_seg_dataset")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-images", type=int, default=10)
    return parser.parse_args()


def clean_split(output: Path) -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val"):
            path = output / kind / split
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    if not 0.05 <= args.val_ratio <= 0.5:
        raise ValueError("--val-ratio must be between 0.05 and 0.5")
    source = args.source.resolve()
    output = args.output.resolve()
    image_dir = source / "images"
    label_dir = source / "labels"
    review_dir = source / "reviews"
    metadata_dir = source / "metadata"
    samples = []
    for review_path in sorted(review_dir.glob("*.json")):
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("status") != "COMPLETE":
            continue
        stem = review_path.stem
        candidates = list(image_dir.glob(f"{stem}.*"))
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one image for {stem}, found {len(candidates)}")
        image_path = candidates[0]
        label_path = label_dir / f"{stem}.txt"
        if not label_path.is_file():
            raise FileNotFoundError(f"Missing completed label: {label_path}")
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot read {image_path}")
        height, width = image.shape[:2]
        segments = load_yolo_segments(label_path, width, height)
        metadata_path = metadata_dir / f"{stem}.json"
        metadata = (
            json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_path.is_file()
            else {}
        )
        board_state = metadata.get("board_state", "unknown")
        if (
            board_state in ("normal", "print_variation")
            and class_counts(segments) != NORMAL_CLASS_COUNTS
        ):
            raise RuntimeError(
                f"{stem}: normal metadata requires class counts "
                f"{NORMAL_CLASS_COUNTS}, received {class_counts(segments)}"
            )
        samples.append(
            {
                "stem": stem,
                "image": image_path,
                "label": label_path,
                "segments": segments,
                "scene": metadata.get("scene", stem),
                "board_state": board_state,
            }
        )
    if len(samples) < args.min_images:
        raise RuntimeError(
            f"Only {len(samples)} completely reviewed images; need at least {args.min_images}"
        )

    groups: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        groups[sample["scene"]].append(sample)
    group_names = sorted(groups)
    random.Random(args.seed).shuffle(group_names)
    target_val = max(1, round(len(samples) * args.val_ratio))
    val_groups = set()
    val_count = 0
    for name in group_names:
        if val_count >= target_val and val_groups:
            break
        if len(groups) - len(val_groups) <= 1:
            break
        val_groups.add(name)
        val_count += len(groups[name])
    train = [sample for sample in samples if sample["scene"] not in val_groups]
    val = [sample for sample in samples if sample["scene"] in val_groups]
    if not train or not val:
        raise RuntimeError("Need at least two scene groups for train/val separation")

    clean_split(output)
    rows = []
    split_counts = {}
    all_instances = Counter()
    for split, items in (("train", train), ("val", val)):
        instances = Counter()
        for sample in items:
            shutil.copy2(sample["image"], output / "images" / split / sample["image"].name)
            shutil.copy2(sample["label"], output / "labels" / split / sample["label"].name)
            for class_id, _ in sample["segments"]:
                instances[CLASS_NAMES[class_id]] += 1
                all_instances[CLASS_NAMES[class_id]] += 1
            rows.append(
                {
                    "split": split,
                    "image": sample["image"].name,
                    "scene": sample["scene"],
                    "board_state": sample["board_state"],
                    "instances": len(sample["segments"]),
                }
            )
        split_counts[split] = {
            "images": len(items),
            "instances": dict(instances),
        }
    missing_classes = [name for name in CLASS_NAMES if all_instances[name] == 0]
    if missing_classes:
        raise RuntimeError(f"Dataset has no labels for classes: {missing_classes}")

    yaml_lines = [
        f"path: {output}",
        "train: images/train",
        "val: images/val",
        "names:",
    ]
    yaml_lines.extend(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
    yaml_path = output / "s22_parts_seg.yaml"
    yaml_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("split", "image", "scene", "board_state", "instances")
        )
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema_version": 1,
        "camera": "S22 optical still",
        "image_frame": "perspective-rectified 1600x1266 board ROI",
        "split_policy": "scene groups never cross train and val",
        "seed": args.seed,
        "val_ratio_requested": args.val_ratio,
        "counts": split_counts,
        "total_instances": dict(all_instances),
        "yaml": str(yaml_path),
    }
    summary_path = output / "dataset_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"S22_SEG_DATASET={output}")
    print(f"S22_SEG_YAML={yaml_path}")
    print(f"S22_SEG_COUNTS={json.dumps(split_counts, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
