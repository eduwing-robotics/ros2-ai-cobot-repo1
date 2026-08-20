#!/usr/bin/env python3
"""Import Unity's PCB pick-point export into the physical board frame.

Unity exports X/Y from the model board's minimum corner.  Robot vision uses
the physical board centre, so this tool recentres the points and applies the
measured 139 x 110 mm board scale.  Z remains a nominal top-surface height and
must not be used for an unverified automatic descent.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

TYPE_SPECS = {
    "AI_GPU": {
        "component_type": "GPU", "recipe": "gpu", "count": 1,
        "size_mm": (29.7166, 57.1065, 6.6383), "base_long_axis_deg": 90.0,
    },
    "HBM": {
        "component_type": "HBM", "recipe": "hbm", "count": 8,
        "size_mm": (10.2466, 14.3100, 9.8151), "base_long_axis_deg": 90.0,
    },
    "Power_Module": {
        "component_type": "Power Module", "recipe": "long_orange", "count": 4,
        "size_mm": (12.1300, 59.9891, 4.7848), "base_long_axis_deg": 90.0,
    },
    "VRM": {
        "component_type": "VRM", "recipe": "left_black_block", "count": 5,
        "size_mm": (11.0000, 14.0000, 5.2025), "base_long_axis_deg": 90.0,
    },
    "Inductor": {
        "component_type": "Inductor", "recipe": "right_white_black", "count": 2,
        "size_mm": (9.3686, 9.3686, 8.5222), "base_long_axis_deg": 0.0,
    },
    "SMD_Capacitor": {
        "component_type": "SMD Capacitor", "recipe": "right_white_brown", "count": 5,
        "size_mm": (3.8361, 6.8013, 3.0238), "base_long_axis_deg": 90.0,
    },
}


def normalize_axis_angle(degrees: float) -> float:
    while degrees >= 180.0:
        degrees -= 180.0
    while degrees < 0.0:
        degrees += 180.0
    if abs(degrees - 180.0) < 1e-9:
        return 0.0
    return degrees


def spec_for(part_id: str) -> tuple[str, dict]:
    for prefix, spec in TYPE_SPECS.items():
        if part_id == prefix or part_id.startswith(prefix + "_"):
            return prefix, spec
    raise ValueError(f"Unknown Unity part ID: {part_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--unity-csv", type=Path,
        default=Path.home() / "My project/Assets/RobotArm/PcbPickCoordinates.csv",
    )
    parser.add_argument("--model-board-width-mm", type=float, default=140.0)
    parser.add_argument("--model-board-height-mm", type=float, default=110.337)
    parser.add_argument("--physical-board-width-mm", type=float, default=139.0)
    parser.add_argument("--physical-board-height-mm", type=float, default=110.0)
    parser.add_argument(
        "--json-output", type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.json",
    )
    parser.add_argument(
        "--csv-output", type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.csv",
    )
    parser.add_argument(
        "--assembly-output", type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/assembly_layout_approx.json",
    )
    parser.add_argument(
        "--svg-output", type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.svg",
    )
    return parser.parse_args()


def build_layout(args: argparse.Namespace) -> tuple[dict, dict]:
    if not args.unity_csv.is_file():
        raise FileNotFoundError(args.unity_csv)
    if min(
        args.model_board_width_mm, args.model_board_height_mm,
        args.physical_board_width_mm, args.physical_board_height_mm,
    ) <= 0.0:
        raise ValueError("All board dimensions must be positive")

    scale_x = args.physical_board_width_mm / args.model_board_width_mm
    scale_y = args.physical_board_height_mm / args.model_board_height_mm
    placements = []
    component_slots: dict[str, list[dict]] = {
        spec["component_type"]: [] for spec in TYPE_SPECS.values()
    }
    counts: Counter[str] = Counter()

    with args.unity_csv.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))

    for row in rows:
        part_id = row["part_id"].strip()
        _, spec = spec_for(part_id)
        counts[spec["component_type"]] += 1
        model_x = float(row["board_x_mm"])
        model_y = float(row["board_y_mm"])
        top_z = float(row["board_z_mm"])
        yaw = float(row["rotation_y_deg"])
        physical_x = (model_x - args.model_board_width_mm * 0.5) * scale_x
        physical_y = (model_y - args.model_board_height_mm * 0.5) * scale_y
        long_axis = normalize_axis_angle(spec["base_long_axis_deg"] - yaw)
        size_x, size_y, nominal_height = spec["size_mm"]
        quarter_turn = abs((yaw % 180.0) - 90.0) < 1e-3
        if quarter_turn:
            footprint_x = size_y * scale_x
            footprint_y = size_x * scale_y
        else:
            footprint_x = size_x * scale_x
            footprint_y = size_y * scale_y

        slot_id = part_id.lower()
        placement = {
            "slot_id": slot_id,
            "part_id": part_id,
            "recipe": spec["recipe"],
            "component_type": spec["component_type"],
            "source_name": row["source_name"].strip(),
            "center_board_mm": {
                "x": physical_x,
                "y": physical_y,
            },
            "top_z_mm_nominal": top_z,
            "long_axis_deg_in_board": long_axis,
            "rotation_y_deg_unity": yaw,
            "nominal_size_mm": {
                "x": footprint_x,
                "y": footprint_y,
                "height": nominal_height,
            },
            "model_local_size_mm": {
                "x": size_x,
                "y": size_y,
                "height": nominal_height,
            },
            "unity_export": {
                "board_x_from_min_mm": model_x,
                "board_y_from_min_mm": model_y,
                "board_z_from_top_mm": top_z,
                "world_x_m": float(row["unity_world_x_m"]),
                "world_y_m": float(row["unity_world_y_m"]),
                "world_z_m": float(row["unity_world_z_m"]),
            },
        }
        placements.append(placement)
        component_slots[spec["component_type"]].append({
            "id": slot_id,
            "x_mm": round(physical_x, 3),
            "y_mm": round(physical_y, 3),
            "top_z_mm_nominal": round(top_z, 3),
            "long_axis_board_deg": round(long_axis, 3),
        })

    expected = {spec["component_type"]: spec["count"] for spec in TYPE_SPECS.values()}
    if dict(counts) != expected:
        raise ValueError(f"Unity part counts differ: expected={expected}, found={dict(counts)}")
    if len({item["part_id"] for item in placements}) != len(placements):
        raise ValueError("Unity export contains duplicate part IDs")

    placements.sort(key=lambda item: item["part_id"])
    for slots in component_slots.values():
        slots.sort(key=lambda item: item["id"])

    layout = {
        "schema_version": 2,
        "source": str(args.unity_csv),
        "status": "Unity-derived physical-scale candidate; validate on the printed board before robot execution",
        "coordinate_convention": {
            "origin": "geometric center of the physical PCB top surface",
            "x": "Unity +X in the board plane",
            "y": "Unity +Z in the board plane",
            "z": "height above PCB top; nominal only",
            "units": "mm",
        },
        "board": {
            "name": "motherBoard",
            "size_mm": {"x": args.physical_board_width_mm, "y": args.physical_board_height_mm},
            "unity_source_size_mm": {"x": args.model_board_width_mm, "y": args.model_board_height_mm},
            "unity_to_physical_scale": {"x": scale_x, "y": scale_y},
        },
        "expected_robot_part_counts": expected,
        "model_robot_part_counts": dict(counts),
        "count_mismatches": {},
        "unresolved_required_parts": [],
        "warnings": [
            "XY values are scaled CAD candidates, not measured robot-base coordinates.",
            "Top Z and nominal component heights must be checked with aligned depth/calipers.",
            "Keep physical slot overrides until every regenerated slot is validated by TCP hover.",
        ],
        "placements": placements,
    }
    assembly = {
        "schema_version": 2,
        "name": "semiconductor_package_assembly_unity_layout",
        "coordinate_frame": "board_center",
        "units": "mm",
        "board_size_mm": {"x": args.physical_board_width_mm, "y": args.physical_board_height_mm},
        "source": str(args.unity_csv),
        "status": "Unity-derived physical-scale candidate; re-register after final fixture and S22 installation",
        "component_types": {
            component_type: {
                "count": len(slots),
                "slots": slots,
            }
            for component_type, slots in component_slots.items()
        },
    }
    assembly["component_types"]["SMD Capacitor"]["aliases"] = [
        "SMD Capacitior", "right_white_brown"
    ]
    return layout, assembly


def write_outputs(args: argparse.Namespace, layout: dict, assembly: dict) -> None:
    for output in (args.json_output, args.csv_output, args.assembly_output, args.svg_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(layout, indent=2, ensure_ascii=False) + "\n")
    args.assembly_output.write_text(json.dumps(assembly, indent=2, ensure_ascii=False) + "\n")

    with args.csv_output.open("w", newline="", encoding="utf-8") as stream:
        fields = [
            "slot_id", "component_type", "recipe", "source_name",
            "x_board_mm", "y_board_mm", "top_z_mm_nominal",
            "long_axis_deg", "rotation_y_deg_unity",
            "size_x_mm", "size_y_mm", "height_mm_nominal",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in layout["placements"]:
            writer.writerow({
                "slot_id": item["slot_id"],
                "component_type": item["component_type"],
                "recipe": item["recipe"],
                "source_name": item["source_name"],
                "x_board_mm": f'{item["center_board_mm"]["x"]:.3f}',
                "y_board_mm": f'{item["center_board_mm"]["y"]:.3f}',
                "top_z_mm_nominal": f'{item["top_z_mm_nominal"]:.3f}',
                "long_axis_deg": f'{item["long_axis_deg_in_board"]:.3f}',
                "rotation_y_deg_unity": f'{item["rotation_y_deg_unity"]:.3f}',
                "size_x_mm": f'{item["nominal_size_mm"]["x"]:.3f}',
                "size_y_mm": f'{item["nominal_size_mm"]["y"]:.3f}',
                "height_mm_nominal": f'{item["nominal_size_mm"]["height"]:.3f}',
            })

    # Reuse the established presentation SVG renderer. It consumes the same
    # board/placement fields and legacy recipe names retained above.
    from extract_unity_board_layout import write_svg
    write_svg(args.svg_output, layout)


def main() -> None:
    args = parse_args()
    layout, assembly = build_layout(args)
    write_outputs(args, layout, assembly)
    print(
        f'Board: {layout["board"]["size_mm"]["x"]:.3f} x '
        f'{layout["board"]["size_mm"]["y"]:.3f} mm (physical centre frame)'
    )
    print(f'Parts: {len(layout["placements"])}; counts={layout["model_robot_part_counts"]}')
    print(f'JSON: {args.json_output}')
    print(f'CSV:  {args.csv_output}')
    print(f'SVG:  {args.svg_output}')


if __name__ == "__main__":
    main()
