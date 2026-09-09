#!/usr/bin/env python3
"""Freeze the reviewed 2026-09-01 30-image normal S22 acquisition set."""

from __future__ import annotations

import csv
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "runtime/inspection"
OUTPUT = ROOT / "vision_assembly/inspection/datasets/pcb_normal_current_v2"
OLD_DEFECT = ROOT / "vision_assembly/inspection/datasets/pcb_anomaly_v1/test/mixed_defect"
PHASES = (
    ["baseline_start"] * 5
    + ["board_left"] * 2
    + ["board_right"] * 2
    + ["board_up", "board_down", "board_cw", "board_ccw"]
    + ["gpu_tolerance_a", "gpu_tolerance_b"]
    + ["hbm_tolerance_a"] * 2
    + ["hbm_tolerance_b"] * 2
    + ["power_module_tolerance_a", "power_module_tolerance_b"]
    + ["vrm_tolerance_a", "vrm_tolerance_b"]
    + ["inductor_i1_tolerance", "inductor_i2_tolerance"]
    + ["baseline_final"] * 5
)
TEST_INDICES = {5, 7, 9, 13, 19, 30}


def main() -> None:
    images = sorted(SOURCE.glob("s22_inspection_roi_20260901_*.png"))
    images = [item for item in images if item.stem.split("_")[-1] >= "142511"]
    if len(images) != 30:
        raise RuntimeError(f"Expected exactly 30 reviewed images, found {len(images)}")
    if len(PHASES) != 30:
        raise RuntimeError("Internal phase table must contain 30 entries")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    rows = []
    for index, (source, phase) in enumerate(zip(images, PHASES), start=1):
        split = "test/good" if index in TEST_INDICES else "train/good"
        destination = OUTPUT / split / f"normal_current_{index:03d}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        rows.append({
            "index": index,
            "phase": phase,
            "split": split,
            "source": str(source.relative_to(ROOT)),
            "destination": str(destination.relative_to(ROOT)),
            "review_status": "VERIFIED_NORMAL_BY_OPERATOR",
            "smd_policy": "EXCLUDED_AND_ABSENT",
        })
    defect_destination = OUTPUT / "test/mixed_defect"
    defect_destination.mkdir(parents=True, exist_ok=True)
    for source in sorted(OLD_DEFECT.glob("*.png")):
        shutil.copy2(source, defect_destination / source.name)
    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"NORMAL_TRAIN={30 - len(TEST_INDICES)}")
    print(f"NORMAL_TEST={len(TEST_INDICES)}")
    print(f"LEGACY_UNVERIFIED_DEFECT={len(list(defect_destination.glob('*.png')))}")
    print(f"BOARD_DATASET={OUTPUT}")


if __name__ == "__main__":
    main()
