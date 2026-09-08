#!/usr/bin/env python3
"""Build a frozen 25-part assembly plan without commanding the robot.

This is the permanent form of the full-cycle planner that was previously run
as an inline Python program.  It consumes one fixed-fixture snapshot and the
validated recipe/slot configuration, then writes only a JSON plan.  Motion is
intentionally outside this module.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from smd_grasp_center_audit import describe_center
from successful_gripper_directions import REFERENCES, REVISION, validate_item

from placement_orientation import (
    circular_distance_deg,
    plan_carried_part_orientation,
    slot_axis_base_angle_deg,
    tool_axis_base_angle_deg,
    wrap_degrees,
)


ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / "vision_assembly"
DEFAULT_SNAPSHOT = VISION / "data/fixed_cycle_snapshot.json"
DEFAULT_RECIPES = VISION / "config/part_gripper_recipes.json"
DEFAULT_SLOTS = VISION / "config/assembly_slots_r1.json"
DEFAULT_OUTPUT = VISION / "data/full_cycle_plan.json"

ALIGN_CARRIED_AXIS_MODE = "align_actual_carried_axis_to_current_slot_axis"
PRESERVE_PICK_TCP_MODE = "preserve_pick_tcp_orientation"
MOTION_PROFILE = "smooth_combined_transfer_v1"

SLOT_PART_SEQUENCE = tuple(
    [("GPU-01", "gpu")]
    + [(f"HBM-{index:02d}", "hbm") for index in range(1, 9)]
    + [(f"PM-{index:02d}", "long_orange") for index in range(1, 5)]
    + [(f"VRM-{index:02d}", "black_block") for index in range(1, 6)]
    + [(f"IND-{index:02d}", "marked_white") for index in range(1, 3)]
    + [(f"CAP-{index:02d}", "right_white_brown") for index in range(1, 6)]
)
SLOT_SEQUENCE = tuple(slot for slot, _ in SLOT_PART_SEQUENCE)
EXPECTED_TRAY_COUNTS = {
    "gpu": 1,
    "hbm": 8,
    "long_orange": 4,
    "black_block": 5,
    "marked_white": 2,
    "right_white_brown": 5,
}
DEFAULT_SPEEDS_PERCENT = {
    "travel": 25,
    "combined_rotation": 25,
    "vertical": 10,
    "high_transfer": 40,
    "clearance_lift": 30,
}
COMMON_BOARD_PLACE_Z_RAISE_MM = 0.3


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _finite_vector(value: Any, length: int, label: str) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must contain {length} finite values") from exc
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise RuntimeError(f"{label} must contain {length} finite values")
    return vector


def _finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be finite") from exc
    if not math.isfinite(number):
        raise RuntimeError(f"{label} must be finite")
    return number


def _xy(mapping: Mapping[str, Any], key: str, label: str) -> np.ndarray:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise RuntimeError(f"missing {label}")
    return _finite_vector([value.get("x"), value.get("y")], 2, label)


def _command_position(command: Any, label: str) -> int:
    if not isinstance(command, Mapping):
        raise RuntimeError(f"missing {label} gripper command")
    args = command.get("args")
    if not isinstance(args, Sequence) or isinstance(args, (str, bytes)) or len(args) < 2:
        raise RuntimeError(f"invalid {label} gripper command")
    raw_position = _finite_number(args[1], f"{label} gripper position")
    position = int(raw_position)
    if raw_position != position or not 0 <= position <= 100:
        raise RuntimeError(f"invalid {label} gripper position {raw_position}")
    return position


def choose_symmetric_pick_c(
    detected_axis_deg: float,
    gripper_axis: str,
    reference_c_deg: float,
) -> float:
    """Choose the 180-degree-equivalent pick pose closest to prior placement."""

    if gripper_axis not in ("tool_x", "tool_y"):
        raise RuntimeError(f"invalid gripper axis {gripper_axis!r}")
    offset = 90.0 if gripper_axis == "tool_y" else 0.0
    first = wrap_degrees(detected_axis_deg + offset)
    second = wrap_degrees(first + 180.0)
    return float(
        min(
            (first, second),
            key=lambda candidate: (
                circular_distance_deg(candidate, reference_c_deg),
                abs(candidate),
            ),
        )
    )


def _pick_correction(
    recipe: Mapping[str, Any],
    part_type: str,
    pick_abc: Sequence[float],
) -> np.ndarray:
    if part_type == "long_orange":
        # The PM correction was physically taught in Tool XY.  Its Base-XY
        # value therefore has to follow the selected symmetric wrist branch.
        tool_xy = _xy(
            recipe,
            "grasp_center_correction_tool_mm",
            "Power Module Tool-XY grasp correction",
        )
        operator_base_xy = _xy(
            recipe,
            "operator_additional_correction_base_mm",
            "Power Module operator Base-XY correction",
        )
        rotated = Rotation.from_euler(
            "xyz", pick_abc, degrees=True
        ).as_matrix() @ np.array([tool_xy[0], tool_xy[1], 0.0])
        return rotated[:2] + operator_base_xy
    return _xy(
        recipe,
        "grasp_center_correction_base_mm",
        f"{part_type} Base-XY grasp correction",
    )


def _pick_z(
    recipe: Mapping[str, Any],
    surface_z_mm: float,
    part_type: str,
) -> tuple[float, str]:
    height = recipe.get("grasp_height")
    if isinstance(height, Mapping):
        position_mode = height.get("position_mode")
        if position_mode == "fixed_fixture_absolute":
            return (
                _finite_number(
                    height.get("taught_tcp_z_mm"),
                    f"{part_type} fixed pick TCP Z",
                ),
                "fixed_fixture_absolute",
            )
        if position_mode not in (None, "detected_surface_relative"):
            raise RuntimeError(
                f"unsupported {part_type} grasp-height mode {position_mode!r}"
            )
        offset = _finite_number(
            height.get("tcp_z_offset_from_detected_surface_mm"),
            f"{part_type} pick Z offset",
        )
        return float(surface_z_mm + offset), "detected_surface_relative"

    offset = _finite_number(
        recipe.get("grasp_z_offset_from_detected_surface_mm"),
        f"{part_type} pick Z offset",
    )
    return float(surface_z_mm + offset), "detected_surface_relative"


def _gripper_positions(
    recipe: Mapping[str, Any], part_type: str
) -> tuple[int, int, int]:
    if part_type == "black_block":
        horizontal = recipe.get("horizontal")
        if not isinstance(horizontal, Mapping):
            raise RuntimeError("missing VRM horizontal gripper recipe")
        return (
            _command_position(horizontal.get("tray_pick_open"), "VRM tray-open"),
            _command_position(horizontal.get("grip"), "VRM grip"),
            _command_position(horizontal.get("release"), "VRM release"),
        )

    release_command = recipe.get("release")
    tray_open_command = recipe.get("tray_pick_open", release_command)
    return (
        _command_position(tray_open_command, f"{part_type} tray-open"),
        _command_position(recipe.get("grip"), f"{part_type} grip"),
        _command_position(release_command, f"{part_type} release"),
    )


def _recipe_table(recipe_config: Mapping[str, Any]) -> Mapping[str, Any]:
    parts = recipe_config.get("parts")
    if isinstance(parts, Mapping):
        return parts
    return recipe_config


def _slot_table(slot_config: Any) -> dict[str, Mapping[str, Any]]:
    values = slot_config.get("slots") if isinstance(slot_config, Mapping) else slot_config
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise RuntimeError("slot configuration must contain a slots array")
    result: dict[str, Mapping[str, Any]] = {}
    for value in values:
        if not isinstance(value, Mapping):
            raise RuntimeError("slot configuration contains a non-object entry")
        code = str(value.get("slot_code", ""))
        if not code or code in result:
            raise RuntimeError(f"invalid or duplicate slot code {code!r}")
        result[code] = value
    return result


def _tray_parts_by_type(
    snapshot: Mapping[str, Any],
    required_counts: Mapping[str, int] = EXPECTED_TRAY_COUNTS,
    required_indices: Mapping[str, list[int]] | None = None,
) -> dict[str, list[Mapping[str, Any]]]:
    tray_capture = snapshot.get("tray_capture")
    if not isinstance(tray_capture, Mapping):
        raise RuntimeError("snapshot has no tray capture")
    values = tray_capture.get("parts")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise RuntimeError("snapshot tray capture has no parts array")

    grouped: dict[str, list[Mapping[str, Any]]] = {
        part_type: [] for part_type in required_counts
    }
    for value in values:
        if not isinstance(value, Mapping):
            raise RuntimeError("snapshot tray capture contains a non-object part")
        part_type = str(value.get("part_type", ""))
        if part_type not in grouped:
            if part_type in EXPECTED_TRAY_COUNTS:
                continue
            raise RuntimeError(f"unexpected tray part type {part_type!r}")
        if bool(value.get("consumed", False)):
            raise RuntimeError(
                f"tray part {part_type}:{value.get('instance_index')} is consumed"
            )
        grouped[part_type].append(value)

    for part_type, expected_count in required_counts.items():
        parts = grouped[part_type]
        try:
            parts.sort(key=lambda item: int(item["instance_index"]))
            indices = [int(item["instance_index"]) for item in parts]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid {part_type} tray instance index") from exc
        if len(parts) != expected_count:
            raise RuntimeError(
                f"expected {expected_count} {part_type} detections, got {len(parts)}"
            )
        expected_indices = (required_indices[part_type] if required_indices is not None
                            else list(range(1, expected_count + 1)))
        if indices != expected_indices:
            raise RuntimeError(
                f"{part_type} tray instance indices must be {expected_indices}"
            )
    return grouped


def _validate_speeds(speeds_percent: Mapping[str, Any] | None) -> dict[str, int]:
    supplied = DEFAULT_SPEEDS_PERCENT if speeds_percent is None else speeds_percent
    result: dict[str, int] = {}
    for key in DEFAULT_SPEEDS_PERCENT:
        raw = _finite_number(supplied.get(key), f"{key} speed")
        value = int(raw)
        if raw != value or not 1 <= value <= 100:
            raise RuntimeError(f"invalid {key} speed {raw}")
        result[key] = value
    return result


def _plan_placement_orientation(
    *,
    slot_code: str,
    part_type: str,
    policy: Mapping[str, Any],
    slot: Mapping[str, Any],
    board_rotation: np.ndarray,
    pick_abc: list[float],
) -> tuple[list[float], dict[str, Any]]:
    mode = str(policy.get("mode", ""))
    gripper_axis = str(policy.get("gripper_axis", ""))
    if gripper_axis not in ("tool_x", "tool_y"):
        raise RuntimeError(f"{slot_code} has invalid gripper axis {gripper_axis!r}")
    symmetry = _finite_number(
        policy.get("symmetry_period_deg"), f"{slot_code} symmetry period"
    )
    if not 0.0 < symmetry <= 360.0:
        raise RuntimeError(f"{slot_code} symmetry period is outside (0, 360]")

    target_axis = slot_axis_base_angle_deg(
        board_rotation,
        _finite_number(slot.get("long_axis_board_deg"), f"{slot_code} slot axis"),
    )
    raw_preferred = REFERENCES[slot_code][1]
    preferred_c = (
        None
        if raw_preferred is None
        else _finite_number(raw_preferred, f"{slot_code} preferred TCP C")
    )
    tie_threshold = (
        10.0
        if slot_code == "GPU-01"
        else _finite_number(
            policy.get("preference_tie_threshold_deg", 5.0),
            f"{slot_code} preference tie threshold",
        )
    )

    if mode == PRESERVE_PICK_TCP_MODE:
        if part_type != "hbm":
            raise RuntimeError(
                f"{PRESERVE_PICK_TCP_MODE} is only valid for HBM, got {slot_code}"
            )
        current_axis = tool_axis_base_angle_deg(pick_abc, gripper_axis)
        # Copy the exact components.  Do not round, re-express, or run them
        # through an Euler conversion: equality is the no-rotation contract.
        place_abc = list(pick_abc)
        planned = {
            "current_axis_base_deg": float(current_axis),
            "target_axis_base_deg": float(current_axis),
            "diagnostic_slot_axis_base_deg": float(target_axis),
            "symmetry_period_deg": float(symmetry),
            "rotation_delta_deg": 0.0,
            "target_tcp_abc_deg": list(pick_abc),
            "preferred_tcp_c_deg": preferred_c,
        }
        maximum_rotation = 0.0
        skip_threshold = 0.0
        rotation_skipped = True
    elif mode == ALIGN_CARRIED_AXIS_MODE:
        maximum_rotation = _finite_number(
            policy.get("maximum_intentional_rotation_deg"),
            f"{slot_code} maximum intentional rotation",
        )
        if part_type == "right_white_brown":
            # Successful CAP01 rotates from near-zero pickup to near-180 place;
            # CAP02..05 place near +90. TCP transfer is staged; J6 step/bounds
            # remain independently enforced by controller preflight.
            maximum_rotation = 180.0
        skip_threshold = _finite_number(
            policy.get("skip_rotation_below_deg", 0.5),
            f"{slot_code} skip-rotation threshold",
        )
        if not 0.0 < maximum_rotation <= (185.0 if part_type == "marked_white" else 180.0) or skip_threshold < 0.0:
            raise RuntimeError(f"{slot_code} has an invalid rotation envelope")
        planned = plan_carried_part_orientation(
            pick_abc,
            target_axis,
            gripper_axis,
            symmetry,
            preferred_tcp_c_deg=preferred_c,
            preference_tie_threshold_deg=tie_threshold,
            lock_preferred_branch=True,
        )
        rotation_delta = float(planned["rotation_delta_deg"])
        if part_type == "marked_white" and rotation_delta < 0.0:
            rotation_delta += 360.0
            planned["rotation_delta_deg"] = rotation_delta
        if abs(rotation_delta) > maximum_rotation + 1e-6:
            raise RuntimeError(
                f"{slot_code} rotation {rotation_delta:.3f}deg exceeds "
                f"{maximum_rotation:.3f}deg"
            )
        rotation_skipped = abs(rotation_delta) <= skip_threshold
        place_abc = (
            list(pick_abc)
            if rotation_skipped
            else [float(value) for value in planned["target_tcp_abc_deg"]]
        )
    else:
        raise RuntimeError(f"{slot_code} has unsupported orientation mode {mode!r}")

    metadata = {
        "mode": mode,
        "target_axis_base_deg": float(target_axis),
        "gripper_axis": gripper_axis,
        "symmetry_period_deg": float(symmetry),
        "maximum_intentional_rotation_deg": float(maximum_rotation),
        "preference_tie_threshold_deg": float(tie_threshold),
        "skip_rotation_below_deg": float(skip_threshold),
        "preferred_tcp_c_deg": preferred_c,
        "rotation_delta_deg": float(planned["rotation_delta_deg"]),
        "rotation_skipped_in_plan": bool(rotation_skipped),
        "planned_from_pick": planned,
    }
    return place_abc, metadata


def build_plan(
    snapshot: Mapping[str, Any],
    recipe_config: Mapping[str, Any],
    slot_config: Any,
    *,
    snapshot_path: Path | str | None = None,
    created_unix: float | None = None,
    transfer_z_mm: float = 350.0,
    speeds_percent: Mapping[str, Any] | None = None,
    only_slot: str | None = None,
    selected_slots: Sequence[str] | None = None,
    phase: str = "full",
) -> dict[str, Any]:
    """Return a validated full-cycle or GPU-only plan; perform no I/O."""

    if snapshot.get("schema") != "fr5.fixed_fixture_cycle_snapshot/v1":
        raise RuntimeError("wrong fixed-cycle snapshot schema")
    required_indices = None
    if phase not in ("full", "non-smd", "smd"):
        raise RuntimeError("unknown assembly phase")
    if phase != "full" and (only_slot is not None or selected_slots is not None):
        raise RuntimeError("phase cannot be combined with slot selection")
    if phase != "full":
        if not snapshot.get("board_captured") or not snapshot.get("tray_captured"):
            raise RuntimeError("phase requires board and tray captures")
        if phase == "smd" and not snapshot.get("smd_close_captured"):
            raise RuntimeError("SMD phase requires SMDView measurement")
        selected_slot_parts = tuple((s,t) for s,t in SLOT_PART_SEQUENCE
            if (t == "right_white_brown") == (phase == "smd"))
        required_counts = {t:n for t,n in EXPECTED_TRAY_COUNTS.items()
            if (t == "right_white_brown") == (phase == "smd")}
    elif selected_slots is not None:
        requested = list(selected_slots)
        if only_slot is not None or not requested or len(requested) != len(set(requested)):
            raise RuntimeError('explicit selection must be nonempty, unique and not combined with only_slot')
        canonical = [s for s in SLOT_SEQUENCE if s in requested]
        if requested != canonical or any(s.startswith('CAP-') for s in requested):
            raise RuntimeError('explicit selection requires canonical non-SMD slots')
        if not snapshot.get('board_captured') or not snapshot.get('tray_captured'):
            raise RuntimeError('explicit selection requires fresh board and tray captures')
        if snapshot.get('authorized_selected_slots') != requested:
            raise RuntimeError('snapshot scope does not match requested slots')
        selected_slot_parts = tuple((s,t) for s,t in SLOT_PART_SEQUENCE if s in requested)
        required_indices = {}
        for s,t in selected_slot_parts:
            required_indices.setdefault(t, []).append(int(s.split('-')[1]))
        required_counts = {t:len(indices) for t,indices in required_indices.items()}
    elif only_slot is None:
        if not bool(snapshot.get("ready_for_continuous_execution")):
            raise RuntimeError("snapshot is not ready for continuous execution")
        selected_slot_parts = SLOT_PART_SEQUENCE
        required_counts = EXPECTED_TRAY_COUNTS
    else:
        partial_slot_types = {"GPU-01": "gpu", "HBM-01": "hbm"}
        part_type = partial_slot_types.get(only_slot)
        if part_type is None:
            raise RuntimeError(
                "partial planning is restricted to GPU-01 or HBM-01"
            )
        if not bool(snapshot.get("board_captured")) or not bool(
            snapshot.get("tray_captured")
        ):
            raise RuntimeError(
                f"{only_slot} planning requires fresh board and tray captures"
            )
        selected_slot_parts = ((only_slot, part_type),)
        required_counts = {part_type: 1}

    board_capture = snapshot.get("board_capture")
    if not isinstance(board_capture, Mapping):
        raise RuntimeError("snapshot has no board capture")
    board_transform = np.asarray(board_capture.get("T_base_board"), dtype=float)
    if board_transform.shape != (4, 4) or not np.all(np.isfinite(board_transform)):
        raise RuntimeError("snapshot has no finite 4x4 T_base_board")
    board_rotation = board_transform[:3, :3]

    recipes = _recipe_table(recipe_config)
    slots = _slot_table(slot_config)
    tray_parts = _tray_parts_by_type(snapshot, required_counts, required_indices)
    placements = snapshot.get("resolved_placements")
    if not isinstance(placements, Mapping):
        raise RuntimeError("snapshot has no resolved placements")

    transfer_z = _finite_number(transfer_z_mm, "transfer Z")
    speeds = _validate_speeds(speeds_percent)
    counters = {part_type: 0 for part_type in required_counts}
    incoming_c = 90.0
    planned_items: list[dict[str, Any]] = []

    for slot_code, part_type in selected_slot_parts:
        recipe = recipes.get(part_type)
        if not isinstance(recipe, Mapping):
            raise RuntimeError(f"missing recipe for {part_type}")
        slot = slots.get(slot_code)
        if not isinstance(slot, Mapping):
            raise RuntimeError(f"missing slot configuration for {slot_code}")

        detection = tray_parts[part_type][counters[part_type]]
        if detection.get("deferred_to_smd_close"):
            raise RuntimeError("SMDView validation required before using deferred SMD pick coordinates")
        counters[part_type] += 1
        surface = _finite_vector(
            detection.get("base_xyz_mm"), 3, f"{slot_code} tray surface"
        )
        tray_angle = _finite_number(
            detection.get("long_axis_angle_base_deg"), f"{slot_code} tray angle"
        )

        policy = recipe.get("placement_orientation_policy")
        if not isinstance(policy, Mapping):
            raise RuntimeError(f"missing placement orientation policy for {part_type}")
        validated_pm = recipe.get('validated_placement_centers', {}).get(slot_code)
        if validated_pm is not None:
            policy = dict(policy, skip_rotation_below_deg=0.0)
        gripper_axis = str(policy.get("gripper_axis", recipe.get("gripper_axis", "")))
        pick_policy = recipe.get("pick_orientation_policy", {})
        if not isinstance(pick_policy, Mapping):
            raise RuntimeError(f"{slot_code} has invalid pick orientation policy")
        grasp_axis_offset = _finite_number(
            pick_policy.get("grasp_axis_offset_from_detected_deg", 0.0),
            f"{slot_code} grasp-axis offset",
        )
        if part_type == 'black_block' and detection.get('angle_source') == 'vrm_four_edge_v1':
            grasp_axis_offset = 0.0
        if abs(grasp_axis_offset) > 5.0:
            raise RuntimeError(f"{slot_code} grasp-axis offset exceeds +/-5deg")
        pick_reference_c = REFERENCES[slot_code][0]
        pick_c = choose_symmetric_pick_c(
            tray_angle + grasp_axis_offset, gripper_axis, pick_reference_c
        )
        pick_abc = [-180.0, 0.0, float(pick_c)]
        correction = _pick_correction(recipe, part_type, pick_abc)
        pick_z, pick_z_mode = _pick_z(recipe, float(surface[2]), part_type)
        tray_open, grip, release = _gripper_positions(recipe, part_type)
        pick_final = [
            float(surface[0] + correction[0]),
            float(surface[1] + correction[1]),
            float(pick_z),
            *pick_abc,
        ]

        placement = placements.get(slot_code)
        if not isinstance(placement, Mapping) or not bool(
            placement.get("placement_ready")
        ):
            raise RuntimeError(f"{slot_code} placement is not ready")
        placement_part_type = placement.get("part_type")
        if placement_part_type is not None and str(placement_part_type) != part_type:
            raise RuntimeError(
                f"{slot_code} placement part type {placement_part_type!r} "
                f"does not match {part_type!r}"
            )
        place_xy = _finite_vector(
            placement.get("corrected_place_xy_base_mm"),
            2,
            f"{slot_code} place XY",
        )
        calibrated_place_z = _finite_number(
            placement.get("final_tcp_z_mm"), f"{slot_code} final place Z"
        )
        default_place_adjustment = _finite_number(
            recipe.get("board_place_z_adjustment_mm", 0.0),
            f"{slot_code} board place Z adjustment",
        )
        expected_overrides = ({f"CAP-{i:02}": (-1.7 if i == 1 else -2.4)
                               for i in range(1, 6)} if part_type == "right_white_brown" else {})
        overrides = recipe.get("board_place_z_adjustment_by_slot_mm", {})
        if (default_place_adjustment != (-1.9 if part_type == "right_white_brown" else -1.0 if part_type == "hbm" else -0.5 if part_type == "long_orange" else 0.0)
                or not isinstance(overrides, dict) or overrides != expected_overrides):
            raise RuntimeError(f"{slot_code} board place Z adjustment differs from operator-approved value")
        place_z_adjustment = _finite_number(overrides.get(slot_code, default_place_adjustment),
                                            f"{slot_code} selected board place Z adjustment")
        place_z = calibrated_place_z + COMMON_BOARD_PLACE_Z_RAISE_MM + place_z_adjustment
        place_abc, orientation = _plan_placement_orientation(
            slot_code=slot_code,
            part_type=part_type,
            policy=policy,
            slot=slot,
            board_rotation=board_rotation,
            pick_abc=pick_abc,
        )
        place_final = [
            float(place_xy[0]),
            float(place_xy[1]),
            float(place_z),
            *place_abc,
        ]

        pm_evidence = None
        if validated_pm is not None:
            if part_type != 'long_orange' or slot_code not in ('PM-03', 'PM-04') or validated_pm.get('mode') != 'observed_board_center_plus_carried_pick_offset_v1':
                raise RuntimeError('invalid validated PM placement correction')
            delta = _finite_vector(validated_pm['visible_center_shift_board_mm'], 2, 'PM board center shift')
            if np.linalg.norm(delta) > 5:
                raise RuntimeError('PM board center correction exceeds 5mm')
            static = _finite_vector(placement['place_tcp_compensation_base_mm'], 3, 'PM old slot correction')[:2]
            extra = _finite_vector(placement.get('place_tcp_correction_base_mm', [0, 0]), 2, 'PM old Base correction')
            carried = (Rotation.from_euler('xyz', place_abc, degrees=True).as_matrix()
                       @ Rotation.from_euler('xyz', pick_abc, degrees=True).as_matrix().T
                       @ np.r_[correction, 0.0])
            target = place_xy - static - extra + (board_rotation @ np.r_[delta, 0.0])[:2] + carried[:2]
            place_final[:2] = target.tolist()
            pm_evidence = dict(mode=validated_pm['mode'], visible_center_shift_board_mm=delta.tolist(),
                               carried_pick_offset_base_mm=carried.tolist())

        planned_items.append(
            {
                "slot_code": slot_code,
                "part_type": part_type,
                "tray_instance_index": int(detection["instance_index"]),
                "tray_surface_base_mm": [float(value) for value in surface],
                "tray_long_axis_base_deg": float(tray_angle),
                "pick_correction_base_mm": [
                    float(correction[0]),
                    float(correction[1]),
                ],
                "pick_z_mode": pick_z_mode,
                "pick_final_tcp": pick_final,
                "place_final_tcp": place_final,
                "calibrated_place_final_tcp_z_mm": float(calibrated_place_z),
                "board_place_z_adjustment_mm": place_z_adjustment,
                "board_place_common_z_raise_mm": COMMON_BOARD_PLACE_Z_RAISE_MM,
                "tray_open_position": tray_open,
                "grip_position": grip,
                "release_position": release,
                "placement_orientation": orientation,
            }
        )
        validate_item(planned_items[-1])
        planned_items[-1]['successful_direction_revision'] = REVISION
        if pm_evidence is not None:
            planned_items[-1]['validated_pm_placement'] = pm_evidence
        planned_items[-1]['pick_angle_source'] = detection.get('angle_source', 'tray_detector')
        if part_type == 'right_white_brown':
            planned_items[-1]['grasp_center_diagnostic'] = describe_center(
                recipe, surface[:2], pick_final[:2]
            )
        incoming_c = float(place_abc[2])

    inspection_reference = None
    if phase == "non-smd" or selected_slots is not None or only_slot in ("GPU-01", "HBM-01"):
        reference_parts = [p for values in tray_parts.values() for p in values]
        if all(p.get("reference_center_pixel") is not None for p in reference_parts):
            inspection_reference = {
                "handeye_sha256": snapshot["tray_capture"].get("handeye_sha256"),
                "parts": reference_parts,
                "bindings": [{"part_type": p["part_type"],
                    "physical_index": p["instance_index"],
                    "reference_center_pixel": _finite_vector(p["reference_center_pixel"], 2, "inspection reference pixel").tolist()}
                    for p in reference_parts],
            }
    timestamp = time.time() if created_unix is None else _finite_number(
        created_unix, "plan creation timestamp"
    )
    source = (
        "in_memory"
        if snapshot_path is None
        else str(Path(snapshot_path).expanduser().resolve())
    )
    return {
        "schema": "fr5.full_fixed_cycle_plan/v1",
        "created_unix": float(timestamp),
        "cycle_id": str(snapshot.get("cycle_id", "")),
        "snapshot": source,
        "tray_inspection_reference": inspection_reference,
        "source_captures": {
            "tray_captured_unix": snapshot.get("tray_capture", {}).get("captured_unix"),
            "board_captured_unix": snapshot.get("board_capture", {}).get("captured_unix"),
            "smd_captured_unix": snapshot.get("smd_close_capture", {}).get("captured_unix"),
        },
        "transfer_z_mm": float(transfer_z),
        "speeds_percent": speeds,
        "board_place_common_z_raise_mm": COMMON_BOARD_PLACE_Z_RAISE_MM,
        "motion_profile": MOTION_PROFILE,
        "robot_motion_authorized": False,
        "plan_selection": {
            "mode": (phase if phase != "full" else 'explicit_slots' if selected_slots is not None else
                     ('full_cycle' if only_slot is None else 'single_slot')),
            "requested_only_slot": only_slot,
            "selected_slots": [
                slot_code for slot_code, _ in selected_slot_parts
            ],
        },
        "cycle_overrides": {
            "GPU-01": {
                "preferred_tcp_c_deg": 180.0,
                "preference_tie_threshold_deg": 10.0,
            },
            "PM-01": {
                "pick_reference_tcp_c_deg": recipes["long_orange"]["grasp_center_correction_base_mm"]["reference_tcp_rz_deg"],
                "locked_place_reference_tcp_c_deg": 180.0,
            },
            "pick_symmetric_solution": {
                "rule": (
                    "choose the 180-degree-equivalent pick TCP C nearest the "
                    "previous planned place TCP C, except HBM and PM-01 use "
                    "their recorded pick references"
                )
            },
            "VRM": {
                "locked_place_reference_tcp_c_deg": 180.0,
                "source": "VRM-01 physical success 2026-09-04; opposite branch rejected after 2026-09-05 review",
            },
            "HBM": {
                "pick_reference_tcp_c_deg": 90.0,
                "locked_place_reference_tcp_c_deg": 180.0,
                "orientation_mode": str(
                    recipes["hbm"]["placement_orientation_policy"]["mode"]
                )
            },
        },
        "plan": planned_items,
        "status": "planned_not_executed",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a 25-part frozen full-cycle plan; never move the robot."
    )
    parser.add_argument("--phase", choices=("full", "non-smd", "smd"), default="full")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--recipe-file", type=Path, default=DEFAULT_RECIPES)
    parser.add_argument("--slot-file", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--transfer-z-mm", type=float, default=350.0)
    parser.add_argument("--only-slot", choices=("GPU-01", "HBM-01"))
    parser.add_argument('--selected-slots', nargs='+', choices=SLOT_SEQUENCE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_plan(
        load_json(args.snapshot),
        load_json(args.recipe_file),
        load_json(args.slot_file),
        snapshot_path=args.snapshot,
        transfer_z_mm=args.transfer_z_mm,
        only_slot=args.only_slot,
        selected_slots=args.selected_slots,
        phase=args.phase,
    )
    atomic_write_json(args.output, payload)
    print(
        f"FULL PLAN READY: {len(payload['plan'])} parts -> "
        f"{args.output.resolve()}"
    )
    for item in payload["plan"]:
        print(
            f"{item['slot_code']:<6} "
            f"pickXYZC={[round(item['pick_final_tcp'][index], 3) for index in (0, 1, 2, 5)]} "
            f"placeXYZC={[round(item['place_final_tcp'][index], 3) for index in (0, 1, 2, 5)]} "
            f"rotation={item['placement_orientation']['rotation_delta_deg']:.3f}deg"
        )
    print("ROBOT DID NOT MOVE")


if __name__ == "__main__":
    main()
