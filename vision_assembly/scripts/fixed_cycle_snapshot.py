#!/usr/bin/env python3
"""Freeze one board view and one tray view for a fixed-fixture assembly cycle.

This utility never commands the robot. It resolves every board slot from the
single 3D board-pose result and records the full-tray detections for later use.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np

from placement_orientation import slot_axis_base_angle_deg


ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / "vision_assembly"
DEFAULT_OUTPUT = VISION / "data/fixed_cycle_snapshot.json"
DEFAULT_SMD_CLOSE = VISION / "data/smd_close_targets_current.json"
DEFAULT_BOARD = VISION / "data/board_pose_3d_live.json"
DEFAULT_TRAY = VISION / "data/tray_detections_last.json"
DEFAULT_SLOTS = VISION / "config/assembly_slots_r1.json"
DEFAULT_RECIPES = VISION / "config/part_gripper_recipes.json"

SLOT_SEQUENCE = (
    ["GPU-01"]
    + [f"HBM-{index:02d}" for index in range(1, 9)]
    + [f"PM-{index:02d}" for index in range(1, 5)]
    + [f"VRM-{index:02d}" for index in range(1, 6)]
    + [f"IND-{index:02d}" for index in range(1, 3)]
    + [f"CAP-{index:02d}" for index in range(1, 6)]
)
PART_TYPE = {
    "GPU": "gpu",
    "HBM": "hbm",
    "PM": "long_orange",
    "VRM": "black_block",
    "IND": "marked_white",
    "CAP": "right_white_brown",
}
EXPECTED_TRAY_COUNTS = {
    "gpu": 1,
    "hbm": 8,
    "long_orange": 4,
    "black_block": 5,
    "marked_white": 2,
    "right_white_brown": 5,
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_vector(value, length: int, label: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise RuntimeError(f"{label} must contain {length} finite values")
    return vector

QUALITY_METRIC_FIELDS = {
    "minimum_detection_confidence": "median_detection_confidence",
    "minimum_mask_shape_score": "median_mask_shape_score",
    "minimum_rectangularity": "median_rectangularity",
}


def validate_tray_detection_quality(detection: dict, quality_config: dict) -> dict:
    part = str(detection.get("part_type", ""))
    instance = detection.get("instance_index", "?")
    part_config = quality_config.get("parts", {}).get(part)
    if not isinstance(part_config, dict):
        raise RuntimeError(f"missing tray quality gate for {part!r}")

    reasons = []
    observation_frames = int(detection.get("observation_frames", 0))
    minimum_frames = int(quality_config.get("minimum_observation_frames", 1))
    if observation_frames < minimum_frames:
        reasons.append(
            f"observation_frames={observation_frames} < {minimum_frames}"
        )

    metrics = {"observation_frames": observation_frames}
    for threshold_name, field_name in QUALITY_METRIC_FIELDS.items():
        raw_value = detection.get(field_name)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            reasons.append(f"missing {field_name}")
            continue
        if not math.isfinite(value):
            reasons.append(f"non-finite {field_name}")
            continue
        minimum = float(part_config[threshold_name])
        metrics[field_name] = round(value, 6)
        if value < minimum:
            reasons.append(f"{field_name}={value:.3f} < {minimum:.3f}")

    if reasons:
        raise RuntimeError(
            f"tray quality gate failed for {part}:{instance}: "
            + "; ".join(reasons)
        )
    return metrics



def fresh(path: Path, maximum_age_sec: float) -> float:
    age = time.time() - path.stat().st_mtime
    if age < -5.0 or age > maximum_age_sec:
        raise RuntimeError(f"{path.name} is stale ({age:.1f}s)")
    return age


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def base_payload() -> dict:
    return {
        "schema": "fr5.fixed_fixture_cycle_snapshot/v1",
        "cycle_id": time.strftime("%Y%m%d-%H%M%S"),
        "created_unix": time.time(),
        "mode": "fixed_board_and_tray_one_capture_per_cycle",
        "robot_motion_authorized": False,
        "capture_sequence": ["PlaceCamera board", "TrayHome full tray", "SMDView CAP angles"],
        "invalidation_rules": [
            "invalidate if the PCB, fixture, or tray is touched or moved",
            "invalidate after collision, emergency stop, or unexpected contact",
            "invalidate a pick target after that frozen tray item is consumed",
            "recapture after a failed grasp or uncertain part identity",
            "recapture both TrayHome and SMDView after any CAP moves in the tray",
        ],
        "motion_invariants": {
            "travel_speed_percent": 40,
            "vertical_clearance_mm": 100.0,
            "vertical_speed_percent": 20,
            "forbid_simultaneous_xy_z_change": True,
            "require_vertical_retract_before_rotation_or_horizontal_motion": True,
        },
        "board_captured": False,
        "tray_captured": False,
        "smd_close_captured": False,
        "ready_for_continuous_execution": False,
    }


def resolve_placement(
    code: str,
    surface: np.ndarray,
    slot: dict,
    recipe: dict,
    board_rotation: np.ndarray,
) -> dict:
    board_xy = finite_vector(
        slot.get("place_tcp_compensation_board_mm", [0.0, 0.0]),
        2,
        f"{code} board correction",
    )
    board_correction = board_rotation @ np.array([board_xy[0], board_xy[1], 0.0])
    base_xy = finite_vector(
        slot.get("place_tcp_correction_base_mm", [0.0, 0.0]),
        2,
        f"{code} Base correction",
    )
    corrected = surface + board_correction + np.array([base_xy[0], base_xy[1], 0.0])
    reasons: list[str] = []

    legacy_abc_value = slot.get("placement_tcp_abc_deg")
    try:
        legacy_abc = finite_vector(
            legacy_abc_value, 3, f"{code} legacy placement orientation"
        ).tolist()
    except (RuntimeError, TypeError, ValueError):
        legacy_abc = None

    policy = recipe.get("placement_orientation_policy")
    if not isinstance(policy, dict) or policy.get("mode") != "align_actual_carried_axis_to_current_slot_axis":
        orientation = None
        reasons.append("missing carried-axis-to-slot-axis placement policy")
    else:
        try:
            gripper_axis = str(policy["gripper_axis"])
            if gripper_axis not in ("tool_x", "tool_y"):
                raise ValueError("invalid gripper axis")
            symmetry = float(policy["symmetry_period_deg"])
            maximum_rotation = float(policy["maximum_intentional_rotation_deg"])
            long_axis_board = float(slot["long_axis_board_deg"])
            target_axis_base = slot_axis_base_angle_deg(
                board_rotation, long_axis_board
            )
            preferred_c = slot.get("preferred_tcp_c_deg")
            if preferred_c is not None:
                preferred_c = float(preferred_c)
            if not all(math.isfinite(value) for value in (
                symmetry, maximum_rotation, long_axis_board, target_axis_base
            )):
                raise ValueError("non-finite orientation policy")
            if not 0.0 < symmetry <= 360.0 or not 0.0 < maximum_rotation <= 180.0:
                raise ValueError("orientation policy outside safe range")
            orientation = {
                "mode": policy["mode"],
                "gripper_axis": gripper_axis,
                "symmetry_period_deg": symmetry,
                "maximum_intentional_rotation_deg": maximum_rotation,
                "preference_tie_threshold_deg": float(
                    policy.get("preference_tie_threshold_deg", 5.0)
                ),
                "skip_rotation_below_deg": float(
                    policy.get("skip_rotation_below_deg", 0.5)
                ),
                "slot_long_axis_board_deg": long_axis_board,
                "slot_long_axis_base_deg": target_axis_base,
                "preferred_tcp_c_deg": preferred_c,
            }
        except (KeyError, TypeError, ValueError) as exc:
            orientation = None
            reasons.append(f"invalid carried-axis placement policy: {exc}")

    if "placement_surface_to_tcp_z_offset_mm" in recipe:
        z_offset = float(recipe["placement_surface_to_tcp_z_offset_mm"])
        if not math.isfinite(z_offset):
            reasons.append("invalid placement surface-to-TCP Z offset")
            final_z = None
            z_mode = "missing"
        else:
            final_z = float(corrected[2] + z_offset)
            z_mode = "surface_relative"
    elif "placement_final_tcp_z_mm" in recipe:
        final_z = float(recipe["placement_final_tcp_z_mm"])
        if not math.isfinite(final_z):
            reasons.append("invalid absolute final TCP Z")
            final_z = None
            z_mode = "missing"
        else:
            z_mode = "fixed_fixture_absolute"
    else:
        final_z = None
        z_mode = "missing"
        reasons.append("final placement Z is not physically validated")

    return {
        "slot_code": code,
        "part_type": PART_TYPE[code.split("-", 1)[0]],
        "surface_base_mm": np.round(surface, 6).tolist(),
        "place_tcp_compensation_board_mm": np.round(board_xy, 6).tolist(),
        "place_tcp_compensation_base_mm": np.round(board_correction, 6).tolist(),
        "place_tcp_correction_base_mm": np.round(base_xy, 6).tolist(),
        "corrected_surface_base_mm": np.round(corrected, 6).tolist(),
        "corrected_place_xy_base_mm": np.round(corrected[:2], 6).tolist(),
        "final_tcp_z_mm": None if final_z is None else round(final_z, 6),
        "final_z_mode": z_mode,
        "placement_orientation": orientation,
        "legacy_absolute_placement_tcp_abc_deg": legacy_abc,
        "placement_ready": not reasons,
        "blocking_reasons": reasons,
    }


def capture_board(args: argparse.Namespace) -> dict:
    source_age = fresh(args.board_input, args.max_source_age_sec)
    board = load(args.board_input)
    if board.get("valid") is not True:
        raise RuntimeError("board pose is not valid")
    rms = float(board.get("hole_fit_rms_mm", math.inf))
    mad = float(board.get("plane_residual_mad_mm", math.inf))
    if rms > args.max_hole_fit_rms_mm:
        raise RuntimeError(f"board hole-fit RMS too high ({rms:.3f}mm)")
    if mad > args.max_plane_mad_mm:
        raise RuntimeError(f"board plane MAD too high ({mad:.3f}mm)")

    source_slots = board.get("slots", {})
    if set(source_slots) != set(SLOT_SEQUENCE):
        missing = sorted(set(SLOT_SEQUENCE) - set(source_slots))
        extra = sorted(set(source_slots) - set(SLOT_SEQUENCE))
        raise RuntimeError(f"board slot set mismatch; missing={missing}, extra={extra}")

    slot_config = {item["slot_code"]: item for item in load(args.slot_file)["slots"]}
    recipes = load(args.recipe_file)["parts"]
    transform = np.asarray(board["T_base_board"], dtype=float)
    if transform.shape != (4, 4) or not np.all(np.isfinite(transform)):
        raise RuntimeError("invalid T_base_board")
    rotation = transform[:3, :3]
    if abs(np.linalg.det(rotation) - 1.0) > 0.05:
        raise RuntimeError("invalid board rotation matrix")

    resolved = {}
    for code in SLOT_SEQUENCE:
        if code not in slot_config:
            raise RuntimeError(f"missing slot configuration for {code}")
        part = PART_TYPE[code.split("-", 1)[0]]
        if part not in recipes:
            raise RuntimeError(f"missing part recipe for {part}")
        surface = finite_vector(
            source_slots[code]["surface_base_mm"], 3, f"{code} surface"
        )
        resolved[code] = resolve_placement(
            code, surface, slot_config[code], recipes[part], rotation
        )

    payload = base_payload()
    payload.update(
        {
            "board_captured": True,
            "board_capture": {
                "captured_unix": time.time(),
                "source_file": str(args.board_input.resolve()),
                "source_age_sec": round(source_age, 3),
                "hole_fit_rms_mm": rms,
                "plane_residual_mad_mm": mad,
                "T_base_board": transform.tolist(),
                "slot_count": len(resolved),
            },
            "resolved_placements": resolved,
        }
    )
    update_readiness(payload)
    return payload


def load_smd_close_angles(args: argparse.Namespace) -> tuple[dict[int, dict], dict]:
    source_age = fresh(args.smd_close_input, args.max_smd_close_age_sec)
    payload = load(args.smd_close_input)
    captured_unix = float(payload.get("timestamp_unix", math.nan))
    capture_age = time.time() - captured_unix
    if not math.isfinite(capture_age) or capture_age < -5.0 or capture_age > args.max_smd_close_age_sec:
        raise RuntimeError(f"SMD close capture is stale ({capture_age:.1f}s)")
    if payload.get("mode") != "smd_close_multiframe_base_targets":
        raise RuntimeError("SMD close input is not an all-instance batch")
    if payload.get("validation_passed") is not True:
        raise RuntimeError("SMD close batch validation did not pass")
    handeye_sha256 = str(payload.get("handeye_sha256", ""))
    if len(handeye_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in handeye_sha256.lower()
    ):
        raise RuntimeError("SMD close batch has no valid hand-eye calibration hash")

    parts = payload.get("parts", [])
    cycle_count = EXPECTED_TRAY_COUNTS["right_white_brown"]
    set_index = int(payload.get("set_index", -1))
    if set_index != args.smd_set_index:
        raise RuntimeError(
            f"SMD close set mismatch: requested {args.smd_set_index}, received {set_index}"
        )
    if int(payload.get("required_count", -1)) != cycle_count:
        raise RuntimeError("SMD close batch does not contain one five-part set")
    if int(payload.get("layout_capacity", -1)) != cycle_count * 2:
        raise RuntimeError("SMD close batch does not describe the 10-part fixture")
    if len(parts) != cycle_count:
        raise RuntimeError(
            f"expected {cycle_count} selected SMD close angles, received {len(parts)}"
        )
    resolved = {}
    for part in parts:
        if part.get("part_type") != "right_white_brown":
            raise RuntimeError("SMD close batch contains a non-CAP part")
        instance = int(part.get("instance_index", -1))
        physical_instance = int(part.get("physical_instance_index", -1))
        expected_physical = (set_index - 1) * cycle_count + instance
        if int(part.get("set_index", -1)) != set_index or physical_instance != expected_physical:
            raise RuntimeError(f"invalid SMD set mapping for cycle instance {instance}")
        if instance in resolved:
            raise RuntimeError(f"duplicate SMD close instance {instance}")
        if part.get("validation_passed") is not True:
            raise RuntimeError(f"SMD close instance {instance} did not validate")
        frame_count = int(part.get("frame_count", 0))
        confidence = float(part.get("confidence_median", math.nan))
        angle = float(part.get("long_axis_angle_base_deg", math.nan))
        if frame_count < args.min_smd_close_frames:
            raise RuntimeError(
                f"SMD close instance {instance} has only {frame_count} frames"
            )
        if not math.isfinite(confidence) or confidence < args.min_smd_close_confidence:
            raise RuntimeError(
                f"SMD close instance {instance} confidence is too low "
                f"({confidence:.3f})"
            )
        if not math.isfinite(angle):
            raise RuntimeError(f"SMD close instance {instance} angle is invalid")
        resolved[instance] = {
            "long_axis_angle_base_deg": angle,
            "confidence_median": confidence,
            "frame_count": frame_count,
            "physical_instance_index": physical_instance,
        }

    expected_instances = set(range(1, EXPECTED_TRAY_COUNTS["right_white_brown"] + 1))
    if set(resolved) != expected_instances:
        raise RuntimeError(
            f"SMD close instance set mismatch: {sorted(resolved)}"
        )
    metadata = {
        "source_file": str(args.smd_close_input.resolve()),
        "source_age_sec": round(source_age, 3),
        "captured_unix": captured_unix,
        "capture_age_sec": round(capture_age, 3),
        "handeye_sha256": handeye_sha256,
        "set_index": set_index,
        "physical_instance_indices": [resolved[index]["physical_instance_index"] for index in sorted(resolved)],
        "part_count": len(resolved),
        "angle_source": "SMD close-view robust OBB only",
    }
    return resolved, metadata


def capture_tray(args: argparse.Namespace, payload: dict) -> dict:
    if not payload.get("board_captured"):
        raise RuntimeError("capture the board first")
    source_age = fresh(args.tray_input, args.max_source_age_sec)
    tray = load(args.tray_input)
    if tray.get("tray_registration") != "TRACKING":
        raise RuntimeError("tray registration is not TRACKING")
    if tray.get("base_transform_status") not in ("OK", "VALID_COORDINATES_ONLY"):
        raise RuntimeError(
            f"tray Base transform invalid: {tray.get('base_transform_status')}"
        )
    handeye_sha256 = str(tray.get("handeye_sha256", ""))
    if len(handeye_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in handeye_sha256.lower()
    ):
        raise RuntimeError("tray detection has no valid hand-eye calibration hash")
    detections = tray.get("stable_detections", [])
    if len(detections) != sum(EXPECTED_TRAY_COUNTS.values()):
        raise RuntimeError(
            f"expected 25 stable tray detections, received {len(detections)}"
        )
    quality_config = load(args.recipe_file).get("tray_snapshot_quality")
    if not isinstance(quality_config, dict):
        raise RuntimeError("missing tray_snapshot_quality recipe")
    if set(quality_config.get("parts", {})) != set(EXPECTED_TRAY_COUNTS):
        raise RuntimeError("tray quality-gate part set does not match cycle parts")

    counts = {key: 0 for key in EXPECTED_TRAY_COUNTS}
    frozen = []
    for detection in detections:
        part = str(detection.get("part_type", ""))
        if part not in counts:
            raise RuntimeError(f"unexpected tray part type {part!r}")
        counts[part] += 1
        xyz = finite_vector(detection.get("base_xyz_mm"), 3, "tray Base XYZ")
        angle = float(detection.get("long_axis_angle_base_deg"))
        if not math.isfinite(angle):
            raise RuntimeError("invalid tray part angle")
        quality = validate_tray_detection_quality(detection, quality_config)
        frozen.append(
            {
                "part_type": part,
                "instance_index": int(detection["instance_index"]),
                "base_xyz_mm": np.round(xyz, 6).tolist(),
                "long_axis_angle_base_deg": round(angle, 6),
                "observation_frames": int(detection.get("observation_frames", 0)),
                "quality": quality,
                "consumed": False,
            }
        )
    if counts != EXPECTED_TRAY_COUNTS:
        raise RuntimeError(
            f"tray counts mismatch; expected={EXPECTED_TRAY_COUNTS}, actual={counts}"
        )
    frozen.sort(key=lambda item: (item["part_type"], item["instance_index"]))
    payload.pop("smd_close_capture", None)
    payload["tray_captured"] = True
    payload["smd_close_captured"] = False
    payload["tray_capture"] = {
        "captured_unix": time.time(),
        "source_file": str(args.tray_input.resolve()),
        "source_age_sec": round(source_age, 3),
        "handeye_sha256": handeye_sha256,
        "counts": counts,
        "part_count": len(frozen),
        "quality_gate": quality_config,
        "parts": frozen,
    }
    update_readiness(payload)
    return payload


def merge_smd_close_angles(
    payload: dict,
    angles: dict[int, dict],
    metadata: dict,
    max_angle_error_deg: float = 5.0,
) -> dict:
    if not payload.get("board_captured") or not payload.get("tray_captured"):
        raise RuntimeError("capture the board and TrayHome view before SMDView")
    parts = payload.get("tray_capture", {}).get("parts", [])
    caps = {
        int(item["instance_index"]): item
        for item in parts
        if item.get("part_type") == "right_white_brown"
    }
    expected = set(range(1, EXPECTED_TRAY_COUNTS["right_white_brown"] + 1))
    if set(caps) != expected or set(angles) != expected:
        raise RuntimeError(
            f"CAP instance mismatch; TrayHome={sorted(caps)}, SMDView={sorted(angles)}"
        )

    for instance in sorted(expected):
        cap = caps[instance]
        close = angles[instance]
        coarse_angle = float(cap["long_axis_angle_base_deg"])
        close_angle = float(close["long_axis_angle_base_deg"])
        angle_error = abs((close_angle - coarse_angle + 90.0) % 180.0 - 90.0)
        if angle_error > max_angle_error_deg:
            raise RuntimeError(
                f"CAP-{instance:02d} coarse/close angle contradiction: "
                f"coarse={coarse_angle:.3f}deg, close={close_angle:.3f}deg, "
                f"error={angle_error:.3f}deg exceeds {max_angle_error_deg:.3f}deg"
            )
        cap["coarse_long_axis_angle_base_deg"] = round(coarse_angle, 6)
        cap["long_axis_angle_base_deg"] = round(close_angle, 6)
        cap["position_source"] = "TrayHome full-tray detection"
        cap["angle_source"] = metadata["angle_source"]
        cap["smd_set_index"] = int(metadata["set_index"])
        cap["smd_physical_instance_index"] = int(close["physical_instance_index"])
        cap["smd_close_quality"] = {
            "confidence_median": round(float(close["confidence_median"]), 6),
            "frame_count": int(close["frame_count"]),
            "coarse_close_angle_error_deg": round(angle_error, 6),
        }

    payload["smd_close_captured"] = True
    payload["smd_close_capture"] = {
        **metadata,
        "merged_unix": time.time(),
        "position_source": "TrayHome full-tray detection",
    }
    update_readiness(payload)
    return payload


def capture_smd_close(args: argparse.Namespace, payload: dict) -> dict:
    if not payload.get("tray_captured"):
        raise RuntimeError("capture the TrayHome full view before SMDView")
    angles, metadata = load_smd_close_angles(args)
    tray_capture = payload.get("tray_capture", {})
    tray_captured_unix = float(tray_capture.get("captured_unix", math.nan))
    if not math.isfinite(tray_captured_unix):
        raise RuntimeError("TrayHome capture timestamp is invalid")
    if metadata["captured_unix"] < tray_captured_unix - 2.0:
        raise RuntimeError("SMDView capture predates the current TrayHome capture")
    if metadata["handeye_sha256"] != tray_capture.get("handeye_sha256"):
        raise RuntimeError("TrayHome and SMDView use different hand-eye calibration")
    return merge_smd_close_angles(
        payload, angles, metadata, args.max_smd_coarse_fine_angle_error_deg
    )


def update_readiness(payload: dict) -> None:
    placements = payload.get("resolved_placements", {})
    blocked = [
        code for code, target in placements.items()
        if not target.get("placement_ready", False)
    ]
    payload["placement_ready_count"] = len(placements) - len(blocked)
    payload["placement_blocked_slots"] = blocked
    payload["ready_for_continuous_execution"] = bool(
        payload.get("board_captured")
        and payload.get("tray_captured")
        and payload.get("smd_close_captured")
        and len(placements) == 25
        and not blocked
    )


def print_status(payload: dict) -> None:
    print(f"Cycle: {payload.get('cycle_id', 'NONE')}")
    print(
        f"Board captured: {payload.get('board_captured', False)}; "
        f"tray captured: {payload.get('tray_captured', False)}; "
        f"SMD close captured: {payload.get('smd_close_captured', False)}"
    )
    print(
        f"Placement ready: {payload.get('placement_ready_count', 0)}/25; "
        f"continuous execution ready: "
        f"{payload.get('ready_for_continuous_execution', False)}"
    )
    blocked = payload.get("placement_blocked_slots", [])
    if blocked:
        print("Missing final placement targets:", ", ".join(blocked))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("board", "tray", "smd-close", "status"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--board-input", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--tray-input", type=Path, default=DEFAULT_TRAY)
    parser.add_argument("--smd-close-input", type=Path, default=DEFAULT_SMD_CLOSE)
    parser.add_argument("--slot-file", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--recipe-file", type=Path, default=DEFAULT_RECIPES)
    parser.add_argument("--max-source-age-sec", type=float, default=10.0)
    parser.add_argument("--max-smd-close-age-sec", type=float, default=120.0)
    parser.add_argument("--min-smd-close-frames", type=int, default=8)
    parser.add_argument("--min-smd-close-confidence", type=float, default=0.5)
    parser.add_argument(
        "--max-smd-coarse-fine-angle-error-deg",
        type=float,
        default=5.0,
    )
    parser.add_argument("--smd-set-index", type=int, choices=(1, 2), default=1)
    parser.add_argument("--max-hole-fit-rms-mm", type=float, default=1.5)
    parser.add_argument("--max-plane-mad-mm", type=float, default=2.0)
    args = parser.parse_args()

    if args.phase == "board":
        payload = capture_board(args)
        atomic_write(args.output, payload)
    elif args.phase == "tray":
        payload = capture_tray(args, load(args.output))
        atomic_write(args.output, payload)
    elif args.phase == "smd-close":
        payload = capture_smd_close(args, load(args.output))
        atomic_write(args.output, payload)
    else:
        payload = load(args.output)
    print_status(payload)
    print(f"Snapshot: {args.output.resolve()}")
    print("ROBOT DID NOT MOVE")


if __name__ == "__main__":
    main()
