#!/usr/bin/env python3
"""Build a fresh full-schema snapshot for a cycle with completed leading slots.

The full planner requires all 25 logical tray instances.  This helper keeps the
already-completed GPU-01/HBM-01 reference records as non-executed placeholders,
then binds every live remaining detection to its previous physical tray cell by
nearest XY.  It never sends a robot command.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import time
from pathlib import Path


EXPECTED = {
    "gpu": 0,
    "hbm": 7,
    "long_orange": 4,
    "black_block": 5,
    "marked_white": 2,
    "right_white_brown": 5,
}
COMPLETED = {("gpu", 1), ("hbm", 1)}
MAX_MATCH_MM = 5.0


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def distance_xy(first: dict, second: dict) -> float:
    a = first["base_xyz_mm"]
    b = second["base_xyz_mm"]
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def quality_from_detection(detection: dict) -> dict:
    return {
        "observation_frames": int(detection["observation_frames"]),
        "median_detection_confidence": float(detection["median_detection_confidence"]),
        "median_mask_shape_score": float(detection["median_mask_shape_score"]),
        "median_rectangularity": float(detection["median_rectangularity"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board-snapshot", type=Path, required=True)
    parser.add_argument("--reference-full-snapshot", type=Path, required=True)
    parser.add_argument("--tray-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-tray-age-sec", type=float, default=15.0)
    args = parser.parse_args()

    board = load(args.board_snapshot)
    reference = load(args.reference_full_snapshot)
    tray = load(args.tray_input)
    if board.get("schema") != "fr5.fixed_fixture_cycle_snapshot/v1":
        raise RuntimeError("wrong board snapshot schema")
    if reference.get("schema") != "fr5.fixed_fixture_cycle_snapshot/v1":
        raise RuntimeError("wrong reference snapshot schema")
    if tray.get("tray_registration") != "TRACKING":
        raise RuntimeError("live tray registration is not TRACKING")
    if tray.get("base_transform_status") not in ("OK", "VALID_COORDINATES_ONLY"):
        raise RuntimeError("live tray Base transform is invalid")
    age = time.time() - args.tray_input.stat().st_mtime
    if age < 0.0 or age > args.maximum_tray_age_sec:
        raise RuntimeError(f"live tray input is stale: {age:.3f}s")

    live = tray.get("stable_detections", [])
    counts = {name: 0 for name in EXPECTED}
    for item in live:
        part_type = str(item.get("part_type"))
        if part_type not in counts:
            raise RuntimeError(f"unexpected live part type {part_type!r}")
        counts[part_type] += 1
    if counts != EXPECTED:
        raise RuntimeError(f"remaining tray counts mismatch: expected={EXPECTED}, actual={counts}")

    reference_parts = reference["tray_capture"]["parts"]
    result_parts = []
    bindings = []
    for ref in reference_parts:
        key = (str(ref["part_type"]), int(ref["instance_index"]))
        if key in COMPLETED:
            result_parts.append(copy.deepcopy(ref))

    for part_type, expected_count in EXPECTED.items():
        if expected_count == 0:
            continue
        candidates = [
            item for item in reference_parts
            if item["part_type"] == part_type
            and (part_type, int(item["instance_index"])) not in COMPLETED
        ]
        detections = [item for item in live if item["part_type"] == part_type]
        available = list(candidates)
        for detection in detections:
            target = min(available, key=lambda item: distance_xy(detection, item))
            distance = distance_xy(detection, target)
            if distance > MAX_MATCH_MM:
                raise RuntimeError(
                    f"{part_type} live instance {detection['instance_index']} has no "
                    f"reference cell within {MAX_MATCH_MM:.1f}mm (nearest={distance:.3f}mm)"
                )
            available.remove(target)
            item = copy.deepcopy(target)
            item["base_xyz_mm"] = [float(value) for value in detection["base_xyz_mm"]]
            item["observation_frames"] = int(detection["observation_frames"])
            item["quality"] = quality_from_detection(detection)
            item["consumed"] = False
            item["live_detector_instance_index"] = int(detection["instance_index"])
            item["reference_cell_match_distance_mm"] = round(distance, 3)
            if part_type == "right_white_brown":
                item["coarse_long_axis_angle_base_deg"] = float(
                    detection["long_axis_angle_base_deg"]
                )
                item["fine_angle_reference_reused"] = True
            else:
                item["long_axis_angle_base_deg"] = float(
                    detection["long_axis_angle_base_deg"]
                )
            result_parts.append(item)
            bindings.append(
                {
                    "part_type": part_type,
                    "live_instance_index": int(detection["instance_index"]),
                    "logical_instance_index": int(target["instance_index"]),
                    "distance_mm": round(distance, 3),
                }
            )
        if available:
            raise RuntimeError(f"unmatched reference cells remain for {part_type}")

    result_parts.sort(key=lambda item: (item["part_type"], int(item["instance_index"])))
    output = copy.deepcopy(reference)
    output["cycle_id"] = time.strftime("%Y%m%d-%H%M%S")
    output["created_unix"] = time.time()
    output["board_capture"] = copy.deepcopy(board["board_capture"])
    output["resolved_placements"] = copy.deepcopy(board["resolved_placements"])
    output["placement_ready_count"] = int(board["placement_ready_count"])
    output["placement_blocked_slots"] = copy.deepcopy(board["placement_blocked_slots"])
    output["tray_capture"] = {
        "captured_unix": time.time(),
        "source_file": str(args.tray_input.resolve()),
        "source_sha256": hashlib.sha256(args.tray_input.read_bytes()).hexdigest(),
        "source_age_sec": round(age, 3),
        "handeye_sha256": str(tray.get("handeye_sha256", "")),
        "counts": {"gpu": 1, "hbm": 8, "long_orange": 4, "black_block": 5,
                   "marked_white": 2, "right_white_brown": 5},
        "part_count": 25,
        "capture_scope": {
            "mode": "remaining_cycle_with_completed_placeholders",
            "completed_slots": ["GPU-01", "HBM-01"],
            "live_remaining_count": 23,
        },
        "parts": result_parts,
        "bindings": bindings,
    }
    output["board_captured"] = True
    output["tray_captured"] = True
    output["smd_close_captured"] = True
    output["ready_for_continuous_execution"] = True
    output["robot_motion_authorized"] = False
    output["remaining_cycle_provenance"] = {
        "completed_slots": ["GPU-01", "HBM-01"],
        "live_remaining_count": 23,
        "cap_fine_angles_from_reference": str(args.reference_full_snapshot.resolve()),
    }
    atomic_write(args.output, output)
    print(f"REMAINING SNAPSHOT READY: 23 live parts -> {args.output.resolve()}")
    print("ROBOT DID NOT MOVE")


if __name__ == "__main__":
    main()
