#!/usr/bin/env python3
"""Shared definitions for the S22 semiconductor-part segmentation dataset."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import cv2
import numpy as np


CLASS_NAMES = (
    "gpu",
    "hbm",
    "power_module",
    "vrm",
    "inductor",
    "smd_capacitor",
)
CLASS_COLORS = (
    (255, 118, 20),
    (232, 45, 210),
    (0, 172, 255),
    (45, 45, 245),
    (0, 220, 220),
    (55, 210, 75),
)
NORMAL_CLASS_COUNTS = {
    "gpu": 1,
    "hbm": 8,
    "power_module": 4,
    "vrm": 5,
    "inductor": 2,
    "smd_capacitor": 5,
}


def polygon_area(points: np.ndarray) -> float:
    return abs(float(cv2.contourArea(np.asarray(points, dtype=np.float32))))


def load_yolo_segments(
    path: Path, width: int, height: int
) -> list[tuple[int, np.ndarray]]:
    segments: list[tuple[int, np.ndarray]] = []
    if not path.is_file():
        return segments
    scale = np.asarray((width, height), dtype=np.float32)
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 7 or len(fields) % 2 == 0:
            raise ValueError(f"{path}:{line_number}: invalid YOLO segment row")
        class_id = int(fields[0])
        if not 0 <= class_id < len(CLASS_NAMES):
            raise ValueError(f"{path}:{line_number}: invalid class {class_id}")
        values = np.asarray([float(value) for value in fields[1:]], np.float32)
        if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
            raise ValueError(f"{path}:{line_number}: coordinate outside [0, 1]")
        points = values.reshape(-1, 2) * scale
        if len(points) < 3 or polygon_area(points) < 1.0:
            raise ValueError(f"{path}:{line_number}: degenerate polygon")
        segments.append((class_id, points))
    return segments


def save_yolo_segments(
    path: Path,
    segments: list[tuple[int, np.ndarray]],
    width: int,
    height: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scale = np.asarray((width, height), dtype=np.float32)
    rows = []
    for class_id, points in segments:
        normalized = np.clip(np.asarray(points, np.float32) / scale, 0.0, 1.0)
        values = " ".join(f"{value:.8f}" for value in normalized.reshape(-1))
        rows.append(f"{class_id} {values}")
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def class_counts(segments: list[tuple[int, np.ndarray]]) -> dict[str, int]:
    counts = Counter(class_id for class_id, _ in segments)
    return {name: counts.get(class_id, 0) for class_id, name in enumerate(CLASS_NAMES)}
