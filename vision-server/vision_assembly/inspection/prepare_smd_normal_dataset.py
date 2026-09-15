#!/usr/bin/env python3
"""Freeze the reviewed 53-image SMD-present normal acquisition."""

from __future__ import annotations

import csv
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "runtime/inspection"
OUTPUT = ROOT / "vision_assembly/inspection/datasets/pcb_smd_normal_v3"
OLD_DEFECT = ROOT / "vision_assembly/inspection/datasets/pcb_anomaly_v1/test/mixed_defect"
TEST_INDICES = {5, 7, 9, 11, 13, 15, 17, 19, 21, 30, 38, 43, 49, 53}


def phase(index: int) -> str:
    ranges = (
        (1, 5, "baseline_start"), (6, 7, "board_left"),
        (8, 9, "board_right"), (10, 10, "board_up"),
        (11, 11, "board_down"), (12, 13, "smd_s1_tolerance"),
        (14, 15, "smd_s2_tolerance"), (16, 17, "smd_s3_tolerance"),
        (18, 19, "smd_s4_tolerance"), (20, 21, "smd_s5_tolerance"),
        (22, 23, "gpu_tolerance"), (24, 30, "hbm_tolerance"),
        (31, 38, "power_module_tolerance"), (39, 43, "vrm_tolerance"),
        (44, 49, "inductor_tolerance"), (50, 53, "baseline_final"),
    )
    return next(name for first, last, name in ranges if first <= index <= last)


def main() -> None:
    images = sorted(SOURCE.glob("s22_inspection_roi_20260901_*.png"))
    images = [item for item in images if item.stem.split("_")[-1] >= "155058"]
    if len(images) != 53:
        raise RuntimeError(f"Expected exactly 53 reviewed images, found {len(images)}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    rows = []
    for index, source in enumerate(images, start=1):
        split = "test/good" if index in TEST_INDICES else "train/good"
        destination = OUTPUT / split / f"normal_smd_{index:03d}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        rows.append({
            "index": index, "phase": phase(index), "split": split,
            "source": str(source.relative_to(ROOT)),
            "destination": str(destination.relative_to(ROOT)),
            "review_status": "VERIFIED_NORMAL_BY_OPERATOR",
            "smd_policy": "INCLUDED_ALL_5_PRESENT",
        })
    defect_dir = OUTPUT / "test/mixed_defect"
    defect_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(OLD_DEFECT.glob("*.png")):
        shutil.copy2(source, defect_dir / source.name)
    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"NORMAL_TRAIN={53-len(TEST_INDICES)}")
    print(f"NORMAL_TEST={len(TEST_INDICES)}")
    print(f"BOARD_DATASET={OUTPUT}")


if __name__ == "__main__":
    main()
