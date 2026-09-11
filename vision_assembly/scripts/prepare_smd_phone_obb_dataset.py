#!/usr/bin/env python3
"""Build an SMD OBB dataset from high-resolution phone photographs.

The saturated brown body provides the stable seed. Its long axis is extended
to include both white terminals, which is the axis used by the gripper.
Source photographs are never modified.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


VAL_STEMS = {"IMG_2302", "IMG_2303", "IMG_2313", "IMG_2314", "IMG_2315"}


def ordered_box(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, np.float32)
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    points = points[np.argsort(angles)]
    return np.roll(points, -int(np.argmin(points[:, 0] + points[:, 1])), axis=0)


def body_mask(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv, np.array([3, 30, 55], np.uint8), np.array([42, 190, 245], np.uint8)
    )
    roi = np.zeros_like(mask)
    roi[int(0.20 * height):int(0.67 * height),
        int(0.20 * width):int(0.77 * width)] = 255
    mask = cv2.bitwise_and(mask, roi)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))


def component_points(mask: np.ndarray) -> list[np.ndarray]:
    components = []
    for contour in cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )[0]:
        area = cv2.contourArea(contour)
        x, y, width, height = cv2.boundingRect(contour)
        if not (1000 < area < 22000 and 25 < width < 240 and 25 < height < 240):
            continue
        local = np.zeros((height, width), np.uint8)
        shifted = contour - np.array([[[x, y]]], dtype=contour.dtype)
        cv2.drawContours(local, [shifted], -1, 255, cv2.FILLED)
        yy, xx = np.nonzero(local)
        components.append(
            np.column_stack([xx + x, yy + y]).astype(np.float32)
        )

    if len(components) == 4:
        areas = np.asarray([len(points) for points in components], float)
        merged_index = int(np.argmax(areas))
        others = np.delete(areas, merged_index)
        if areas[merged_index] < 1.65 * float(np.median(others)):
            raise RuntimeError("four bodies found but no clearly merged component")
        merged = components.pop(merged_index)
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
            80,
            0.2,
        )
        _compactness, labels, _centers = cv2.kmeans(
            merged, 2, None, criteria, 20, cv2.KMEANS_PP_CENTERS
        )
        components.extend(
            [merged[labels[:, 0] == index] for index in range(2)]
        )

    if len(components) != 5:
        raise RuntimeError(f"expected five SMD bodies, got {len(components)}")
    return components


def terminal_box(
    points: np.ndarray, long_scale: float, short_scale: float
) -> np.ndarray:
    center, (width, height), angle = cv2.minAreaRect(points)
    if min(width, height) < 20.0:
        raise RuntimeError("SMD body rectangle is too small")
    if width >= height:
        width *= long_scale
        height *= short_scale
    else:
        height *= long_scale
        width *= short_scale
    return ordered_box(cv2.boxPoints((center, (width, height), angle)))


def review_image(
    image: np.ndarray, boxes: list[np.ndarray], stem: str
) -> np.ndarray:
    review = image.copy()
    ordered = sorted(boxes, key=lambda item: float(item[:, 1].mean()))
    for index, box in enumerate(ordered, 1):
        polygon = np.rint(box).astype(np.int32)
        center = np.rint(box.mean(axis=0)).astype(int)
        cv2.polylines(
            review, [polygon], True, (0, 255, 0), 12, cv2.LINE_AA
        )
        cv2.putText(
            review,
            str(index),
            tuple(center + [15, -15]),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (0, 255, 255),
            4,
            cv2.LINE_AA,
        )
    cv2.putText(
        review,
        stem,
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.4,
        (0, 0, 255),
        4,
        cv2.LINE_AA,
    )
    return cv2.resize(review, (378, 504), interpolation=cv2.INTER_AREA)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", type=Path, default=Path.home() / "Desktop/학습"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "datasets/smd_obb_phone_pilot04",
    )
    parser.add_argument("--long-scale", type=float, default=1.45)
    parser.add_argument("--short-scale", type=float, default=1.08)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(
            f"refusing to overwrite existing dataset: {args.output}"
        )
    paths = sorted(args.source.glob("*.jpg"))
    if len(paths) != 30:
        raise RuntimeError(
            f"expected 30 phone photographs, got {len(paths)}"
        )

    for split in ("train", "val"):
        (args.output / "images" / split).mkdir(parents=True)
        (args.output / "labels" / split).mkdir(parents=True)
    review_dir = args.output / "label_review"
    review_dir.mkdir()
    summary_rows = []
    contact_cells = []

    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            raise RuntimeError(f"cannot read {path}")
        height, width = image.shape[:2]
        points = component_points(body_mask(image))
        boxes = [
            terminal_box(item, args.long_scale, args.short_scale)
            for item in points
        ]
        for box in boxes:
            limit = np.array([width, height], np.float32)
            if np.any(box < 0) or np.any(box >= limit):
                raise RuntimeError(
                    f"expanded label leaves image bounds: {path.name}"
                )
        split = "val" if path.stem in VAL_STEMS else "train"
        shutil.copy2(path, args.output / "images" / split / path.name)
        rows = []
        for box in boxes:
            normalized = box / np.array([width, height], np.float32)
            values = " ".join(
                f"{value:.7f}" for value in normalized.reshape(-1)
            )
            rows.append("0 " + values)
        label_path = args.output / "labels" / split / f"{path.stem}.txt"
        label_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        review = review_image(image, boxes, path.stem)
        cv2.imwrite(
            str(review_dir / path.name),
            review,
            [cv2.IMWRITE_JPEG_QUALITY, 92],
        )
        contact_cells.append(review)
        summary_rows.append(
            {"file": path.name, "split": split, "instances": len(boxes)}
        )

    rows = [
        np.hstack(contact_cells[index:index + 6])
        for index in range(0, len(contact_cells), 6)
    ]
    contact = np.vstack(rows)
    cv2.imwrite(
        str(args.output / "label_review_contact.jpg"),
        contact,
        [cv2.IMWRITE_JPEG_QUALITY, 92],
    )
    dataset_yaml = (
        f"path: {args.output.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: smd_capacitor\n"
    )
    (args.output / "dataset.yaml").write_text(
        dataset_yaml, encoding="utf-8"
    )
    summary = {
        "schema_version": 1,
        "source": str(args.source.resolve()),
        "source_images": len(paths),
        "train_images": sum(
            row["split"] == "train" for row in summary_rows
        ),
        "val_images": sum(row["split"] == "val" for row in summary_rows),
        "instances": sum(row["instances"] for row in summary_rows),
        "label_source": (
            "brown-body HSV components, long axis extended "
            "to include both white terminals"
        ),
        "long_scale": args.long_scale,
        "short_scale": args.short_scale,
        "validation_split_policy": (
            "held-out physical arrangements IMG_2302-2303 "
            "and IMG_2313-2315"
        ),
        "manual_review_required": True,
        "files": summary_rows,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
