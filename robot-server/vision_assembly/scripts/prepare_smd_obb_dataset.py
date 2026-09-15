#!/usr/bin/env python3
"""Create an SMD-only YOLO OBB dataset from denoised close-view masks."""
import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

from detect_smd_section import register_clean_section
from prepare_smd_close_finetune import find_smd_polygons, variant


def ordered_box(polygon):
    points = cv2.boxPoints(cv2.minAreaRect(polygon.astype(np.float32)))
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    points = points[np.argsort(angles)]
    start = int(np.argmin(points[:, 0] + points[:, 1]))
    return np.roll(points, -start, axis=0)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=Path, default=root / "data/smd_section_live_frames_1920")
    parser.add_argument("--config", type=Path, default=root / "config/smd_section_view.json")
    parser.add_argument("--output", type=Path, default=root / "datasets/smd_obb")
    parser.add_argument("--variants", type=int, default=8)
    parser.add_argument("--fixed-polygon-at-verified-pose", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    width, height = map(int, config["canonical_size"])
    destination = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    rectified = []
    paths = sorted(args.frames.glob("*.jpg"))
    if len(paths) != 8:
        raise RuntimeError(f"expected 8 source frames, got {len(paths)}")
    for path in paths:
        image = cv2.imread(str(path))
        try:
            section, _ = register_clean_section(image, config, args.config)
        except RuntimeError:
            if not args.fixed_polygon_at_verified_pose:
                raise
            source_size = np.asarray(config.get("source_image_size", [image.shape[1], image.shape[0]]), float)
            scale = np.asarray([image.shape[1], image.shape[0]], np.float32) / source_size.astype(np.float32)
            section = np.asarray(config["section_polygon_pixel"], np.float32) * scale
        transform = cv2.getPerspectiveTransform(section.astype(np.float32), destination)
        rectified.append(cv2.warpPerspective(image, transform, (width, height), flags=cv2.INTER_CUBIC))
    median = np.median(np.stack(rectified), axis=0).astype(np.uint8)
    polygons, _ = find_smd_polygons(median)
    boxes = [ordered_box(polygon) for _, polygon, _ in polygons]
    if args.output.exists():
        shutil.rmtree(args.output)
    for split in ("train", "val"):
        (args.output / f"images/{split}").mkdir(parents=True)
        (args.output / f"labels/{split}").mkdir(parents=True)
    angles = []
    for polygon in [item[1] for item in polygons]:
        (_, _), (rw, rh), angle = cv2.minAreaRect(polygon.astype(np.float32))
        if rh > rw:
            angle += 90.0
        angles.append(round((float(angle) + 90.0) % 180.0 - 90.0, 4))
    for frame_index, image in enumerate(rectified, 1):
        split = "val" if frame_index <= 2 else "train"
        for variant_index in range(args.variants):
            stem = f"frame_{frame_index:02d}_v{variant_index:02d}"
            cv2.imwrite(str(args.output / f"images/{split}/{stem}.jpg"), variant(image, variant_index),
                        [cv2.IMWRITE_JPEG_QUALITY, 94])
            rows = []
            for box in boxes:
                normalized = box / np.array([width, height], dtype=np.float32)
                rows.append("0 " + " ".join(f"{value:.6f}" for value in normalized.reshape(-1)))
            (args.output / f"labels/{split}/{stem}.txt").write_text("\n".join(rows) + "\n")
    (args.output / "dataset.yaml").write_text(
        f"path: {args.output.resolve()}\ntrain: images/train\nval: images/val\n\nnames:\n  0: smd_capacitor\n")
    summary = {"schema_version": 1, "source_frames": 8, "train_images": 48,
               "val_images": 16, "instances_per_image": 10,
               "median_reference_angles_deg": angles, "label_source": "8-frame median registered mask"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    cv2.imwrite(str(args.output / "median_reference.jpg"), median, [cv2.IMWRITE_JPEG_QUALITY, 96])
    review = median.copy()
    for index, (box, angle) in enumerate(zip(boxes, angles), 1):
        polygon = np.rint(box).astype(np.int32)
        center = np.rint(box.mean(axis=0)).astype(int)
        cv2.polylines(review, [polygon], True, (0, 200, 0), 3, cv2.LINE_AA)
        cv2.putText(review, f"{index}: {angle:+.1f} deg", tuple(center + [10, -10]),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(args.output / "label_review.jpg"), review, [cv2.IMWRITE_JPEG_QUALITY, 96])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
