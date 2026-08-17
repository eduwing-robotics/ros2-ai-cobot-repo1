#!/usr/bin/env python3
"""Extract a board-relative placement layout from the supplied Unity/OBJ assembly.

The supplied model uses Unity X/Z as its board plane and a 0.01 root scale.
OBJ geometry is converted from its right-handed X axis to Unity's left-handed
X axis before the prefab transforms are applied.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MM_PER_MODEL_UNIT = 10.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RECIPE_BY_ASSET = {
    "Sk_hynix": "hbm",
    "BlackBox1": "left_black_block",
    "YellowBar": "long_orange",
    "cap_small": "right_white_brown",
    "cap_Big": "right_white_black",
    "nvidia": "gpu",
    "motherBoard": "board",
}

EXPECTED_ROBOT_PART_COUNTS = {
    "gpu": 1,
    "hbm": 8,
    "left_black_block": 5,
    "right_white_brown": 5,
    "right_white_black": 2,
    "long_orange": 4,
}


@dataclass
class ObjBounds:
    minimum: list[float]
    maximum: list[float]

    @property
    def center_unity(self) -> list[float]:
        center_obj = [
            (self.minimum[index] + self.maximum[index]) * 0.5
            for index in range(3)
        ]
        # Unity converts the right-handed OBJ X axis to its left-handed X axis.
        return [-center_obj[0], center_obj[1], center_obj[2]]

    @property
    def extent(self) -> list[float]:
        return [
            self.maximum[index] - self.minimum[index] for index in range(3)
        ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path.home() / "Downloads/Board_obj",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.json",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.csv",
    )
    parser.add_argument(
        "--svg-output",
        type=Path,
        default=PROJECT_ROOT / "vision_assembly/config/board_layout_from_unity.svg",
    )
    return parser.parse_args()


def load_guid_paths(source: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for meta_file in source.rglob("*.meta"):
        match = re.search(
            r"^guid:\s*([0-9a-f]+)", meta_file.read_text(errors="ignore"), re.M
        )
        if match:
            result[match.group(1)] = Path(str(meta_file)[: -len(".meta")])
    return result


def parse_obj_bounds(obj_file: Path) -> ObjBounds:
    minimum = [math.inf, math.inf, math.inf]
    maximum = [-math.inf, -math.inf, -math.inf]
    vertices = 0
    with obj_file.open(errors="ignore") as stream:
        for line in stream:
            if not line.startswith("v "):
                continue
            values = line.split()
            if len(values) < 4:
                continue
            xyz = [float(value) for value in values[1:4]]
            vertices += 1
            for index, value in enumerate(xyz):
                minimum[index] = min(minimum[index], value)
                maximum[index] = max(maximum[index], value)
    if not vertices:
        raise ValueError(f"No OBJ vertices found: {obj_file}")
    return ObjBounds(minimum=minimum, maximum=maximum)


def parse_modification_groups(block: str) -> dict[str, dict[str, str]]:
    groups: dict[str, dict[str, str]] = defaultdict(dict)
    expression = re.compile(
        r"- target: \{fileID: ([^,]+),[^}]*\}\n"
        r"\s+propertyPath: (.+?)\n"
        r"\s+value:\s*(.*?)\n"
    )
    for match in expression.finditer(block):
        file_id, property_path, value = match.groups()
        groups[file_id.strip()][property_path.strip().strip("'")] = value.strip()
    return dict(groups)


def vector_from_group(group: dict[str, str], prefix: str) -> list[float]:
    return [float(group.get(f"{prefix}.{axis}", "0") or 0) for axis in "xyz"]


def root_group_id(groups: dict[str, dict[str, str]]) -> str:
    def score(item: tuple[str, dict[str, str]]) -> tuple[int, int]:
        _, group = item
        rotation_count = sum(
            f"m_LocalRotation.{axis}" in group for axis in "xyzw"
        )
        position_count = sum(
            f"m_LocalPosition.{axis}" in group for axis in "xyz"
        )
        return rotation_count, position_count

    candidates = [
        item
        for item in groups.items()
        if any(key.startswith("m_LocalPosition.") for key in item[1])
    ]
    if not candidates:
        raise ValueError("Prefab instance has no transform position")
    return max(candidates, key=score)[0]


def quaternion_matrix(group: dict[str, str]) -> list[list[float]]:
    x = float(group.get("m_LocalRotation.x", "0") or 0)
    y = float(group.get("m_LocalRotation.y", "0") or 0)
    z = float(group.get("m_LocalRotation.z", "0") or 0)
    w = float(group.get("m_LocalRotation.w", "1") or 1)
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def matrix_vector(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[index] * vector[index] for index in range(3)) for row in matrix]


def add(*vectors: list[float]) -> list[float]:
    return [sum(vector[index] for vector in vectors) for index in range(3)]


def source_model_for_asset(asset_file: Path, guid_paths: dict[str, Path]) -> Path:
    if asset_file.suffix.lower() == ".obj":
        return asset_file
    text = asset_file.read_text(errors="ignore")
    match = re.search(r"m_SourcePrefab: \{[^}]*guid: ([0-9a-f]+)", text)
    if not match or match.group(1) not in guid_paths:
        raise ValueError(f"Cannot resolve model source for {asset_file}")
    model_file = guid_paths[match.group(1)]
    if model_file.suffix.lower() != ".obj":
        raise ValueError(f"Resolved source is not OBJ: {model_file}")
    return model_file


def inherited_child_offset(asset_file: Path) -> list[float]:
    if asset_file.suffix.lower() != ".prefab":
        return [0.0, 0.0, 0.0]
    groups = parse_modification_groups(asset_file.read_text(errors="ignore"))
    if not groups:
        return [0.0, 0.0, 0.0]
    root_id = root_group_id(groups)
    offsets = [
        vector_from_group(group, "m_LocalPosition")
        for file_id, group in groups.items()
        if file_id != root_id
        and any(key.startswith("m_LocalPosition.") for key in group)
    ]
    return add(*offsets) if offsets else [0.0, 0.0, 0.0]


def asset_name(asset_file: Path) -> str:
    return asset_file.stem


def normalize_axis_angle(degrees: float) -> float:
    while degrees >= 90.0:
        degrees -= 180.0
    while degrees < -90.0:
        degrees += 180.0
    return degrees


def build_layout(source: Path) -> dict[str, Any]:
    guid_paths = load_guid_paths(source)
    assembly_file = source / "ITEAM.prefab"
    assembly_text = assembly_file.read_text(errors="ignore")
    blocks = re.split(r"(?=^--- !u!1001 )", assembly_text, flags=re.M)
    instances: list[dict[str, Any]] = []

    bounds_cache: dict[Path, ObjBounds] = {}
    inherited_offset_cache: dict[Path, list[float]] = {}

    for block in blocks:
        source_match = re.search(
            r"m_SourcePrefab: \{[^}]*guid: ([0-9a-f]+)", block
        )
        if not source_match:
            continue
        source_guid = source_match.group(1)
        if source_guid not in guid_paths:
            raise ValueError(f"Unknown Unity GUID: {source_guid}")
        asset_file = guid_paths[source_guid]
        model_file = source_model_for_asset(asset_file, guid_paths)
        groups = parse_modification_groups(block)
        root_id = root_group_id(groups)
        root_group = groups[root_id]
        root_position = vector_from_group(root_group, "m_LocalPosition")
        root_rotation = quaternion_matrix(root_group)

        instance_offsets = [
            vector_from_group(group, "m_LocalPosition")
            for file_id, group in groups.items()
            if file_id != root_id
            and any(key.startswith("m_LocalPosition.") for key in group)
        ]
        instance_child_offset = (
            add(*instance_offsets) if instance_offsets else [0.0, 0.0, 0.0]
        )
        if asset_file not in inherited_offset_cache:
            inherited_offset_cache[asset_file] = inherited_child_offset(asset_file)
        child_offset = add(
            inherited_offset_cache[asset_file], instance_child_offset
        )

        if model_file not in bounds_cache:
            bounds_cache[model_file] = parse_obj_bounds(model_file)
        bounds = bounds_cache[model_file]
        local_center = add(child_offset, bounds.center_unity)
        center_model = add(root_position, matrix_vector(root_rotation, local_center))

        display_name = ""
        for group in groups.values():
            if group.get("m_Name"):
                display_name = group["m_Name"]
        base_asset_name = asset_name(asset_file)
        recipe = RECIPE_BY_ASSET.get(base_asset_name)
        if recipe is None:
            raise ValueError(f"No recipe mapping for asset {asset_file}")

        extent = bounds.extent
        canonical_long_axis = [1.0, 0.0, 0.0] if extent[0] >= extent[2] else [0.0, 0.0, 1.0]
        rotated_long_axis = matrix_vector(root_rotation, canonical_long_axis)
        long_axis_deg = normalize_axis_angle(
            math.degrees(math.atan2(rotated_long_axis[2], rotated_long_axis[0]))
        )

        instances.append(
            {
                "name": display_name or base_asset_name,
                "asset": base_asset_name,
                "recipe": recipe,
                "source_model": str(model_file.relative_to(source)),
                "center_model_units": center_model,
                "root_position_model_units": root_position,
                "child_offset_model_units": child_offset,
                "nominal_size_mm": {
                    "x": extent[0] * MM_PER_MODEL_UNIT,
                    "y": extent[2] * MM_PER_MODEL_UNIT,
                    "height": extent[1] * MM_PER_MODEL_UNIT,
                },
                "long_axis_deg_in_board": long_axis_deg,
            }
        )

    board_instances = [item for item in instances if item["recipe"] == "board"]
    if len(board_instances) != 1:
        raise ValueError(f"Expected exactly one board, found {len(board_instances)}")
    board = board_instances[0]
    board_center = board["center_model_units"]

    placements: list[dict[str, Any]] = []
    for item in instances:
        if item["recipe"] == "board":
            continue
        center = item["center_model_units"]
        placement = dict(item)
        placement["center_board_mm"] = {
            "x": (center[0] - board_center[0]) * MM_PER_MODEL_UNIT,
            "y": (center[2] - board_center[2]) * MM_PER_MODEL_UNIT,
        }
        placements.append(placement)

    placements.sort(
        key=lambda item: (
            item["recipe"],
            round(item["center_board_mm"]["x"], 4),
            round(item["center_board_mm"]["y"], 4),
        )
    )
    recipe_indices: Counter[str] = Counter()
    for item in placements:
        recipe_indices[item["recipe"]] += 1
        item["slot_id"] = f"{item['recipe']}_{recipe_indices[item['recipe']]:02d}"
    actual_counts = Counter(item["recipe"] for item in placements)
    mismatches = {
        recipe: {
            "expected": expected,
            "model": actual_counts.get(recipe, 0),
        }
        for recipe, expected in EXPECTED_ROBOT_PART_COUNTS.items()
        if actual_counts.get(recipe, 0) != expected
    }
    unresolved_required_parts = [
        {
            "recipe": recipe,
            "missing_count": details["expected"] - details["model"],
            "center_board_mm": None,
            "status": "missing from supplied Unity assembly; corrected CAD/assembly required",
        }
        for recipe, details in mismatches.items()
        if details["expected"] > details["model"]
    ]

    return {
        "schema_version": 1,
        "source": str(source),
        "assembly": "ITEAM.prefab",
        "status": "CAD-derived candidate; verify on the printed board before robot execution",
        "coordinate_convention": {
            "origin": "geometric center of motherBoard OBJ after Unity prefab transforms",
            "x": "Unity +X in the board plane",
            "y": "Unity +Z in the board plane",
            "z": "Unity +Y upward; not used as an automatic placement height",
            "millimeters_per_model_unit": MM_PER_MODEL_UNIT,
        },
        "board": {
            "name": board["name"],
            "size_mm": board["nominal_size_mm"],
            "center_model_units": board_center,
        },
        "expected_robot_part_counts": EXPECTED_ROBOT_PART_COUNTS,
        "model_robot_part_counts": dict(sorted(actual_counts.items())),
        "count_mismatches": mismatches,
        "unresolved_required_parts": unresolved_required_parts,
        "warnings": [
            "CAD planar coordinates are candidates until checked against the actual print.",
            "Nominal heights come from OBJ bounds and must be measured with a caliper.",
            "Placement Z must come from the detected board plane/Depth plus a verified recipe height.",
            "The model contains four right_white_brown instances, while the project list expects five.",
        ],
        "placements": placements,
    }


def write_csv(output_file: Path, layout: dict[str, Any]) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "slot_id",
                "recipe",
                "source_name",
                "x_board_mm",
                "y_board_mm",
                "long_axis_deg",
                "size_x_mm",
                "size_y_mm",
                "height_mm_nominal",
            ],
        )
        writer.writeheader()
        for item in layout["placements"]:
            writer.writerow(
                {
                    "slot_id": item["slot_id"],
                    "recipe": item["recipe"],
                    "source_name": item["name"],
                    "x_board_mm": round(item["center_board_mm"]["x"], 4),
                    "y_board_mm": round(item["center_board_mm"]["y"], 4),
                    "long_axis_deg": round(item["long_axis_deg_in_board"], 4),
                    "size_x_mm": round(item["nominal_size_mm"]["x"], 4),
                    "size_y_mm": round(item["nominal_size_mm"]["y"], 4),
                    "height_mm_nominal": round(
                        item["nominal_size_mm"]["height"], 4
                    ),
                }
            )


def write_svg(output_file: Path, layout: dict[str, Any]) -> None:
    colors = {
        "gpu": "#76b900",
        "hbm": "#444444",
        "left_black_block": "#111111",
        "long_orange": "#d89c27",
        "right_white_black": "#d8d8d8",
        "right_white_brown": "#8b4c39",
    }
    width = layout["board"]["size_mm"]["x"]
    height = layout["board"]["size_mm"]["y"]
    scale = 6.0
    margin = 25.0
    canvas_width = width * scale + 2 * margin
    canvas_height = height * scale + 2 * margin

    def sx(x_mm: float) -> float:
        return margin + (x_mm + width * 0.5) * scale

    def sy(y_mm: float) -> float:
        return margin + (height * 0.5 - y_mm) * scale

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width:.0f}" '
        f'height="{canvas_height:.0f}" viewBox="0 0 {canvas_width:.3f} {canvas_height:.3f}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<rect x="{margin:.3f}" y="{margin:.3f}" width="{width * scale:.3f}" '
        f'height="{height * scale:.3f}" fill="#253438" stroke="#000" stroke-width="3"/>',
        f'<line x1="{sx(0):.3f}" y1="{margin:.3f}" x2="{sx(0):.3f}" '
        f'y2="{margin + height * scale:.3f}" stroke="#00ffff" stroke-width="1"/>',
        f'<line x1="{margin:.3f}" y1="{sy(0):.3f}" x2="{margin + width * scale:.3f}" '
        f'y2="{sy(0):.3f}" stroke="#00ffff" stroke-width="1"/>',
    ]
    for item in layout["placements"]:
        center = item["center_board_mm"]
        size = item["nominal_size_mm"]
        part_width = size["x"]
        part_height = size["y"]
        angle = item["long_axis_deg_in_board"]
        canonical_long_is_y = size["y"] >= size["x"]
        if canonical_long_is_y and abs(angle) < 45.0:
            part_width, part_height = part_height, part_width
        x = sx(center["x"]) - part_width * scale * 0.5
        y = sy(center["y"]) - part_height * scale * 0.5
        fill = colors[item["recipe"]]
        text_color = "#111" if item["recipe"] == "right_white_black" else "white"
        short_id = item["slot_id"].rsplit("_", 1)[-1]
        lines.append(
            f'<rect x="{x:.3f}" y="{y:.3f}" width="{part_width * scale:.3f}" '
            f'height="{part_height * scale:.3f}" fill="{fill}" stroke="white" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{sx(center["x"]):.3f}" y="{sy(center["y"]) + 4:.3f}" '
            f'font-family="sans-serif" font-size="11" text-anchor="middle" '
            f'fill="{text_color}">{short_id}</text>'
        )
    lines.append("</svg>")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    layout = build_layout(args.source)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(layout, indent=2, ensure_ascii=False) + "\n")
    write_csv(args.csv_output, layout)
    write_svg(args.svg_output, layout)

    print(f"Board: {layout['board']['size_mm']['x']:.2f} x {layout['board']['size_mm']['y']:.2f} mm")
    print(f"Robot-placeable model instances: {len(layout['placements'])}")
    print("Counts:", layout["model_robot_part_counts"])
    if layout["count_mismatches"]:
        print("COUNT MISMATCH:", layout["count_mismatches"])
    print(f"JSON: {args.json_output}")
    print(f"CSV:  {args.csv_output}")
    print(f"SVG:  {args.svg_output}")


if __name__ == "__main__":
    main()
