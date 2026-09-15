#!/usr/bin/env python3
"""Build a strict golden-board dataset from the reviewed 53-image acquisition."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vision_assembly/inspection/datasets/pcb_smd_normal_v3"
OUTPUT = ROOT / "vision_assembly/inspection/datasets/pcb_whole_strict_v5"
STRICT_TRAIN = {1, 2, 3, 4, 6, 8, 10, 50, 51, 52}
STRICT_TEST = {5, 7, 9, 11, 53}


def main() -> None:
    rows = list(csv.DictReader((SOURCE / "manifest.csv").open(encoding="utf-8")))
    if len(rows) != 53:
        raise RuntimeError(f"Expected 53 reviewed records, found {len(rows)}")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    manifest = []
    for row in rows:
        index = int(row["index"])
        source = ROOT / row["destination"]
        if index in STRICT_TRAIN:
            group, policy = "train/good", "STRICT_GOLDEN_NORMAL"
        elif index in STRICT_TEST:
            group, policy = "test/good", "STRICT_GOLDEN_NORMAL"
        else:
            group, policy = "test/mixed_defect", "CONTROLLED_COMPONENT_DEVIATION"
        destination = OUTPUT / group / f"strict_{index:03d}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest.append({
            "index": index, "phase": row["phase"], "group": group,
            "policy": policy, "source": str(source.relative_to(ROOT)),
            "destination": str(destination.relative_to(ROOT)),
        })

    legacy = sorted((SOURCE / "test/mixed_defect").glob("*.png"))
    for sequence, source in enumerate(legacy, start=1):
        destination = OUTPUT / "test/mixed_defect" / f"legacy_{sequence:03d}.png"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        manifest.append({
            "index": "", "phase": "legacy_mixed_defect",
            "group": "test/mixed_defect", "policy": "LEGACY_UNVERIFIED_DETAIL",
            "source": str(source.relative_to(ROOT)),
            "destination": str(destination.relative_to(ROOT)),
        })

    with (OUTPUT / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    summary = {
        "schema_version": 1,
        "policy": "strict_golden_normal_only",
        "counts": {
            "train/good": len(STRICT_TRAIN),
            "test/good": len(STRICT_TEST),
            "test/mixed_defect": 53 - len(STRICT_TRAIN) - len(STRICT_TEST) + len(legacy),
            "controlled_component_deviation": 38,
            "legacy_mixed_defect": len(legacy),
        },
        "reason": (
            "Component-tolerance phases are excluded from normal training so "
            "small placement/orientation deviations remain detectable."
        ),
    }
    (OUTPUT / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["counts"], indent=2))
    print(f"STRICT_WHOLE_BOARD_DATASET={OUTPUT}")


if __name__ == "__main__":
    main()
