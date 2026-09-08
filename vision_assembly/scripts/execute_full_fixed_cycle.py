#!/usr/bin/env python3
"""Preflight and execute the permanent smooth fixed-fixture cycle plan.

The executor intentionally separates physical proof from command completion.
For a fresh GPU run it must stop after the 100 mm proof lift.  A second,
explicit resume invocation is required after the operator confirms that the
GPU is actually held.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import signal
import threading
import time
from pathlib import Path

import numpy as np
import rclpy
from scipy.spatial.transform import Rotation

from execute_cached_hbm_remaining import Executor, atomic_write, init_executor_ros
from execution_safety import STATE_MAX_AGE_SEC, STOP_RPC_TIMEOUT_SEC, STOP_FEEDBACK_TIMEOUT_SEC
from full_cycle_motion import (
    DEFAULT_J6_OPERATIONAL_BOUNDS_DEG,
    MotionPlanError,
    MotionWaypoint,
    build_canonical_slot_waypoints,
    validate_joint_path,
    normalize_controller_tcp,
)
from full_cycle_plan import ALIGN_CARRIED_AXIS_MODE, MOTION_PROFILE, SLOT_SEQUENCE
from placement_orientation import tool_axis_base_angle_deg
from successful_gripper_directions import MAX_FINE_ANGLE_DEG, validate_item as validate_successful_direction


ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / "vision_assembly"
DEFAULT_PLAN = VISION / "data/full_cycle_plan.json"
DEFAULT_RUN_RECORD = VISION / "data/full_cycle_run.json"
RUN_SCHEMA = "fr5.full_fixed_cycle_run/v2"
GLOBAL_SPEED_PERCENT = 40
REQUIRED_SPEEDS_PERCENT = {
    "travel": 25,
    "combined_rotation": 25,
    "vertical": 10,
    "high_transfer": 40,
    "clearance_lift": 30,
}
REQUIRED_BOARD_PLACE_Z_RAISE_MM = 0.3


@dataclass(frozen=True)
class PreflightWaypoint:
    slot_code: str
    label: str
    tcp: tuple[float, float, float, float, float, float]
    linear: bool
    speed_percent: int
    reference_joints: tuple[float, float, float, float, float, float]
    target_joints: tuple[float, float, float, float, float, float]
    minimum_soft_limit_margin_deg: float


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def load_plan_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload, hashlib.sha256(raw).hexdigest()


def pose_error(actual: list[float], expected: list[float]) -> tuple[float, float]:
    position = float(
        np.linalg.norm(np.asarray(actual[:3], dtype=float) - np.asarray(expected[:3], dtype=float))
    )
    actual_rotation = Rotation.from_euler("xyz", actual[3:], degrees=True)
    expected_rotation = Rotation.from_euler("xyz", expected[3:], degrees=True)
    angle = math.degrees((actual_rotation.inv() * expected_rotation).magnitude())
    return position, float(angle)

def finite_abc(value: object, label: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must contain three finite values") from exc
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise RuntimeError(f"{label} must contain three finite values")
    return result


def finite_orientation_value(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise RuntimeError(f"{label} must be finite")
    return result


def symmetric_axis_error_deg(first: float, second: float, period: float) -> float:
    if not 0.0 < period <= 360.0:
        raise RuntimeError("orientation symmetry period must be in (0, 360]")
    return abs(
        (float(first) - float(second) + period / 2.0) % period - period / 2.0
    )


def checked_tool_axis_angle(abc: np.ndarray, axis: str, label: str) -> float:
    try:
        return float(tool_axis_base_angle_deg(abc.tolist(), axis))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{label} has an invalid gripper axis or ABC") from exc


def validate_plan(
    payload: dict,
    maximum_age_sec: float,
    requested_only_slot: str | None = None,
    requested_selected_slots: list[str] | None = None,
) -> list[dict]:
    if payload.get("schema") != "fr5.full_fixed_cycle_plan/v1":
        raise RuntimeError("wrong full-cycle plan schema")
    if payload.get("motion_profile") != MOTION_PROFILE:
        raise RuntimeError(
            f"plan must use {MOTION_PROFILE}; split rotate/horizontal plans are forbidden"
        )
    if payload.get("speeds_percent") != REQUIRED_SPEEDS_PERCENT:
        raise RuntimeError(
            "plan speed contract mismatch; required "
            f"{REQUIRED_SPEEDS_PERCENT}, got {payload.get('speeds_percent')}"
        )
    common_place_raise = finite_orientation_value(
        payload.get("board_place_common_z_raise_mm"),
        "board place common Z raise",
    )
    if abs(common_place_raise - REQUIRED_BOARD_PLACE_Z_RAISE_MM) > 1e-9:
        raise RuntimeError(
            "plan board-place Z raise mismatch; required "
            f"{REQUIRED_BOARD_PLACE_Z_RAISE_MM}mm, got {common_place_raise}mm"
        )
    age = time.time() - float(payload.get("created_unix", math.nan))
    if not math.isfinite(age) or age < -5.0 or age > maximum_age_sec:
        raise RuntimeError(f"full-cycle plan is stale ({age:.1f}s)")
    items = payload.get("plan")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise RuntimeError("full-cycle plan must contain a plan-object array")
    actual_sequence = tuple(str(item.get("slot_code")) for item in items)
    selection = payload.get("plan_selection")
    if requested_selected_slots is not None:
        scope=tuple(requested_selected_slots)
        if (not scope or len(scope)!=len(set(scope))
            or scope!=tuple(s for s in SLOT_SEQUENCE if s in scope)
            or any(s.startswith('CAP-') for s in scope)
            or actual_sequence!=scope):
            raise RuntimeError('explicit remaining scope mismatch')
        if (not isinstance(selection,dict) or selection.get('mode')!='explicit_slots'
            or selection.get('selected_slots')!=list(scope)):
            raise RuntimeError('explicit selection metadata mismatch')
        for item in items:
            if item.get('tray_instance_index')!=int(item['slot_code'].split('-')[1]):
                raise RuntimeError('explicit physical instance mismatch')
        captures=payload.get('source_captures',{})
        for key in ('tray_captured_unix','board_captured_unix'):
            source_age=time.time()-float(captures.get(key,math.nan))
            if not math.isfinite(source_age) or not 0<=source_age<=maximum_age_sec:
                raise RuntimeError('explicit capture is stale')
    elif len(items) == len(SLOT_SEQUENCE):
        if actual_sequence != SLOT_SEQUENCE:
            raise RuntimeError("full-cycle slot order is invalid")
        if selection is not None and (
            not isinstance(selection, dict)
            or selection.get("mode") != "full_cycle"
            or selection.get("requested_only_slot") is not None
            or selection.get("selected_slots") != list(SLOT_SEQUENCE)
        ):
            raise RuntimeError("full-cycle plan selection metadata is invalid")
    elif isinstance(selection, dict) and selection.get("mode") in ("non-smd", "smd"):
        expected = tuple(s for s in SLOT_SEQUENCE
                         if s.startswith("CAP-") == (selection["mode"] == "smd"))
        if (actual_sequence != expected or selection.get("selected_slots") != list(expected)
                or selection.get("requested_only_slot") is not None):
            raise RuntimeError("assembly phase scope mismatch")
    elif len(items) == 1:
        if requested_only_slot is None:
            raise RuntimeError("single-slot plan requires matching CLI --only-slot")
        if actual_sequence != (requested_only_slot,):
            raise RuntimeError("single-slot plan does not match CLI --only-slot")
        if (
            not isinstance(selection, dict)
            or selection.get("mode") != "single_slot"
            or selection.get("requested_only_slot") != requested_only_slot
            or selection.get("selected_slots") != [requested_only_slot]
        ):
            raise RuntimeError("single-slot plan selection metadata is invalid")
    else:
        raise RuntimeError("plan must contain the full 25 slots or one scoped slot")
    for item in items:
        validate_successful_direction(item)
        slot_code = str(item.get("slot_code", "UNKNOWN"))
        place_tcp = item.get("place_final_tcp")
        if not isinstance(place_tcp, list) or len(place_tcp) != 6:
            raise RuntimeError(f"{slot_code} place TCP must contain six values")
        calibrated_place_z = finite_orientation_value(
            item.get("calibrated_place_final_tcp_z_mm"),
            f"{slot_code} calibrated place Z",
        )
        item_place_raise = finite_orientation_value(
            item.get("board_place_common_z_raise_mm"),
            f"{slot_code} common place Z raise",
        )
        place_adjustment = finite_orientation_value(
            item.get("board_place_z_adjustment_mm", 0.0), f"{slot_code} board place Z adjustment")
        expected_adjustment = ((-1.7 if slot_code == "CAP-01" else -2.4)
                               if item.get("part_type") == "right_white_brown" else
                               -1.0 if item.get("part_type") == "hbm" else -0.5 if item.get("part_type") == "long_orange" else 0.0)
        if (
            abs(item_place_raise - common_place_raise) > 1e-9
            or abs(place_adjustment - expected_adjustment) > 1e-9
            or abs(float(place_tcp[2]) - calibrated_place_z - common_place_raise - place_adjustment) > 1e-6
        ):
            raise RuntimeError(f"{slot_code} common board-place Z raise is inconsistent")
        if item.get("part_type") not in ("hbm", "black_block"):
            continue
        slot_code = str(item.get("slot_code", "UNKNOWN"))
        part_label = "VRM" if item.get("part_type") == "black_block" else "HBM"
        policy = item.get("placement_orientation")
        if (
            not isinstance(policy, dict)
            or policy.get("mode") != ALIGN_CARRIED_AXIS_MODE
        ):
            raise RuntimeError(
                f"{slot_code} must align the carried {part_label} axis to the slot axis"
            )

        pick_tcp = item.get("pick_final_tcp")
        place_tcp = item.get("place_final_tcp")
        if not isinstance(pick_tcp, list) or len(pick_tcp) != 6:
            raise RuntimeError(f"{slot_code} {part_label} pick TCP must contain six values")
        if not isinstance(place_tcp, list) or len(place_tcp) != 6:
            raise RuntimeError(f"{slot_code} {part_label} place TCP must contain six values")
        pick_abc = finite_abc(pick_tcp[3:], f"{slot_code} {part_label} pick ABC")
        place_abc = finite_abc(place_tcp[3:], f"{slot_code} {part_label} place ABC")

        gripper_axis = str(policy.get("gripper_axis", ""))
        symmetry = finite_orientation_value(
            policy.get("symmetry_period_deg"), f"{slot_code} {part_label} symmetry period"
        )
        maximum_rotation = finite_orientation_value(
            policy.get("maximum_intentional_rotation_deg"),
            f"{slot_code} {part_label} maximum rotation",
        )
        skip_threshold = finite_orientation_value(
            policy.get("skip_rotation_below_deg"),
            f"{slot_code} {part_label} skip threshold",
        )
        rotation_delta = finite_orientation_value(
            policy.get("rotation_delta_deg"), f"{slot_code} {part_label} rotation delta"
        )
        if not 0.0 < maximum_rotation <= 180.0 or skip_threshold < 0.0:
            raise RuntimeError(f"{slot_code} {part_label} rotation envelope is invalid")
        if abs(rotation_delta) > maximum_rotation + 1e-6:
            raise RuntimeError(f"{slot_code} {part_label} rotation exceeds its envelope")
        skipped = policy.get("rotation_skipped_in_plan")
        if not isinstance(skipped, bool):
            raise RuntimeError(f"{slot_code} {part_label} rotation-skipped flag is invalid")

        planned = policy.get("planned_from_pick")
        if not isinstance(planned, dict):
            raise RuntimeError(f"{slot_code} {part_label} has no rotation plan from pick")
        planned_delta = finite_orientation_value(
            planned.get("rotation_delta_deg"),
            f"{slot_code} {part_label} planned rotation delta",
        )
        if abs(planned_delta - rotation_delta) > 1e-6:
            raise RuntimeError(f"{slot_code} {part_label} rotation metadata is inconsistent")
        target_axis = finite_orientation_value(
            policy.get("target_axis_base_deg"), f"{slot_code} {part_label} target axis"
        )
        planned_target_axis = finite_orientation_value(
            planned.get("target_axis_base_deg"),
            f"{slot_code} {part_label} planned target axis",
        )
        if symmetric_axis_error_deg(
            target_axis, planned_target_axis, 360.0
        ) > 1e-6:
            raise RuntimeError(
                f"{slot_code} {part_label} target-axis metadata is inconsistent"
            )
        planned_target_abc = finite_abc(
            planned.get("target_tcp_abc_deg"),
            f"{slot_code} {part_label} planned target ABC",
        )

        pick_axis = checked_tool_axis_angle(
            pick_abc, gripper_axis, f"{slot_code} {part_label} pick"
        )
        target_abc_axis = checked_tool_axis_angle(
            planned_target_abc, gripper_axis, f"{slot_code} {part_label} planned target"
        )
        if symmetric_axis_error_deg(
            target_abc_axis, target_axis, symmetry
        ) > 1e-5:
            raise RuntimeError(
                f"{slot_code} {part_label} target ABC does not align to slot axis"
            )
        if symmetric_axis_error_deg(
            pick_axis + rotation_delta, target_axis, symmetry
        ) > 1e-5:
            raise RuntimeError(
                f"{slot_code} {part_label} rotation delta does not reach slot axis"
            )

        if skipped:
            if abs(rotation_delta) > skip_threshold + 1e-6:
                raise RuntimeError(f"{slot_code} {part_label} skipped a required rotation")
            if not np.allclose(place_abc, pick_abc, rtol=0.0, atol=1e-6):
                raise RuntimeError(
                    f"{slot_code} {part_label} skipped rotation but changed place ABC"
                )
        else:
            if abs(rotation_delta) <= skip_threshold + 1e-9:
                raise RuntimeError(
                    f"{slot_code} {part_label} rotation skip metadata is inconsistent"
                )
            if not np.allclose(
                place_abc, planned_target_abc, rtol=0.0, atol=1e-6
            ):
                raise RuntimeError(
                    f"{slot_code} {part_label} place ABC differs from planned target ABC"
                )
        if symmetric_axis_error_deg(place_abc[2], 180.0, 360.0) >= 90.0:
            raise RuntimeError(f"{slot_code} {part_label} place uses the opposite C180 branch")
        place_axis = checked_tool_axis_angle(
            place_abc, gripper_axis, f"{slot_code} {part_label} place"
        )
        allowed_residual = skip_threshold + 1e-6 if skipped else 1e-5
        if symmetric_axis_error_deg(
            place_axis, target_axis, symmetry
        ) > allowed_residual:
            raise RuntimeError(
                f"{slot_code} {part_label} place axis does not align to slot axis"
            )
    return items


def select_items(
    items: list[dict],
    only_slot: str | None,
    start_slot: str | None,
    end_slot: str | None,
) -> list[dict]:
    if only_slot is not None:
        if start_slot is not None or end_slot is not None:
            raise RuntimeError("--only-slot cannot be combined with start/end")
        if len(items) == 1:
            if str(items[0].get("slot_code")) != only_slot:
                raise RuntimeError("single-slot plan does not match CLI --only-slot")
            return items
        start_slot = end_slot = only_slot
    start = SLOT_SEQUENCE[0] if start_slot is None else start_slot
    end = SLOT_SEQUENCE[-1] if end_slot is None else end_slot
    if start not in SLOT_SEQUENCE or end not in SLOT_SEQUENCE:
        raise RuntimeError("start/end slot is not in the fixed 25-slot sequence")
    start_index = SLOT_SEQUENCE.index(start)
    end_index = SLOT_SEQUENCE.index(end)
    if start_index > end_index:
        raise RuntimeError("start slot must not follow end slot")
    selected = [item for item in items
                if start_index <= SLOT_SEQUENCE.index(item['slot_code']) <= end_index]
    if not selected:
        raise RuntimeError("no slots selected")
    return selected


def waypoint_speed(label: str, speeds: dict) -> int:
    # Dedicated high-clearance speeds: never accelerate the contact zone.
    # Older camera/recovery callers keep their explicitly supplied speeds.
    if label == 'tray_after_raise':
        return int(speeds.get('clearance_lift', speeds['vertical']))
    high_transfer = {
        'pick_combined_xy_abc', 'pick_combined_xy_abc_midpoint',
        'place_combined_xy_abc', 'place_combined_xy_abc_midpoint',
        'tray_after_mid_travel', 'tray_after_travel',
    }
    if label in high_transfer and 'high_transfer' in speeds:
        return int(speeds['high_transfer'])
    if label.startswith('tray_'):
        return int(speeds['combined_rotation'] if label.endswith(('travel','return')) else speeds['vertical'])
    if label in ("pick_combined_xy_abc", "pick_combined_xy_abc_midpoint", "place_combined_xy_abc", "place_combined_xy_abc_midpoint"):
        return min(int(speeds["travel"]), int(speeds["combined_rotation"]))
    if label in (
        "pick_final_50mm_vertical",
        "post_grasp_lift_50mm_vertical",
        "place_final_50mm_vertical",
        "post_release_lift_50mm_vertical",
    ):
        return int(speeds["vertical"])
    return int(speeds["travel"])


def build_tcp_route(
    selected: list[dict],
    start_tcp: list[float],
    transfer_z_mm: float,
    *,
    resume_after_grasp: bool,
) -> list[tuple[str, object]]:
    route: list[tuple[str, object]] = []
    preceding_tcp = list(start_tcp)
    for index, item in enumerate(selected):
        policy = item.get("placement_orientation", {})
        waypoints = build_canonical_slot_waypoints(
            preceding_tcp,
            item["pick_final_tcp"],
            item["place_final_tcp"],
            item.get('transfer_z_mm', transfer_z_mm),
            part_type=item.get("part_type"),
            orientation_policy_mode=policy.get("mode"),
        )
        if item['slot_code'] in ('HBM-07', 'PM-03', 'PM-04', 'VRM-02', 'VRM-03', 'VRM-04', 'VRM-05', 'IND-01', 'IND-02') or item.get('part_type') == 'right_white_brown':
            origin=waypoints[0].tcp
            target=list(waypoints[1].tcp)
            for axis in (3,4,5):
                target[axis]=origin[axis]+(target[axis]-origin[axis]+180)%360-180
            fractions=(1/3,2/3) if item['slot_code']=='PM-03' or item.get('part_type') == 'right_white_brown' else (.5,)
            if item['slot_code'] in ('IND-01', 'IND-02') or item.get('part_type') == 'right_white_brown':
                if target[5]>origin[5]:target[5]-=360
                fractions=(1/3,2/3)
            midpoints=tuple(MotionWaypoint('pick_combined_xy_abc_midpoint',
                tuple(origin[k]+f*(target[k]-origin[k]) for k in range(6)),False) for f in fractions)
            waypoints=waypoints[:1]+midpoints+waypoints[1:]
        if item["slot_code"] in ("HBM-01", "HBM-02", "HBM-03", "HBM-05", "HBM-07", "HBM-08", "HBM-04", "HBM-06", "PM-03", "VRM-01", "VRM-02", "VRM-03", "VRM-04", "VRM-05", "CAP-02", "CAP-03", "CAP-04", "CAP-05"):
            place_index = next(
                waypoint_index
                for waypoint_index, waypoint in enumerate(waypoints)
                if waypoint.label == "place_combined_xy_abc"
            )
            origin = waypoints[place_index - 1].tcp
            target = waypoints[place_index].tcp
            fractions = (1.0 / 3.0, 2.0 / 3.0) if item["slot_code"] in ("HBM-04", "VRM-05", "CAP-01", "CAP-02", "CAP-03", "CAP-04", "CAP-05") else (0.5,)
            interpolation_target = list(target)
            # Equivalent +/-180 roll must not interpolate through zero and
            # tip the held part. Preserve the nearest roll/pitch representation.
            for axis in (3, 4):
                interpolation_target[axis] = origin[axis] + (
                    (target[axis] - origin[axis] + 180.0) % 360.0 - 180.0
                )
            interpolation_target[5] = origin[5] + (
                (target[5] - origin[5] + 180.0) % 360.0 - 180.0
            )
            midpoints = tuple(
                MotionWaypoint(
                    "place_combined_xy_abc_midpoint",
                    tuple(
                        origin[axis] + fraction * (interpolation_target[axis] - origin[axis])
                        for axis in range(6)
                    ),
                    False,
                )
                for fraction in fractions
            )
            waypoints = (
                waypoints[:place_index] + midpoints + waypoints[place_index:]
            )
        if item.get("part_type") == "marked_white" or item["slot_code"] == "CAP-01":
            place_index = next(i for i, w in enumerate(waypoints)
                               if w.label == "place_combined_xy_abc")
            origin = waypoints[place_index - 1].tcp
            target = list(waypoints[place_index].tcp)
            delta = (target[5] - origin[5]) % 360.0
            # CAP01 retains its successful positive transfer from the fixed
            # near-zero pick branch to the fixed near-180 place branch.
            # Allow both endpoints' already-validated fine-angle deviations;
            # every segment and J6 limit is still checked by controller IK.
            maximum_transfer = 180.0 + 2 * MAX_FINE_ANGLE_DEG if item["slot_code"] == "CAP-01" else 185.0
            if delta > maximum_transfer:
                raise MotionPlanError("Positive transfer exceeds successful endpoint envelope")
            for axis in (3, 4):
                target[axis] = origin[axis] + (target[axis] - origin[axis] + 180) % 360 - 180
            target[5] = origin[5] + delta
            segments = max(1, math.ceil(delta / 60.0))
            staged = tuple(MotionWaypoint("place_combined_xy_abc_midpoint",
                tuple(origin[k] + (target[k] - origin[k]) * step / segments
                      for k in range(6)), False)
                for step in range(1, segments))
            waypoints = waypoints[:place_index] + staged + waypoints[place_index:]
        if resume_after_grasp and index == 0:
            carry_index = next(
                (
                    waypoint_index
                    for waypoint_index, waypoint in enumerate(waypoints)
                    if waypoint.label == "carry_safe_vertical"
                ),
                None,
            )
            if carry_index is None:
                raise MotionPlanError("canonical route has no carry-safe waypoint")
            waypoints = waypoints[carry_index:]
        route.extend((item["slot_code"], waypoint) for waypoint in waypoints)
        preceding_tcp = list(waypoints[-1].tcp)
    return route


def preflight_route(
    node: Executor,
    route: list[tuple[str, object]],
    initial_joints: np.ndarray,
    speeds: dict,
) -> tuple[list[PreflightWaypoint], dict]:
    soft = node.response_values(
        node.service("GetJointSoftLimitDeg(1)"), 12, "joint soft-limit"
    )
    negative, positive = soft[:6], soft[6:]
    safety_stop = node.response_values(
        node.service("GetSafetyStopState()"), 2, "safety-stop"
    )
    if np.any(safety_stop != 0.0):
        raise RuntimeError(
            f"safety stop is active: {safety_stop.astype(int).tolist()}"
        )

    reference = np.asarray(initial_joints, dtype=float)
    planned: list[PreflightWaypoint] = []
    target_joint_rows: list[tuple[float, ...]] = []
    minimum_margin = math.inf
    for slot_code, waypoint in route:
        target = list(normalize_controller_tcp(waypoint.tcp))
        j6_lower, j6_upper = DEFAULT_J6_OPERATIONAL_BOUNDS_DEG

        def referenced_ik(seed: np.ndarray) -> np.ndarray:
            request = "GetInverseKinRef(" + ",".join(
                f"{value:.6f}" for value in [0.0, *target, *seed.tolist()]
            ) + ")"
            candidate = node.response_values(
                node.service(request),
                6,
                f"referenced IK for {slot_code}:{waypoint.label}",
            )
            equivalent_j6 = [
                float(candidate[5]) + 360.0 * turns
                for turns in range(-2, 3)
                if j6_lower - 1e-9
                <= float(candidate[5]) + 360.0 * turns
                <= j6_upper + 1e-9
            ]
            if equivalent_j6:
                candidate[5] = min(
                    equivalent_j6,
                    key=lambda value: abs(value - float(reference[5])),
                )
            return candidate

        candidates = [referenced_ik(reference)]
        first_margins = np.minimum(candidates[0] - negative, positive - candidates[0])
        first_step = float(np.max(np.abs(candidates[0] - reference)))
        if (
            float(np.min(first_margins)) < 10.0
            or not j6_lower <= float(candidates[0][5]) <= j6_upper
            or first_step > 95.0
        ):
            for offset in (-360.0, -270.0, -180.0, -90.0, 90.0, 180.0, 270.0, 360.0):
                seed = reference.copy()
                seed[5] += offset
                try:
                    candidates.append(referenced_ik(seed))
                except RuntimeError:
                    continue
        joints = min(
            candidates,
            key=lambda candidate: (
                float(np.min(np.minimum(candidate - negative, positive - candidate))) < 10.0,
                not j6_lower <= float(candidate[5]) <= j6_upper,
                float(np.max(np.abs(candidate - reference))) > 95.0,
                float(np.max(np.abs(candidate - reference))),
            ),
        )
        margins = np.minimum(joints - negative, positive - joints)
        waypoint_margin = float(np.min(margins))
        if waypoint_margin < 10.0:
            joint = int(np.argmin(margins)) + 1
            raise RuntimeError(
                f"{slot_code}:{waypoint.label} J{joint} soft-limit margin "
                f"{margins[joint - 1]:.3f}deg is below 10deg"
            )
        planned.append(
            PreflightWaypoint(
                slot_code=slot_code,
                label=waypoint.label,
                tcp=tuple(target),
                linear=bool(waypoint.linear),
                speed_percent=waypoint_speed(waypoint.label, speeds),
                reference_joints=tuple(float(value) for value in reference),
                target_joints=tuple(float(value) for value in joints),
                minimum_soft_limit_margin_deg=waypoint_margin,
            )
        )
        target_joint_rows.append(tuple(float(value) for value in joints))
        minimum_margin = min(minimum_margin, waypoint_margin)
        reference = joints

    joint_validation = validate_joint_path(
        target_joint_rows,
        initial_joints_deg=initial_joints.tolist(),
    )
    return planned, {
        "passed": True,
        "waypoints": len(planned),
        "minimum_joint_soft_limit_margin_deg": minimum_margin,
        "maximum_joint_step_deg": joint_validation.maximum_step_deg,
        "minimum_j6_deg": joint_validation.minimum_j6_deg,
        "maximum_j6_deg": joint_validation.maximum_j6_deg,
        "j6_operational_bounds_deg": list(DEFAULT_J6_OPERATIONAL_BOUNDS_DEG),
    }


def move_preflighted(node: Executor, waypoint: PreflightWaypoint) -> list[float]:
    state = node.spin_state(timeout_sec=STATE_MAX_AGE_SEC)
    error = node.safety_error(state)
    if error:
        raise RuntimeError("FR5 safety state is not clear: " + error)
    current_joints = node.state_joints(state)
    reference = np.asarray(waypoint.reference_joints, dtype=float)
    reference_error = float(np.max(np.abs(current_joints - reference)))
    if not math.isfinite(reference_error) or reference_error > 1.5:
        raise RuntimeError(
            f"{waypoint.slot_code}:{waypoint.label} preflight reference drift "
            f"{reference_error:.3f}deg exceeds 1.5deg"
        )
    define = "JNTPoint(1," + ",".join(
        f"{value:.6f}" for value in waypoint.target_joints
    ) + ")"
    command_name = "MoveL" if waypoint.linear else "MoveJ"
    command = f"{command_name}(JNT1,{waypoint.speed_percent},1,0)"
    print(
        f"{waypoint.slot_code}:{waypoint.label} "
        f"target={[round(value, 3) for value in waypoint.tcp]} "
        f"joints={[round(value, 3) for value in waypoint.target_joints]} "
        f"command={command}",
        flush=True,
    )
    node.service(define)
    # Defining the joint point is a separate RPC; recheck its reference after it.
    state = node.spin_state(timeout_sec=STATE_MAX_AGE_SEC)
    error = node.safety_error(state)
    if error or int(state.robot_motion_done) != 1:
        raise RuntimeError("FR5 is not stationary/safe before preflighted motion: " + (error or "moving"))
    def require_reference(sample):
        error_deg = float(np.max(np.abs(node.state_joints(sample) - reference)))
        if not math.isfinite(error_deg) or error_deg > 1.5:
            raise RuntimeError("preflight reference drift before motion command")
    require_reference(state)
    # Validate the same fresh sample used by service after durable journalling;
    # a reference checked before that write may no longer describe the robot.
    node.service(command, state_validator=require_reference)
    result = node.wait_pose(
        list(waypoint.tcp), np.asarray(waypoint.target_joints, dtype=float)
    )
    print(
        f"VERIFIED {waypoint.slot_code}:{waypoint.label}: "
        f"{[round(value, 3) for value in result]}",
        flush=True,
    )
    return result


def read_gripper_current_percent(node: Executor) -> float:
    values = node.response_values(
        node.service("GetGripperCurCurrent()"), 2, "gripper current"
    )
    if int(values[0]) != 0:
        raise RuntimeError(f"gripper current query fault={int(values[0])}")
    return float(values[1])


def initial_record(
    args: argparse.Namespace,
    payload: dict,
    selected: list[dict],
    plan_sha256: str,
) -> dict:
    return {
        "schema": RUN_SCHEMA,
        "started_unix": time.time(),
        "cycle_id": payload.get("cycle_id"),
        "plan_file": str(args.plan_file.resolve()),
        "plan_sha256": plan_sha256,
        "motion_profile": payload.get("motion_profile"),
        "selected_slots": [item["slot_code"] for item in selected],
        "motion_completed_slots": [],
        "grasp_verified_slots": [],
        "placement_verified_slots": [],
        "part_held_candidate": None,
        "holding_state": "unknown",
        "holding_evidence": "no gripper command verified in this run",
        "commands": [],
        "status": "preflighting",
    }


def begin_action(record: dict, path: Path, *, slot: str, kind: str, label: str, **target) -> dict:
    commands = record.setdefault("commands", [])
    action = {"command_id": len(commands) + 1, "slot": slot, "kind": kind,
              "waypoint": label, "status": "preparing", "intent_unix": time.time(), **target}
    commands.append(action)
    record["active_command_id"] = action["command_id"]
    atomic_write(path, record)
    return action


def record_gripper(node, record, path, item, waypoint, position, purpose):
    # A close/release timeout can happen after the controller acted. Preserve
    # uncertainty before entering any RPC or feedback wait, including Ctrl-C.
    record.update(part_held_candidate=None, held_slot=waypoint.slot_code,
                  holding_state="unknown", holding_evidence=f"{purpose}_requested")
    action = begin_action(record, path, slot=waypoint.slot_code, kind="gripper",
                          label=waypoint.label, target_position=int(position), purpose=purpose)
    node.gripper(int(position), f"{waypoint.slot_code} {purpose}")
    action.update(status="verified", verified_unix=time.time())
    record["last_gripper_position"] = int(position)
    if purpose == "grasp":
        record.update(part_held_candidate=True, holding_state="candidate",
                      holding_evidence="close_feedback_verified_not_physical_holding_proof")
    else:
        record.update(part_held_candidate=False, holding_state=f"{purpose}_command_verified",
                      holding_evidence="open_feedback_verified_not_physical_absence_proof")
        record.pop("held_slot", None)
    atomic_write(path, record)


def record_fault_and_stop(node, record, path, exc):
    # The launcher may have sent SIGINT. Ignore repeated Ctrl-C only during the
    # bounded cleanup; SIGTERM/SIGKILL remain available to the launcher.
    previous_sigint = None
    previous_sigterm = None
    if threading.current_thread() is threading.main_thread():
        previous_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
        previous_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
    def persist():
        try:
            atomic_write(path, record)
        except Exception as write_exc:
            # A full/broken disk must not prevent the stop request itself.
            error = f"{type(write_exc).__name__}: {write_exc}"
            record.setdefault("fault_record_write_errors", []).append(error)
            print("FAULT RECORD WRITE FAILED: " + error, flush=True)
    try:
        stop = {"command": "StopMotion()", "intent_unix": time.time(),
                "rpc_timeout_sec": STOP_RPC_TIMEOUT_SEC, "status": "requested",
                "succeeded": None, "feedback_verified_stopped": False}
        record.update(status="stopped_on_error", error=f"{type(exc).__name__}: {exc}",
                      fault_recorded_unix=time.time(), stop_motion_on_error=stop)
        if record.get("commands"):
            record["commands"][-1]["failure"] = record["error"]
        # This record must survive a delayed stop RPC or forced process exit.
        persist()
        stop["attempted_unix"] = time.time()
        persist()
        try:
            stop["response"] = node.service("StopMotion()")
            stop.update(succeeded=True, status="acknowledged")
        except BaseException as stop_exc:
            stop.update(succeeded=False, status="rpc_failed",
                        error=f"{type(stop_exc).__name__}: {stop_exc}")
        stop["rpc_finished_unix"] = time.time()
        persist()
        try:
            record["stop_observation"] = node.observe_stop(
                after_sequence=node.state_sequence, timeout_sec=STOP_FEEDBACK_TIMEOUT_SEC)
            stop["feedback_verified_stopped"] = record["stop_observation"]["feedback_verified_stopped"]
            latest = record["stop_observation"].get("latest_feedback")
            if latest:
                record["last_gripper_position"] = latest["gripper_position"]
                record["last_gripper_position_source"] = "stop_observation"
        except BaseException as observation_exc:
            record["stop_observation"] = {
                "feedback_verified_stopped": False,
                "error": f"{type(observation_exc).__name__}: {observation_exc}",
            }
        # Keep the last *verified waypoint* intact even if stopped elsewhere.
        record["stopped_unix"] = time.time()
        persist()
    finally:
        if previous_sigint is not None:
            signal.signal(signal.SIGINT, previous_sigint)
        if previous_sigterm is not None:
            signal.signal(signal.SIGTERM, previous_sigterm)


def validate_start_state(node: Executor) -> object:
    state = node.spin_state()
    if int(state.robot_mode) != 0:
        raise RuntimeError("AUTO mode required")
    if int(state.tool_num) != 1 or int(state.work_num) != 0:
        raise RuntimeError("expected Tool1/User0")
    if int(state.robot_motion_done) != 1:
        raise RuntimeError("robot must be stationary")
    error = node.safety_error(state)
    if error:
        raise RuntimeError("unsafe start state: " + error)
    return state


def execute(
    args: argparse.Namespace,
    payload: dict,
    selected: list[dict],
    plan_sha256: str,
) -> None:
    if payload.get('execution_scope') == 'placement_review_hover_only' and not getattr(args, 'stop_before_place', False):
        raise RuntimeError('review plan forbids final placement; stop-before-place required')
    if getattr(args, 'stop_before_place', False):
        if len(selected) != 1 or args.resume_held or args.stop_after_grasp or getattr(args, 'stop_after_close', False):
            raise RuntimeError('stop-before-place requires one fresh slot and no other pause/resume mode')
    resume = bool(args.resume_held)
    if resume:
        record = load_json(args.run_record)
        first_slot = selected[0]["slot_code"]
        if record.get("schema") != RUN_SCHEMA:
            raise RuntimeError("resume run record schema mismatch")
        if record.get("status") != "paused_after_grasp_verification_required":
            raise RuntimeError("run record is not paused after a grasp")
        if record.get("held_slot") != first_slot:
            raise RuntimeError("resume slot does not match held slot")
        if record.get("cycle_id") != payload.get("cycle_id"):
            raise RuntimeError("resume plan cycle does not match run record")
        if str(Path(record.get("plan_file", "")).resolve()) != str(args.plan_file.resolve()):
            raise RuntimeError("resume plan file does not match run record")
        if record.get("plan_sha256") != plan_sha256:
            raise RuntimeError("resume plan SHA-256 does not match run record")
    else:
        record = initial_record(args, payload, selected, plan_sha256)
        if getattr(args,'continuation_payload',None):
            record['motion_completed_slots']=list(args.continuation_payload['motion_completed_slots'])
            record['continued_from']=str(args.continue_record.resolve())
        atomic_write(args.run_record, record)

    init_executor_ros()
    node = Executor()
    def command_event(stage, command, response):
        if record.get("commands"):
            action = record["commands"][-1]
            action.update(status=stage, command=command)
            action[f"{stage}_unix"] = time.time()
            if response is not None:
                action["response"] = response
            action["state_sequence"] = node.state_sequence
            action["state_age_sec"] = time.monotonic() - node.state_received_monotonic
            atomic_write(args.run_record, record)
    node.command_event_hook = command_event
    try:
        if not node.client.wait_for_service(timeout_sec=8.0):
            raise RuntimeError("FR5 command service unavailable")
        state = validate_start_state(node)
        start_tcp = node.snapshot()
        node.assert_gripper_ready()
        if getattr(args,'continuation_payload',None):
            from tray_home_gate import HOME
            p,a=pose_error(start_tcp,list(HOME))
            if p>1 or a>1 or int(state.gripper_position)!=25:
                raise RuntimeError('empty-gripper continuation requires TrayHome/gripper25')

        first = selected[0]
        if resume:
            expected_hover = list(first["pick_final_tcp"])
            expected_hover[2] += 100.0
            position_error, angle_error = pose_error(start_tcp, expected_hover)
            if position_error > 1.0 or angle_error > 1.0:
                raise RuntimeError(
                    f"held-part resume pose mismatch: position={position_error:.3f}mm, "
                    f"orientation={angle_error:.3f}deg"
                )
            if int(state.gripper_position) != int(first["grip_position"]):
                raise RuntimeError(
                    f"held-part resume expects gripper={first['grip_position']}, "
                    f"got {state.gripper_position}"
                )
            if first["slot_code"] not in record["grasp_verified_slots"]:
                record["grasp_verified_slots"].append(first["slot_code"])
            record["operator_confirmed_held_unix"] = time.time()
            record.update(part_held_candidate=True, holding_state="operator_confirmed",
                          holding_evidence="explicit_operator_confirmation")
            record["status"] = "running_after_operator_grasp_confirmation"

        route = build_tcp_route(
            selected,
            start_tcp,
            float(payload["transfer_z_mm"]),
            resume_after_grasp=resume,
        )
        if (getattr(args,'tray_home_reference',None) or getattr(args,'inspect_picks',False)):
            from tray_home_gate import add_inspections
            route=add_inspections(route,start_tcp)
        preflighted, preflight_summary = preflight_route(
            node,
            route,
            node.state_joints(state),
            payload["speeds_percent"],
        )
        record["preflight"] = preflight_summary
        record["status"] = (
            "running_after_operator_grasp_confirmation" if resume else "running"
        )
        atomic_write(args.run_record, record)
        print(
            f"PREFLIGHT PASSED: {preflight_summary['waypoints']} waypoints, "
            f"max_step={preflight_summary['maximum_joint_step_deg']:.3f}deg, "
            f"J6=[{preflight_summary['minimum_j6_deg']:.3f}, "
            f"{preflight_summary['maximum_j6_deg']:.3f}]deg",
            flush=True,
        )

        node.service(f"SetSpeed({GLOBAL_SPEED_PERCENT})")
        record["controller_global_speed_percent"] = GLOBAL_SPEED_PERCENT
        record["speed_contract"] = {
            "command_percent": dict(REQUIRED_SPEEDS_PERCENT),
            "effective_percent": {
                key: GLOBAL_SPEED_PERCENT * value / 100.0
                for key, value in REQUIRED_SPEEDS_PERCENT.items()
            },
            "hover_clearance_mm": 100.0,
            "slow_zone_mm": 50.0,
        }
        record["controller_global_speed_set_unix"] = time.time()
        atomic_write(args.run_record, record)

        item_by_slot = {item["slot_code"]: item for item in selected}
        for waypoint in preflighted:
            item = item_by_slot[waypoint.slot_code]
            if (getattr(args,'tray_home_reference',None) or getattr(args,'inspect_picks',False)) and waypoint.label in ('pick_final_50mm_vertical','place_final_50mm_vertical'):
                for capture_key in ('tray_captured_unix','board_captured_unix'):
                    age=time.time()-float(payload['source_captures'][capture_key])
                    if not 0<=age<=args.maximum_plan_age_sec:
                        raise RuntimeError('source capture expired during batch')
            action = begin_action(record, args.run_record, slot=waypoint.slot_code,
                                  kind="motion", label=waypoint.label,
                                  target_tcp=list(waypoint.tcp))
            verified_tcp = move_preflighted(node, waypoint)
            action.update(status="verified", verified_unix=time.time(),
                          verified_tcp=list(verified_tcp),
                          feedback=getattr(node, "last_pose_verification", None))
            record["last_verified_tcp"] = list(verified_tcp)
            record["last_verified_waypoint"] = dict(action)
            feedback = action["feedback"]
            if feedback:
                record["last_gripper_position"] = feedback["gripper_position"]
            atomic_write(args.run_record, record)

            if waypoint.label in ('tray_before_inspect','tray_after_inspect'):
                from tray_home_gate import wait_inventory, HOME
                position,angle=pose_error(node.snapshot(),list(HOME))
                if position>1 or angle>1:raise RuntimeError('TrayHome inspection pose mismatch')
                node.assert_gripper_ready()
                removed=set(record['motion_completed_slots'])
                if waypoint.label=='tray_after_inspect':
                    if int(node.state.gripper_position)!=int(item['grip_position']):
                        raise RuntimeError('gripper changed before tray removal check')
                    removed.add(waypoint.slot_code)
                evidence=wait_inventory(node,VISION/'data/tray_detections_last.json',
                    args.tray_home_payload,removed,
                    load_json(VISION/'config/part_gripper_recipes.json')['tray_snapshot_quality'],
                    picked_slot=waypoint.slot_code)
                record.setdefault('tray_inspections',[]).append(dict(slot=waypoint.slot_code,
                    stage=waypoint.label,**evidence))
                atomic_write(args.run_record,record)
                print('TRAY INSPECTION PASSED '+waypoint.slot_code+' '+waypoint.label,flush=True)

            if waypoint.label == "pick_hover_100mm_vertical":
                record_gripper(node, record, args.run_record, item, waypoint,
                               item["tray_open_position"], "pre_pick_open")
            elif waypoint.label == "pick_final_50mm_vertical":
                record_gripper(node, record, args.run_record, item, waypoint,
                               item["grip_position"], "grasp")
                record.setdefault("gripper_current_samples_percent", {})[
                    waypoint.slot_code
                ] = read_gripper_current_percent(node)
                atomic_write(args.run_record, record)
                if getattr(args,'stop_after_close',False):
                    record['status']='paused_after_close_visual_confirmation_required'
                    record['paused_unix']=time.time()
                    atomic_write(args.run_record,record)
                    print('PAUSED AFTER CLOSE: NO LIFT OR BOARD TRANSFER',flush=True)
                    return
            elif (
                waypoint.label == "post_grasp_proof_lift_100mm_vertical"
                and args.stop_after_grasp
            ):
                record["status"] = "paused_after_grasp_verification_required"
                record["last_gripper_position"] = int(node.state.gripper_position)
                record["paused_unix"] = time.time()
                atomic_write(args.run_record, record)
                print(
                    f"PAUSED AFTER {waypoint.slot_code} 100MM PROOF LIFT; "
                    "NO BOARD TRANSFER OR ROTATION WAS COMMANDED",
                    flush=True,
                )
                return
            elif (waypoint.label == "place_approach_50mm_vertical"
                  and getattr(args, 'stop_before_place', False)):
                record['status'] = 'paused_before_place_visual_confirmation_required'
                record['last_gripper_position'] = int(node.state.gripper_position)
                record['paused_unix'] = time.time()
                record['placement_clearance_mm'] = 50.0
                atomic_write(args.run_record, record)
                print('PAUSED 50MM ABOVE PLACEMENT: NO FINAL DESCENT OR RELEASE', flush=True)
                return
            elif waypoint.label == "place_final_50mm_vertical":
                record_gripper(node, record, args.run_record, item, waypoint,
                               item["release_position"], "release")
            elif waypoint.label == "post_release_lift_100mm_vertical":
                if waypoint.slot_code not in record["motion_completed_slots"]:
                    record["motion_completed_slots"].append(waypoint.slot_code)
                record["last_gripper_position"] = int(node.state.gripper_position)
                atomic_write(args.run_record, record)
                print(
                    f"MOTION SEQUENCE COMPLETED {waypoint.slot_code}; "
                    "PHYSICAL PLACEMENT NOT YET CLAIMED",
                    flush=True,
                )

        record["status"] = "motion_complete_awaiting_physical_verification"
        record["completed_unix"] = time.time()
        atomic_write(args.run_record, record)
        print("SELECTED MOTION SEQUENCES COMPLETED", flush=True)
    except BaseException as exc:
        record_fault_and_stop(node, record, args.run_record, exc)
        raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def dry_run(args: argparse.Namespace, payload: dict, selected: list[dict]) -> None:
    init_executor_ros()
    node = Executor()
    try:
        if not node.client.wait_for_service(timeout_sec=8.0):
            raise RuntimeError("FR5 command service unavailable")
        state = validate_start_state(node)
        start_tcp = node.snapshot()
        route = build_tcp_route(
            selected,
            start_tcp,
            float(payload["transfer_z_mm"]),
            resume_after_grasp=False,
        )
        if (getattr(args,'tray_home_reference',None) or getattr(args,'inspect_picks',False)):
            from tray_home_gate import add_inspections
            route=add_inspections(route,start_tcp)
        _, summary = preflight_route(
            node,
            route,
            node.state_joints(state),
            payload["speeds_percent"],
        )
        print(
            f"DRY PREFLIGHT PASSED: slots={[item['slot_code'] for item in selected]}, "
            f"waypoints={summary['waypoints']}, "
            f"max_step={summary['maximum_joint_step_deg']:.3f}deg, "
            f"J6=[{summary['minimum_j6_deg']:.3f}, {summary['maximum_j6_deg']:.3f}]deg"
        )
        print("ROBOT AND GRIPPER DID NOT MOVE")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-file", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--run-record", type=Path, default=DEFAULT_RUN_RECORD)
    parser.add_argument("--only-slot", choices=SLOT_SEQUENCE)
    parser.add_argument('--selected-slots',nargs='+',choices=SLOT_SEQUENCE)
    parser.add_argument('--tray-home-reference',type=Path)
    parser.add_argument('--continue-record',type=Path)
    parser.add_argument("--start-slot", choices=SLOT_SEQUENCE)
    parser.add_argument("--end-slot", choices=SLOT_SEQUENCE)
    parser.add_argument("--maximum-plan-age-sec", type=float, default=1800.0)
    parser.add_argument("--verify-tray-pick", action="store_true", help="continue after fresh TrayHome cell-removal verification")
    parser.add_argument("--stop-after-grasp", action="store_true")
    parser.add_argument("--stop-before-place", action="store_true", help="hold 50mm above placement without final descent or release; single fresh slot only")
    parser.add_argument('--stop-after-close',action='store_true')
    parser.add_argument("--resume-held", action="store_true")
    parser.add_argument("--confirm-held-part", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-cycle", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        parser.error("choose exactly one of --dry-run or --execute")
    if args.execute != args.confirm_cycle:
        parser.error("execution requires --execute --confirm-cycle")
    if args.resume_held != args.confirm_held_part:
        parser.error("held-part resume requires --resume-held --confirm-held-part")
    if args.stop_after_grasp and args.resume_held:
        parser.error("stop-after-grasp and resume-held cannot be combined")
    if args.stop_after_close and (args.only_slot is None or args.resume_held or args.stop_after_grasp):
        parser.error('stop-after-close requires only-slot and cannot combine with resume/stop-after-grasp')
    if args.stop_after_grasp and args.only_slot is None:
        parser.error("--stop-after-grasp requires --only-slot")
    if args.resume_held and args.only_slot is None and args.start_slot is None:
        parser.error("--resume-held requires --only-slot or --start-slot")
    if args.execute and args.only_slot == "GPU-01" and not args.resume_held:
        if not args.stop_after_grasp and not args.verify_tray_pick:
            parser.error("a fresh GPU execution requires --stop-after-grasp or --verify-tray-pick")
    if not args.maximum_plan_age_sec > 0.0:
        parser.error("--maximum-plan-age-sec must be positive")
    return args


def main() -> None:
    args = parse_args()
    payload, plan_sha256 = load_plan_json(args.plan_file)
    if payload.get('execution_scope')=='close_only_no_lift_or_board' and not (
        args.only_slot=='HBM-02' and args.stop_after_close and not args.resume_held
    ):
        raise RuntimeError('retry plan permits HBM02 close-only, never lift/board transfer')
    items = validate_plan(
        payload, args.maximum_plan_age_sec, requested_only_slot=args.only_slot,
        requested_selected_slots=args.selected_slots
    )
    selected = select_items(items, args.only_slot, args.start_slot, args.end_slot)
    args.inspect_picks = args.verify_tray_pick or payload.get("plan_selection", {}).get("mode") == "non-smd"
    if args.inspect_picks:
        if any(i["slot_code"].startswith("CAP-") for i in selected):
            raise RuntimeError("TrayHome pick verification is for non-SMD parts")
        args.tray_home_payload = payload.get("tray_inspection_reference")
        if args.execute and not args.tray_home_payload:
            raise RuntimeError("non-SMD execution requires a fresh TrayHome capture with cell reference pixels")
    if args.continue_record:
        previous=load_json(args.continue_record)
        completed=previous.get('motion_completed_slots',[])
        if (not args.tray_home_reference or previous.get('schema')!=RUN_SCHEMA
            or previous.get('status')!='stopped_on_error'
            or previous.get('part_held_candidate') is not False or previous.get('held_slot')
            or previous.get('plan_sha256')!=plan_sha256 or previous.get('cycle_id')!=payload.get('cycle_id')
            or not completed or completed!=[i['slot_code'] for i in selected[:len(completed)]]):
            raise RuntimeError('continuation requires matching stopped empty-gripper prefix record')
        if args.execute and args.run_record.exists():
            raise RuntimeError('continuation must use a new output record')
        args.continuation_payload=previous
        selected=selected[len(completed):]
        if not selected:raise RuntimeError('nothing remains')
    if args.tray_home_reference:
        if args.resume_held or args.only_slot or args.start_slot or args.end_slot or args.stop_after_grasp or args.stop_after_close:
            raise RuntimeError('TrayHome batch requires full explicit remaining scope; no resume or partial range')
        reference=load_json(args.tray_home_reference)
        if reference.get('authorized_selected_slots')!=[i['slot_code'] for i in items]:
            raise RuntimeError('TrayHome reference scope mismatch')
        if str(args.tray_home_reference.resolve())!=str(Path(payload['source_captures']['tray_file']).resolve()):
            raise RuntimeError('TrayHome reference differs from plan source')
        args.tray_home_payload=reference
    if (
        args.execute
        and selected[0]["slot_code"] == "GPU-01"
        and not args.resume_held
        and not args.stop_after_grasp
        and not args.inspect_picks
    ):
        raise RuntimeError(
            "a fresh cycle beginning at GPU-01 must run GPU alone with "
            "--stop-after-grasp before any board transfer"
        )
    try:
        if args.dry_run:
            dry_run(args, payload, selected)
        else:
            execute(args, payload, selected, plan_sha256)
    except MotionPlanError as exc:
        raise RuntimeError(f"motion plan rejected: {exc}") from exc


if __name__ == "__main__":
    main()
