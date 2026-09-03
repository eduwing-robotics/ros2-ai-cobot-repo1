#!/usr/bin/env python3
"""Place HBM-05..08 from one frozen tray/board capture.

The executor is deliberately limited to four HBM parts and enforces the
validated 100 mm Base-Z-only approach/retract invariant. It performs no vision
recapture between parts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from rclpy.node import Node
from scipy.spatial.transform import Rotation

from placement_orientation import (
    plan_carried_part_orientation,
    slot_axis_base_angle_deg,
)


ROOT = Path(__file__).resolve().parents[2]
VISION = ROOT / "vision_assembly"
BOARD_SNAPSHOT = VISION / "data/fixed_cycle_snapshot.json"
TRAY_SNAPSHOT = VISION / "data/fixed_cycle_tray_hbm_remaining_2026-09-02.json"
RECIPES = VISION / "config/part_gripper_recipes.json"
SLOT_FILE = VISION / "config/assembly_slots_r1.json"
RUN_RECORD = VISION / "data/cached_hbm_05_08_run.json"
SLOTS = [f"HBM-{index:02d}" for index in range(5, 9)]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wrap_degrees(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def nearest_symmetric_c(long_axis_deg: float, reference_c_deg: float) -> float:
    first = wrap_degrees(long_axis_deg + 90.0)
    second = wrap_degrees(first + 180.0)
    return min(
        (first, second),
        key=lambda candidate: abs(wrap_degrees(candidate - reference_c_deg)),
    )


def finite(values, length: int, label: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise RuntimeError(f"{label} must have {length} finite values")
    return result


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def build_plan(args: argparse.Namespace) -> list[dict]:
    board = load(args.board_snapshot)
    if board.get("schema") != "fr5.fixed_fixture_cycle_snapshot/v1":
        raise RuntimeError("wrong board snapshot schema")
    if not board.get("board_captured"):
        raise RuntimeError("board snapshot is not captured")
    capture = board.get("board_capture", {})
    if int(capture.get("slot_count", 0)) != 25:
        raise RuntimeError("board snapshot does not contain all 25 slots")
    if float(capture.get("hole_fit_rms_mm", math.inf)) > 1.5:
        raise RuntimeError("board snapshot hole-fit quality is invalid")
    if float(capture.get("plane_residual_mad_mm", math.inf)) > 2.0:
        raise RuntimeError("board snapshot plane quality is invalid")
    board_transform = np.asarray(capture.get("T_base_board"), dtype=float)
    if board_transform.shape != (4, 4) or not np.all(np.isfinite(board_transform)):
        raise RuntimeError("board snapshot has no valid Base transform")
    board_rotation = board_transform[:3, :3]
    slot_config = {
        item["slot_code"]: item for item in load(args.slot_file)["slots"]
    }

    tray = load(args.tray_snapshot)
    if tray.get("tray_registration") != "TRACKING":
        raise RuntimeError("frozen tray snapshot was not TRACKING")
    if tray.get("base_transform_status") not in ("OK", "VALID_COORDINATES_ONLY"):
        raise RuntimeError("frozen tray snapshot has no valid Base transform")
    detections = [
        item for item in tray.get("stable_detections", [])
        if item.get("part_type") == "hbm"
    ]
    detections.sort(key=lambda item: int(item["instance_index"]))
    if len(detections) != 4:
        raise RuntimeError(f"expected exactly four frozen HBM detections, got {len(detections)}")
    for item in detections:
        if int(item.get("observation_frames", 0)) < 6:
            raise RuntimeError("HBM tray detection is not sufficiently stable")

    recipe = load(args.recipe_file)["parts"]["hbm"]
    orientation_policy = recipe.get("placement_orientation_policy", {})
    if orientation_policy.get("mode") != "align_actual_carried_axis_to_current_slot_axis":
        raise RuntimeError("HBM dynamic carried-axis placement policy is missing")
    gripper_axis = str(orientation_policy.get("gripper_axis"))
    symmetry = float(orientation_policy.get("symmetry_period_deg", math.nan))
    maximum_rotation = float(
        orientation_policy.get("maximum_intentional_rotation_deg", math.nan)
    )
    tie_threshold = float(
        orientation_policy.get("preference_tie_threshold_deg", 5.0)
    )
    skip_rotation = float(orientation_policy.get("skip_rotation_below_deg", 0.5))
    if gripper_axis not in ("tool_x", "tool_y") or not all(
        math.isfinite(value)
        for value in (symmetry, maximum_rotation, tie_threshold, skip_rotation)
    ):
        raise RuntimeError("invalid HBM dynamic orientation policy")
    correction = recipe.get("grasp_center_correction_base_mm", {})
    pick_xy = finite(
        [correction.get("x"), correction.get("y")],
        2,
        "HBM grasp Base correction",
    )
    pick_z_offset = float(recipe["grasp_z_offset_from_detected_surface_mm"])
    if not -15.0 <= pick_z_offset <= 0.0:
        raise RuntimeError("unsafe HBM grasp Z offset")
    grip = int(recipe["grip"]["args"][1])
    release = int(recipe["release"]["args"][1])
    if (grip, release) != (18, 25):
        raise RuntimeError(f"unexpected HBM gripper values {(grip, release)}")

    placements = board["resolved_placements"]
    plan = []
    reference_c = 90.0
    for slot_code, detection in zip(SLOTS, detections):
        placement = placements.get(slot_code)
        if not placement or not placement.get("placement_ready"):
            raise RuntimeError(f"{slot_code} placement is not ready")
        surface = finite(detection["base_xyz_mm"], 3, "HBM tray surface")
        angle = float(detection["long_axis_angle_base_deg"])
        if not math.isfinite(angle):
            raise RuntimeError("invalid HBM tray angle")
        pick_c = nearest_symmetric_c(angle, reference_c)
        reference_c = pick_c
        place_xy = finite(placement["corrected_place_xy_base_mm"], 2, "place XY")
        place_z = float(placement["final_tcp_z_mm"])
        slot = slot_config.get(slot_code)
        if slot is None:
            raise RuntimeError(f"missing slot configuration for {slot_code}")
        target_axis = slot_axis_base_angle_deg(
            board_rotation, float(slot["long_axis_board_deg"])
        )
        preferred_c = slot.get("preferred_tcp_c_deg")
        pick_final = [
            float(surface[0] + pick_xy[0]),
            float(surface[1] + pick_xy[1]),
            float(surface[2] + pick_z_offset),
            -180.0,
            0.0,
            float(pick_c),
        ]
        orientation_plan = plan_carried_part_orientation(
            pick_final[3:], target_axis, gripper_axis, symmetry,
            preferred_tcp_c_deg=preferred_c,
            preference_tie_threshold_deg=tie_threshold,
        )
        if abs(orientation_plan["rotation_delta_deg"]) > maximum_rotation + 1e-6:
            raise RuntimeError(
                f"{slot_code} required rotation "
                f"{orientation_plan['rotation_delta_deg']:.3f}deg exceeds policy"
            )
        rotation_skipped = (
            abs(orientation_plan["rotation_delta_deg"]) <= skip_rotation
        )
        place_abc = (
            pick_final[3:]
            if rotation_skipped
            else orientation_plan["target_tcp_abc_deg"]
        )
        place_final = [
            float(place_xy[0]),
            float(place_xy[1]),
            place_z,
            *[float(value) for value in place_abc],
        ]
        plan.append(
            {
                "slot_code": slot_code,
                "tray_instance_index": int(detection["instance_index"]),
                "tray_surface_base_mm": surface.tolist(),
                "tray_long_axis_base_deg": angle,
                "pick_final_tcp": pick_final,
                "place_final_tcp": place_final,
                "placement_orientation": {
                    "target_axis_base_deg": target_axis,
                    "gripper_axis": gripper_axis,
                    "symmetry_period_deg": symmetry,
                    "maximum_intentional_rotation_deg": maximum_rotation,
                    "preference_tie_threshold_deg": tie_threshold,
                    "skip_rotation_below_deg": skip_rotation,
                    "preferred_tcp_c_deg": preferred_c,
                    "rotation_skipped_in_plan": rotation_skipped,
                    "planned_from_pick": orientation_plan,
                },
                "grip_position": grip,
                "release_position": release,
            }
        )
    return plan


class Executor(Node):
    def __init__(self) -> None:
        super().__init__("execute_cached_hbm_remaining")
        self.state = None
        self.create_subscription(RobotNonrtState, "/nonrt_state_data", self.state_cb, 10)
        self.client = self.create_client(
            RemoteCmdInterface, "/fairino_remote_command_service"
        )

    def state_cb(self, message) -> None:
        self.state = message

    def spin_state(self, timeout_sec: float = 8.0):
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state is not None:
                return self.state
        raise RuntimeError("no FR5 state received")

    @staticmethod
    def safety_error(state) -> str | None:
        checks = {
            "emg": getattr(state, "emg", 0),
            "main_error": getattr(state, "main_error_code", 0),
            "sub_error": getattr(state, "sub_error_code", 0),
            "collision": getattr(state, "collision_err", 0),
            "alarm": getattr(state, "alarm", 0),
            "motion_alarm": getattr(state, "motionalarm", 0),
            "safety_plane": getattr(state, "safetyplanealarm", 0),
        }
        active = [f"{key}={value}" for key, value in checks.items() if float(value) != 0.0]
        return ", ".join(active) if active else None

    def snapshot(self) -> list[float]:
        state = self.spin_state()
        error = self.safety_error(state)
        if error:
            raise RuntimeError("FR5 safety state is not clear: " + error)
        return [
            float(state.cart_x_cur_pos),
            float(state.cart_y_cur_pos),
            float(state.cart_z_cur_pos),
            float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos),
            float(state.cart_c_cur_pos),
        ]

    def service(self, command: str) -> str:
        request = RemoteCmdInterface.Request()
        request.cmd_str = command
        future = self.client.call_async(request)
        # A long, blocking MoveCart service call can legitimately take more
        # than ten seconds even though the controller accepted the command.
        # Keep the client alive long enough to receive the real result; pose
        # verification below still independently checks motion completion.
        rclpy.spin_until_future_complete(self, future, timeout_sec=90.0)
        if not future.done() or future.result() is None:
            raise RuntimeError(f"FR5 command timeout: {command}")
        result = str(future.result().cmd_res)
        if result.split(",", 1)[0] != "0":
            raise RuntimeError(f"FR5 rejected {command}: {result}")
        return result

    @staticmethod
    def response_values(result: str, count: int, label: str) -> np.ndarray:
        fields = result.split(",")
        if not fields or fields[0] != "0" or len(fields) < count + 1:
            raise RuntimeError(f"invalid {label} response: {result}")
        values = np.asarray([float(value) for value in fields[1:count + 1]], dtype=float)
        if not np.all(np.isfinite(values)):
            raise RuntimeError(f"non-finite {label} response: {result}")
        return values

    @staticmethod
    def state_joints(state) -> np.ndarray:
        return np.asarray(
            [
                state.j1_cur_pos,
                state.j2_cur_pos,
                state.j3_cur_pos,
                state.j4_cur_pos,
                state.j5_cur_pos,
                state.j6_cur_pos,
            ],
            dtype=float,
        )

    def referenced_ik(self, target: list[float], max_joint_step_deg: float = 90.0) -> np.ndarray:
        state = self.spin_state()
        reference = self.state_joints(state)
        soft = self.response_values(
            self.service("GetJointSoftLimitDeg(1)"), 12, "joint soft-limit"
        )
        negative, positive = soft[:6], soft[6:]
        if np.any(reference < negative) or np.any(reference > positive):
            raise RuntimeError("current joints are outside controller soft limits")
        safety = self.response_values(
            self.service("GetSafetyStopState()"), 2, "safety-stop"
        )
        if np.any(safety != 0.0):
            raise RuntimeError(f"safety stop is active: {safety.astype(int).tolist()}")
        request = "GetInverseKinRef(" + ",".join(
            f"{value:.6f}" for value in [0.0, *target, *reference.tolist()]
        ) + ")"
        joints = self.response_values(self.service(request), 6, "referenced IK")
        margins = np.minimum(joints - negative, positive - joints)
        if np.any(margins < 10.0):
            joint = int(np.argmin(margins)) + 1
            raise RuntimeError(
                f"J{joint} soft-limit margin {margins[joint - 1]:.1f}deg is below 10deg"
            )
        delta = np.abs(joints - reference)
        if np.any(delta > max_joint_step_deg):
            joint = int(np.argmax(delta)) + 1
            raise RuntimeError(
                f"J{joint} branch change {delta[joint - 1]:.1f}deg exceeds "
                f"{max_joint_step_deg:.1f}deg"
            )
        return joints

    def wait_pose(
        self,
        target: list[float],
        target_joints: np.ndarray | None = None,
        timeout_sec: float = 90.0,
    ) -> list[float]:
        deadline = time.monotonic() + timeout_sec
        target_rotation = Rotation.from_euler("xyz", target[3:], degrees=True)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            state = self.state
            if state is None:
                continue
            error = self.safety_error(state)
            if error:
                raise RuntimeError("FR5 safety fault during motion: " + error)
            current = np.array(
                [state.cart_x_cur_pos, state.cart_y_cur_pos, state.cart_z_cur_pos],
                dtype=float,
            )
            rotation = Rotation.from_euler(
                "xyz",
                [state.cart_a_cur_pos, state.cart_b_cur_pos, state.cart_c_cur_pos],
                degrees=True,
            )
            angle_error = float((rotation.inv() * target_rotation).magnitude() * 180.0 / math.pi)
            if (
                int(state.robot_motion_done) == 1
                and float(np.linalg.norm(current - np.asarray(target[:3]))) <= 1.0
                and angle_error <= 1.0
                and (
                    target_joints is None
                    or float(np.max(np.abs(self.state_joints(state) - target_joints))) <= 1.0
                )
            ):
                return self.snapshot()
        raise RuntimeError(f"pose verification timeout: {target}")

    def move(
        self,
        target: list[float],
        speed: int,
        label: str,
        *,
        linear: bool = False,
    ) -> list[float]:
        joints = self.referenced_ik(target)
        define = "JNTPoint(1," + ",".join(f"{value:.6f}" for value in joints) + ")"
        motion_command = "MoveL" if linear else "MoveJ"
        command = f"{motion_command}(JNT1,{speed},1,0)"
        print(
            f"{label}: target={[round(value, 3) for value in target]} "
            f"joints={[round(value, 3) for value in joints]} command={command}",
            flush=True,
        )
        self.service(define)
        self.service(command)
        result = self.wait_pose(target, joints)
        print(f"VERIFIED {label}: {[round(value, 3) for value in result]}", flush=True)
        return result

    def vertical(self, target_z: float, speed: int, label: str) -> list[float]:
        current = self.snapshot()
        target = [current[0], current[1], target_z, *current[3:]]
        return self.move(target, speed, label, linear=True)

    def rotate(self, abc: list[float], speed: int, label: str) -> list[float]:
        current = self.snapshot()
        target = [current[0], current[1], current[2], *abc]
        return self.move(target, speed, label)

    def horizontal(self, xy: list[float], speed: int, label: str) -> list[float]:
        current = self.snapshot()
        target = [xy[0], xy[1], current[2], *current[3:]]
        return self.move(target, speed, label)

    def gripper(self, position: int, label: str) -> None:
        print(f"{label}: MoveGripper(1,{position})", flush=True)
        self.service(f"MoveGripper(1,{position})")
        deadline = time.monotonic() + 8.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            state = self.state
            if state is None:
                continue
            error = self.safety_error(state)
            if error:
                raise RuntimeError("FR5 safety fault during gripper command: " + error)
            if int(state.gripper_position) == position:
                print(f"VERIFIED {label}: gripper={position}", flush=True)
                return
        raise RuntimeError(f"gripper verification timeout for position {position}")


def print_plan(plan: list[dict], transfer_z: float) -> None:
    print("CACHED HBM-05..08 PLAN", flush=True)
    print(f"Common transfer Z: {transfer_z:.3f} mm", flush=True)
    for item in plan:
        print(
            f"{item['slot_code']} <- tray#{item['tray_instance_index']} "
            f"pick={[round(value, 3) for value in item['pick_final_tcp']]} "
            f"place={[round(value, 3) for value in item['place_final_tcp']]}",
            flush=True,
        )


def execute(args: argparse.Namespace, plan: list[dict]) -> None:
    record = {
        "schema": "fr5.cached_hbm_05_08_run/v1",
        "started_unix": time.time(),
        "board_snapshot": str(args.board_snapshot.resolve()),
        "tray_snapshot": str(args.tray_snapshot.resolve()),
        "transfer_z_mm": args.transfer_z_mm,
        "plan": plan,
        "completed_slots": [],
        "actual_orientation_decisions": [],
        "status": "running",
    }
    atomic_write(args.run_record, record)
    rclpy.init()
    node = Executor()
    try:
        if not node.client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError("FR5 command service unavailable")
        state = node.spin_state()
        if int(state.robot_mode) != 0:
            raise RuntimeError("AUTO mode required")
        if int(state.tool_num) != 1 or int(state.work_num) != 0:
            raise RuntimeError("expected tool=1 and user=0")
        if int(state.robot_motion_done) != 1:
            raise RuntimeError("robot must be stationary before execution")
        node.snapshot()

        for index, item in enumerate(plan, 1):
            slot = item["slot_code"]
            pick = item["pick_final_tcp"]
            place = item["place_final_tcp"]
            print(f"\n=== {index}/4 {slot} ===", flush=True)

            node.vertical(args.transfer_z_mm, 40, f"{slot} pre-pick safe vertical")
            node.rotate(pick[3:], 40, f"{slot} pick orientation")
            node.horizontal(pick[:2], 40, f"{slot} pick horizontal")
            node.vertical(pick[2] + 100.0, 40, f"{slot} pick 100mm hover")
            node.gripper(item["release_position"], f"{slot} pre-pick open")
            node.vertical(pick[2], 20, f"{slot} final pick descent")
            node.gripper(item["grip_position"], f"{slot} grasp")
            node.vertical(pick[2] + 100.0, 20, f"{slot} post-grasp 100mm lift")
            node.vertical(args.transfer_z_mm, 40, f"{slot} carry safe vertical")
            policy = item["placement_orientation"]
            actual_abc = node.snapshot()[3:]
            actual_orientation = plan_carried_part_orientation(
                actual_abc,
                policy["target_axis_base_deg"],
                policy["gripper_axis"],
                policy["symmetry_period_deg"],
                preferred_tcp_c_deg=policy["preferred_tcp_c_deg"],
                preference_tie_threshold_deg=policy["preference_tie_threshold_deg"],
            )
            rotation_delta = float(actual_orientation["rotation_delta_deg"])
            if abs(rotation_delta) > policy["maximum_intentional_rotation_deg"] + 1e-6:
                raise RuntimeError(
                    f"{slot} actual required rotation {rotation_delta:.3f}deg exceeds policy"
                )
            skip_rotation = float(policy["skip_rotation_below_deg"])
            rotation_skipped = abs(rotation_delta) <= skip_rotation
            place[3:] = (
                actual_abc
                if rotation_skipped
                else actual_orientation["target_tcp_abc_deg"]
            )
            record["actual_orientation_decisions"].append(
                {
                    "slot_code": slot,
                    "rotation_skipped": rotation_skipped,
                    "skip_rotation_below_deg": skip_rotation,
                    **actual_orientation,
                }
            )
            atomic_write(args.run_record, record)
            if not rotation_skipped:
                node.rotate(place[3:], 40, f"{slot} minimal required place rotation")
            else:
                print(
                    f"VERIFIED {slot}: carried orientation already fits slot; "
                    f"rotation skipped ({rotation_delta:.3f}deg)", flush=True
                )
            node.horizontal(place[:2], 40, f"{slot} place horizontal")
            node.vertical(place[2] + 100.0, 40, f"{slot} place 100mm hover")
            node.vertical(place[2], 20, f"{slot} final place descent")
            node.gripper(item["release_position"], f"{slot} release")
            node.vertical(place[2] + 100.0, 20, f"{slot} post-release 100mm lift")

            record["completed_slots"].append(slot)
            record["last_verified_tcp"] = node.snapshot()
            atomic_write(args.run_record, record)
            print(f"COMPLETED {slot}", flush=True)

        record["status"] = "complete"
        record["completed_unix"] = time.time()
        atomic_write(args.run_record, record)
        print("\nALL REMAINING HBM COMPLETED", flush=True)
    except Exception as exc:
        record["status"] = "stopped_on_error"
        record["error"] = str(exc)
        record["stopped_unix"] = time.time()
        try:
            record["last_verified_tcp"] = node.snapshot()
        except Exception:
            pass
        atomic_write(args.run_record, record)
        raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board-snapshot", type=Path, default=BOARD_SNAPSHOT)
    parser.add_argument("--tray-snapshot", type=Path, default=TRAY_SNAPSHOT)
    parser.add_argument("--recipe-file", type=Path, default=RECIPES)
    parser.add_argument("--slot-file", type=Path, default=SLOT_FILE)
    parser.add_argument("--run-record", type=Path, default=RUN_RECORD)
    parser.add_argument("--transfer-z-mm", type=float, default=487.88)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-four-hbm", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        parser.error("choose exactly one of --dry-run or --execute")
    if args.execute != args.confirm_four_hbm:
        parser.error("execution requires --execute --confirm-four-hbm")
    if not 400.0 <= args.transfer_z_mm <= 550.0:
        parser.error("transfer Z must be 400..550 mm")
    plan = build_plan(args)
    print_plan(plan, args.transfer_z_mm)
    if args.dry_run:
        print("DRY RUN - ROBOT DID NOT MOVE")
        return
    execute(args, plan)


if __name__ == "__main__":
    main()
