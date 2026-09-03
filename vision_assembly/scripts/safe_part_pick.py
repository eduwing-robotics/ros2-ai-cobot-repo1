#!/usr/bin/env python3
"""Two-phase, fail-closed tray-part pick approach for the FR5.

prepare: fresh detection -> recipe correction -> stop 100 mm above the surface.
descend: verify the saved hover pose and a fresh detection -> Base-Z-only grasp descent.
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / "vision_assembly"
CAL = ROOT / "calibration"
RECIPES = VISION / "config/part_gripper_recipes.json"
DATA = VISION / "data"
CAPTURE = VISION / "scripts/capture_single_vrm_hover_target.py"
MOVE = CAL / "run_object_approach.sh"

ALIASES = {
    "gpu": "gpu", "hbm": "hbm", "power_module": "long_orange",
    "vrm": "black_block", "inductor": "marked_white",
    "smd_capacitor": "right_white_brown",
}
DISPLAY = {
    "gpu": "GPU", "hbm": "HBM", "long_orange": "Power Module",
    "black_block": "VRM", "marked_white": "Inductor",
    "right_white_brown": "SMD Capacitor",
}


def run(command, label):
    print(f"\n=== {label} ===", flush=True)
    print(" ".join(map(str, command)), flush=True)
    result = subprocess.run([str(value) for value in command], check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def pair(mapping, key):
    value = mapping.get(key)
    if not isinstance(value, dict) or not all(axis in value for axis in ("x", "y")):
        return None
    return [float(value["x"]), float(value["y"])]


def load_pick_recipe(part_type):
    payload = json.loads(RECIPES.read_text(encoding="utf-8"))
    recipe = payload["parts"][part_type]
    tool_xy = pair(recipe, "grasp_center_correction_tool_mm") or [0.0, 0.0]
    base_xy = [0.0, 0.0]
    if part_type == "long_orange":
        extra = pair(recipe, "operator_additional_correction_base_mm")
        if extra is None or pair(recipe, "grasp_center_correction_tool_mm") is None:
            raise ValueError("Power Module requires tool-fixed and additional Base corrections")
        base_xy = extra
    else:
        fixed = pair(recipe, "grasp_center_correction_base_mm")
        if fixed is None:
            raise ValueError("missing validated grasp_center_correction_base_mm")
        base_xy = fixed

    height = recipe.get("grasp_height")
    z_mode = "surface_relative"
    fixed_z = None
    if isinstance(height, dict):
        z_mode = str(height.get("position_mode", z_mode))
        if z_mode == "fixed_fixture_absolute":
            fixed_z = float(height["taught_tcp_z_mm"])
            if not -200.0 <= fixed_z <= 200.0:
                raise ValueError(f"unsafe absolute grasp Z {fixed_z}")
            z_offset = None
        else:
            z_offset = height.get("tcp_z_offset_from_detected_surface_mm")
    else:
        z_offset = recipe.get("grasp_z_offset_from_detected_surface_mm")
    if z_mode not in ("surface_relative", "fixed_fixture_absolute"):
        raise ValueError(f"unknown grasp height mode {z_mode}")
    if z_mode == "surface_relative":
        if z_offset is None:
            raise ValueError("missing validated grasp height offset")
        z_offset = float(z_offset)
        if not -15.0 <= z_offset <= 0.0:
            raise ValueError(f"unsafe grasp height offset {z_offset}")

    pick_policy = recipe.get("pick_orientation_policy", {})
    gripper_axis = str(pick_policy.get("gripper_axis", recipe.get("gripper_axis", "tool_y")))
    branch = str(pick_policy.get("symmetric_rotation_branch", "shortest"))
    if gripper_axis not in ("tool_x", "tool_y"):
        raise ValueError(f"invalid gripper axis {gripper_axis}")
    if branch not in ("shortest", "positive", "negative"):
        raise ValueError(f"invalid symmetric rotation branch {branch}")
    max_rotation = float(pick_policy.get("maximum_rotation_deg", 90.0))
    max_joint_step = float(pick_policy.get("maximum_joint_step_deg", 91.0))
    if not 0.0 < max_rotation <= 180.0 or not 0.0 < max_joint_step <= 180.0:
        raise ValueError("invalid pick rotation safety limit")

    grip = recipe.get("grip")
    if grip is None and part_type == "black_block":
        grip = recipe.get("horizontal", {}).get("grip")
    if not isinstance(grip, dict) or len(grip.get("args", [])) < 2:
        raise ValueError("missing gripper close recipe")
    return {
        "part_type": part_type,
        "display_name": DISPLAY[part_type],
        "tool_correction_xy_mm": tool_xy,
        "base_correction_xy_mm": base_xy,
        "grasp_z_mode": z_mode,
        "grasp_z_offset_mm": z_offset,
        "grasp_fixed_tcp_z_mm": fixed_z,
        "gripper_axis": gripper_axis,
        "symmetric_rotation_branch": branch,
        "max_pick_rotation_deg": max_rotation,
        "max_pick_joint_step_deg": max_joint_step,
        "grip_args": grip["args"],
        "tray_open_args": recipe.get("tray_pick_open", {}).get("args"),
        "release_args": recipe.get("release", {}).get("args"),
    }


def capture(recipe, instance, output, samples=6, expected=None, allow_single_gpu=False):
    command = [
        sys.executable, CAPTURE, "--part-type", recipe["part_type"],
        "--display-name", recipe["display_name"], "--output", output,
        "--samples", str(samples), "--timeout-sec", "60",
        "--max-position-span-mm", "1.0", "--max-angle-span-deg", "2.0",
    ]
    if expected is None:
        command += ["--instance-index", str(instance)]
        if allow_single_gpu:
            command += ["--allow-single-gpu-as-instance-1"]
    else:
        command += [
            "--expected-base-x-mm", str(expected[0]),
            "--expected-base-y-mm", str(expected[1]),
            "--max-expected-distance-mm", "5.0",
        ]
    run(command, "FRESH STABLE PART DETECTION")
    return json.loads(Path(output).read_text(encoding="utf-8"))


def robot_snapshot():
    import rclpy
    from fairino_msgs.msg import RobotNonrtState
    from rclpy.node import Node

    class Reader(Node):
        def __init__(self):
            super().__init__("safe_pick_state_reader")
            self.state = None
            self.create_subscription(RobotNonrtState, "/nonrt_state_data", self.cb, 10)
        def cb(self, message):
            self.state = message

    rclpy.init()
    node = Reader()
    try:
        deadline = time.monotonic() + 8.0
        while rclpy.ok() and time.monotonic() < deadline and node.state is None:
            rclpy.spin_once(node, timeout_sec=0.1)
        if node.state is None:
            raise RuntimeError("No /nonrt_state_data received")
        state = node.state
        checks = {
            "emg": state.emg, "main_error": state.main_error_code,
            "sub_error": state.sub_error_code, "collision": state.collision_err,
            "alarm": state.alarm, "motion_alarm": state.motionalarm,
            "safety_plane": state.safetyplanealarm,
        }
        active = [f"{key}={value}" for key, value in checks.items() if float(value) != 0.0]
        if active:
            raise RuntimeError("robot safety state is not clear: " + ", ".join(active))
        if int(state.robot_motion_done) != 1:
            raise RuntimeError("robot is not stationary")
        return {
            "tcp": [float(value) for value in (
                state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos,
                state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos)],
            "robot_mode": int(state.robot_mode), "tool_id": int(state.tool_num),
            "user_id": int(state.work_num), "motion_done": int(state.robot_motion_done),
        }
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def angle_error_deg(first, second):
    a = Rotation.from_euler("xyz", first, degrees=True)
    b = Rotation.from_euler("xyz", second, degrees=True)
    return float((a.inv() * b).magnitude() * 180.0 / math.pi)


def resolve_grasp_final_z(recipe, detected_surface_z):
    if recipe["grasp_z_mode"] == "fixed_fixture_absolute":
        return float(recipe["grasp_fixed_tcp_z_mm"])
    return float(detected_surface_z + recipe["grasp_z_offset_mm"])


def prepare(args, recipe):
    target = DATA / f"safe_pick_{recipe['part_type']}_{args.instance}.json"
    session = DATA / f"safe_pick_{recipe['part_type']}_{args.instance}_session.json"
    expected = None
    if args.expected_base_x_mm is not None:
        expected = [args.expected_base_x_mm, args.expected_base_y_mm]
    detected = capture(recipe, args.instance, target, expected=expected,
                       allow_single_gpu=args.allow_single_gpu)
    tool = recipe["tool_correction_xy_mm"]
    base = recipe["base_correction_xy_mm"]
    command = [
        MOVE, "--target-file", target, "--approach-offset-mm", "100",
        "--align-part", "--gripper-axis", recipe["gripper_axis"],
        "--symmetric-rotation-branch", recipe["symmetric_rotation_branch"],
        "--max-rotation-deg", str(recipe["max_pick_rotation_deg"]),
        "--center-correction", "--tool-correction-x-mm", str(tool[0]),
        "--tool-correction-y-mm", str(tool[1]),
        "--base-correction-x-mm", str(base[0]),
        "--base-correction-y-mm", str(base[1]),
        "--speed-percent", str(args.travel_speed),
        "--descent-speed-percent", str(args.hover_descent_speed),
        "--rotation-speed-percent", str(args.rotation_speed),
        "--safe-clearance-mm", "100", "--max-distance-mm", "500",
        "--max-target-age-sec", "180", "--max-joint-step-deg",
        str(recipe["max_pick_joint_step_deg"]),
    ]
    if args.execute:
        run(command + ["--execute", "--confirm-move"], "PREPARE TO 100 MM HOVER")
        state = robot_snapshot()
        if state["robot_mode"] != 0 or state["tool_id"] != 1 or state["user_id"] != 0:
            raise RuntimeError(f"unexpected robot frame/mode after hover: {state}")
        record = {
            "schema_version": 1, "phase": "hover_verified",
            "timestamp_unix": time.time(), "part_type": recipe["part_type"],
            "instance_index": args.instance, "target_file": str(target),
            "detection": detected, "recipe": recipe,
            "verified_hover_tcp": state["tcp"],
        }
        tmp = session.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        tmp.replace(session)
        print(f"\nSTOPPED AND VERIFIED AT 100 MM HOVER\nSession: {session}")
        print("Operator center confirmation is required before descend.")
    else:
        run(command + ["--dry-run"], "PREPARE DRY RUN TO 20 MM HOVER")
        print("DRY RUN ONLY: no session was authorized and the robot did not move.")


def descend(args, recipe):
    session_path = DATA / f"safe_pick_{recipe['part_type']}_{args.instance}_session.json"
    record = json.loads(session_path.read_text(encoding="utf-8"))
    age = time.time() - float(record["timestamp_unix"])
    if age < -5.0 or age > args.max_session_age:
        raise RuntimeError(f"hover session is stale ({age:.1f} s); run prepare again")
    if record.get("phase") != "hover_verified" or record.get("part_type") != recipe["part_type"]:
        raise RuntimeError("hover session does not match the requested part")
    if int(record.get("instance_index", -1)) != args.instance:
        raise RuntimeError("hover session does not match the requested instance")

    state = robot_snapshot()
    saved = np.asarray(record["verified_hover_tcp"], dtype=float)
    current = np.asarray(state["tcp"], dtype=float)
    xyz_error = float(np.linalg.norm(current[:3] - saved[:3]))
    orientation_error = angle_error_deg(saved[3:], current[3:])
    if xyz_error > 1.0 or orientation_error > 1.0:
        raise RuntimeError(
            f"robot left verified hover pose: xyz_error={xyz_error:.3f} mm, "
            f"orientation_error={orientation_error:.3f} deg"
        )
    detection = record["detection"]
    center = np.asarray(detection["part_center_base_mm"], dtype=float)
    position_span = np.asarray(detection.get("position_span_mm", []), dtype=float)
    sample_count = int(detection.get("sample_count", 0))
    angle_span = float(detection.get("angle_span_deg", float("inf")))
    if sample_count < 6 or position_span.shape != (3,) or float(np.max(position_span)) > 1.0 or angle_span > 2.0:
        raise RuntimeError(
            f"prepare detection was not stable enough: samples={sample_count}, "
            f"position_span={position_span.tolist()}, angle_span={angle_span}"
        )
    final_z = resolve_grasp_final_z(recipe, float(center[2]))
    down = float(current[2] - final_z)
    if not 0.1 <= down <= 120.0:
        raise RuntimeError(f"unsafe final descent distance {down:.3f} mm")
    command = [
        MOVE, "--x", str(current[0]), "--y", str(current[1]), "--z", str(final_z),
        "--no-center-correction", "--speed-percent", str(args.final_descent_speed),
        "--descent-speed-percent", str(args.final_descent_speed),
        "--safe-z-mm", str(current[2] + 0.2), "--max-distance-mm", "120",
        "--min-horizontal-move-mm", "0.1",
    ]
    if args.execute:
        if not args.confirm_center or not args.confirm_descent:
            raise RuntimeError("actual descent requires --confirm-center --confirm-descent")
        run(command + ["--execute", "--confirm-move"], "FINAL BASE-Z-ONLY DESCENT")
        final_state = robot_snapshot()
        xy_shift = float(np.linalg.norm(np.asarray(final_state["tcp"][:2]) - current[:2]))
        z_error = abs(float(final_state["tcp"][2] - final_z))
        if xy_shift > 0.5 or z_error > 0.7:
            raise RuntimeError(f"final pose verification failed: XY shift={xy_shift:.3f}, Z error={z_error:.3f}")
        record["phase"] = "grasp_height_verified"
        record["timestamp_unix"] = time.time()
        record["descent_detection_source"] = "prepare_verified_detection"
        record["verified_grasp_tcp"] = final_state["tcp"]
        record["gripper_closed"] = False
        tmp = session_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        tmp.replace(session_path)
        print("GRASP HEIGHT VERIFIED; gripper remains open.")
    else:
        run(command + ["--dry-run"], "FINAL DESCENT DRY RUN")
        print("DRY RUN ONLY: gripper remains open and robot did not move.")


def status():
    print("COMMON SAFE PICK RECIPE STATUS")
    for alias, part_type in ALIASES.items():
        try:
            recipe = load_pick_recipe(part_type)
            grasp_z = (
                recipe["grasp_fixed_tcp_z_mm"]
                if recipe["grasp_z_mode"] == "fixed_fixture_absolute"
                else recipe["grasp_z_offset_mm"]
            )
            print(f"READY   {alias:14s} correction(tool={recipe['tool_correction_xy_mm']}, "
                  f"base={recipe['base_correction_xy_mm']}), "
                  f"grasp_z({recipe['grasp_z_mode']})={grasp_z}")
        except (KeyError, TypeError, ValueError) as exc:
            print(f"BLOCKED {alias:14s} {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("status", "prepare", "descend"))
    parser.add_argument("--part", choices=tuple(ALIASES))
    parser.add_argument("--instance", type=int, default=1)
    parser.add_argument("--expected-base-x-mm", type=float)
    parser.add_argument("--expected-base-y-mm", type=float)
    parser.add_argument("--travel-speed", type=int, default=40)
    parser.add_argument("--hover-descent-speed", type=int, default=20)
    parser.add_argument("--rotation-speed", type=int, default=40)
    parser.add_argument("--final-descent-speed", type=int, default=20)
    parser.add_argument("--max-session-age", type=float, default=300.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-prepare", action="store_true")
    parser.add_argument("--confirm-center", action="store_true")
    parser.add_argument("--confirm-descent", action="store_true")
    parser.add_argument("--allow-single-gpu", action="store_true")
    args = parser.parse_args()
    if args.phase == "status":
        status(); return
    if args.part is None:
        parser.error("--part is required")
    if args.instance < 1:
        parser.error("--instance must be positive")
    if (args.expected_base_x_mm is None) != (args.expected_base_y_mm is None):
        parser.error("expected Base X and Y must be provided together")
    if args.dry_run == args.execute:
        parser.error("choose exactly one of --dry-run or --execute")
    if args.phase == "prepare" and args.execute != args.confirm_prepare:
        parser.error("actual prepare requires --execute --confirm-prepare")
    if not all(1 <= value <= 50 for value in (
        args.travel_speed, args.hover_descent_speed,
        args.rotation_speed, args.final_descent_speed)):
        parser.error("all speeds must be between 1 and 50")
    part_type = ALIASES[args.part]
    try:
        recipe = load_pick_recipe(part_type)
    except (KeyError, TypeError, ValueError) as exc:
        parser.error(f"{args.part} is not safe-pick ready: {exc}")
    if args.phase == "prepare":
        prepare(args, recipe)
    else:
        descend(args, recipe)


if __name__ == "__main__":
    main()
