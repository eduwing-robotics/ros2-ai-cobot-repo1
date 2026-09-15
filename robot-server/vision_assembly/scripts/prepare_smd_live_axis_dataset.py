#!/usr/bin/env python3
"""Create real-camera OBB training samples from one operator-verified SMD view."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def ordered_box(points: np.ndarray) -> np.ndarray:
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    points = points[np.argsort(angles)]
    return np.roll(points, -int(np.argmin(points[:, 0] + points[:, 1])), axis=0)


def terminal_box(endpoints: np.ndarray, padding: float, short_side: float) -> np.ndarray:
    first, second = np.asarray(endpoints, dtype=np.float32)
    axis = second - first
    length = float(np.linalg.norm(axis))
    if length < 15.0:
        raise RuntimeError("terminal endpoints are too close")
    direction = axis / length
    normal = np.asarray([-direction[1], direction[0]], dtype=np.float32)
    center = (first + second) * 0.5
    half_long = (length + padding) * 0.5
    half_short = short_side * 0.5
    return ordered_box(np.asarray([
        center - direction * half_long - normal * half_short,
        center + direction * half_long - normal * half_short,
        center + direction * half_long + normal * half_short,
        center - direction * half_long + normal * half_short,
    ], dtype=np.float32))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, default=root / "data/smd_axis_model_live_rectified.jpg")
    parser.add_argument("--manual-axes", type=Path, default=root / "data/smd_manual_axes_set1.json")
    parser.add_argument("--output", type=Path, default=root / "datasets/smd_obb_live_axis_set1")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--terminal-padding-px", type=float, default=8.0)
    parser.add_argument("--short-side-px", type=float, default=32.0)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite existing dataset: {args.output}")
    image = cv2.imread(str(args.image))
    if image is None:
        raise RuntimeError(f"cannot read image: {args.image}")
    height, width = image.shape[:2]
    payload = json.loads(args.manual_axes.read_text(encoding="utf-8"))
    if list(map(int, payload["canonical_size"])) != [width, height]:
        raise RuntimeError("manual-axis and rectified image sizes disagree")
    boxes = [
        terminal_box(np.asarray(part["terminal_endpoints_canonical_pixel"]),
                     args.terminal_padding_px, args.short_side_px)
        for part in payload["parts"]
    ]
    if len(boxes) != 5:
        raise RuntimeError(f"expected five verified SMD axes, got {len(boxes)}")

    image_dir = args.output / "images/train"
    label_dir = args.output / "labels/train"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    rng = np.random.default_rng(9032026)
    reviews = []
    for index in range(args.samples):
        dx = int(rng.integers(-2, 3))
        dy = int(rng.integers(-2, 3))
        affine = np.float32([[1, 0, dx], [0, 1, dy]])
        sample = cv2.warpAffine(image, affine, (width, height),
                                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
        alpha = float(rng.uniform(0.88, 1.12))
        beta = float(rng.uniform(-9.0, 9.0))
        sample = cv2.convertScaleAbs(sample, alpha=alpha, beta=beta)
        if index % 3 == 1:
            sample = cv2.GaussianBlur(sample, (3, 3), 0.55)
        if index % 4 == 2:
            noise = rng.normal(0.0, 1.8, sample.shape).astype(np.float32)
            sample = np.clip(sample.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        shifted = [box + np.asarray([dx, dy], dtype=np.float32) for box in boxes]
        stem = f"live_axis_{index:02d}"
        cv2.imwrite(str(image_dir / f"{stem}.jpg"), sample,
                    [cv2.IMWRITE_JPEG_QUALITY, 94])
        rows = []
        for box in shifted:
            normalized = box / np.asarray([width, height], dtype=np.float32)
            rows.append("0 " + " ".join(f"{value:.7f}" for value in normalized.reshape(-1)))
        (label_dir / f"{stem}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
        if index < 6:
            review = sample.copy()
            for part_index, box in enumerate(shifted, 1):
                polygon = np.rint(box).astype(np.int32)
                cv2.polylines(review, [polygon], True, (0, 255, 0), 3, cv2.LINE_AA)
                center = np.rint(box.mean(axis=0)).astype(int)
                cv2.putText(review, str(part_index), tuple(center + [8, -8]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
            reviews.append(cv2.resize(review, (600, 360), interpolation=cv2.INTER_AREA))
    cv2.imwrite(str(args.output / "label_review.jpg"), np.vstack(reviews),
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    (args.output / "dataset.yaml").write_text(
        f"path: {args.output.resolve()}\ntrain: images/train\nval: images/train\n\n"
        "names:\n  0: smd_capacitor\n", encoding="utf-8")
    summary = {
        "schema_version": 1,
        "source_image": str(args.image.resolve()),
        "manual_axes": str(args.manual_axes.resolve()),
        "samples": args.samples,
        "instances": args.samples * len(boxes),
        "terminal_padding_px": args.terminal_padding_px,
        "short_side_px": args.short_side_px,
        "usage": "training_only; never use these near-duplicate samples for validation",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
