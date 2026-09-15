#!/usr/bin/env python3
"""Unwind an empty FR5 wrist with bounded positive-direction J6 jogs.

This recovery utility never changes collision settings.  It permits only a
small positive J6 jog, checks that the other joints remain fixed, and issues
an immediate jog stop on any fault, reverse motion, or excessive travel.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import rclpy


ROOT = Path(__file__).resolve().parents[2]
VISION_SCRIPTS = ROOT / "vision_assembly" / "scripts"
if str(VISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(VISION_SCRIPTS))

from execute_cached_hbm_remaining import Executor  # noqa: E402


MAX_RECOVERY_J6_DEG = 350.0


def circular_delta_deg(current: float, previous: float) -> float:
    """Return the signed shortest joint delta across the +/-180 display seam."""
    return float((current - previous + 180.0) % 360.0 - 180.0)


def stop_jog(node: Executor) -> None:
    try:
        node.service("ImmStopJOG()")
    except Exception:
        pass


def execute_jog(node: Executor, step_deg: float, speed: float, acceleration: float) -> None:
    state = node.spin_state()
    error = node.safety_error(state)
    if error:
        raise RuntimeError("robot safety state is not clear: " + error)
    if int(state.robot_motion_done) != 1:
        raise RuntimeError("robot must be stationary before J6 recovery")
    if int(state.tool_num) != 1 or int(state.work_num) != 0:
        raise RuntimeError("expected Tool1/User0")
    node.assert_gripper_ready()
    if int(state.gripper_position) != 0:
        raise RuntimeError(
            f"empty-gripper recovery requires gripper position 0, got {state.gripper_position}"
        )

    before = node.state_joints(state)
    target_j6 = float(before[5] + step_deg)
    if target_j6 > MAX_RECOVERY_J6_DEG:
        raise RuntimeError(
            f"bounded recovery target J6={target_j6:.3f} exceeds {MAX_RECOVERY_J6_DEG:.1f}deg"
        )

    command = f"StartJOG(0,6,1,{speed:.3f},{acceleration:.3f},{step_deg:.3f})"
    print(
        f"J6 POSITIVE UNWIND: before={before[5]:.3f}deg, "
        f"bounded_target={target_j6:.3f}deg, command={command}",
        flush=True,
    )
    node.service(command)

    deadline = time.monotonic() + 30.0
    saw_motion = False
    final_state = None
    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            current = node.state
            if current is None:
                continue
            error = node.safety_error(current)
            if error:
                raise RuntimeError("safety fault during J6 recovery: " + error)
            joints = node.state_joints(current)
            other_joint_change = float(np.max(np.abs(joints[:5] - before[:5])))
            if other_joint_change > 0.2:
                raise RuntimeError(
                    f"non-J6 joint moved {other_joint_change:.3f}deg during J6-only recovery"
                )
            travelled = circular_delta_deg(float(joints[5]), float(before[5]))
            if travelled < -0.05:
                raise RuntimeError(
                    f"J6 moved in the forbidden negative direction ({travelled:.3f}deg)"
                )
            if travelled > step_deg + 0.2:
                raise RuntimeError(
                    f"J6 exceeded bounded jog distance ({travelled:.3f}deg)"
                )
            if int(current.robot_motion_done) == 0:
                saw_motion = True
            if (
                int(current.robot_motion_done) == 1
                and travelled >= step_deg - 0.15
                and (saw_motion or travelled >= step_deg - 0.05)
            ):
                final_state = current
                break
        if final_state is None:
            raise RuntimeError("bounded J6 jog did not reach a verified stationary state")
    except BaseException:
        stop_jog(node)
        raise

    after = node.state_joints(final_state)
    travelled = circular_delta_deg(float(after[5]), float(before[5]))
    print(
        f"VERIFIED J6 POSITIVE UNWIND: {before[5]:.3f} -> {after[5]:.3f}deg; "
        f"travel={travelled:.3f}deg; "
        f"torque={float(final_state.j6_cur_tor):.4f}; no collision",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step-deg", type=float, default=0.5)
    parser.add_argument("--speed-percent", type=float, default=1.0)
    parser.add_argument("--acceleration-percent", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-empty-gripper-positive-j6", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        parser.error("choose exactly one of --dry-run or --execute")
    if args.execute != args.confirm_empty_gripper_positive_j6:
        parser.error(
            "execution requires --execute --confirm-empty-gripper-positive-j6"
        )
    if not 0.1 <= args.step_deg <= 5.0:
        parser.error("--step-deg must be in [0.1, 5.0]")
    if not 0.1 <= args.speed_percent <= 5.0:
        parser.error("--speed-percent must be in [0.1, 5.0]")
    if not 0.1 <= args.acceleration_percent <= 5.0:
        parser.error("--acceleration-percent must be in [0.1, 5.0]")

    rclpy.init()
    node = Executor()
    try:
        if not node.client.wait_for_service(timeout_sec=8.0):
            raise RuntimeError("FR5 command service unavailable")
        state = node.spin_state()
        before = node.state_joints(state)
        print(
            f"RECOVERY PREFLIGHT: mode={state.robot_mode}, stationary={state.robot_motion_done}, "
            f"J6={before[5]:.3f}deg, gripper={state.gripper_position}, "
            f"feedback_valid={state.gripper_feedback_valid}"
        )
        if args.dry_run:
            print(
                f"DRY RUN: would jog only J6 positive by at most {args.step_deg:.3f}deg "
                f"at {args.speed_percent:.3f}%"
            )
            print("ROBOT DID NOT MOVE")
            return
        execute_jog(
            node,
            args.step_deg,
            args.speed_percent,
            args.acceleration_percent,
        )
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
