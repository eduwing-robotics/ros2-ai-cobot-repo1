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
from execution_safety import STATE_MAX_AGE_SEC, STOP_RPC_TIMEOUT_SEC, STOP_FEEDBACK_TIMEOUT_SEC

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
J6_OPERATIONAL_MIN_DEG = -178.0
J6_OPERATIONAL_MAX_DEG = 178.0


def init_executor_ros() -> None:
    """Keep ROS alive for StopMotion when Python receives KeyboardInterrupt.

    rclpy's default SIGINT handler shuts down the context before caller cleanup.
    These executors own shutdown in finally, after their bounded stop attempt.
    """
    from rclpy.signals import SignalHandlerOptions
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)


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
    with temporary.open("w", encoding="utf-8") as output:
        output.write(json.dumps(payload, indent=2) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
    if orientation_policy.get("mode") != "preserve_pick_tcp_orientation":
        raise RuntimeError("HBM pick-orientation preservation policy is missing")
    if float(orientation_policy.get("maximum_intentional_rotation_deg", math.nan)) != 0.0:
        raise RuntimeError("HBM preservation policy must prohibit intentional rotation")
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
        pick_final = [
            float(surface[0] + pick_xy[0]),
            float(surface[1] + pick_xy[1]),
            float(surface[2] + pick_z_offset),
            -180.0,
            0.0,
            float(pick_c),
        ]
        place_abc = list(pick_final[3:])
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
                    "mode": "preserve_pick_tcp_orientation",
                    "maximum_intentional_rotation_deg": 0.0,
                    "rotation_delta_deg": 0.0,
                    "target_tcp_abc_deg": list(place_abc),
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
        self.state_sequence = 0
        self.state_received_monotonic = 0.0
        self.create_subscription(RobotNonrtState, "/nonrt_state_data", self.state_cb, 10)
        self.client = self.create_client(
            RemoteCmdInterface, "/fairino_remote_command_service"
        )

    def state_cb(self, message) -> None:
        self.state = message
        self.state_sequence += 1
        self.state_received_monotonic = time.monotonic()

    def state_is_fresh(self, after_sequence: int) -> bool:
        age = time.monotonic() - self.state_received_monotonic
        return (self.state is not None and self.state_sequence > after_sequence
                and 0.0 <= age <= STATE_MAX_AGE_SEC)

    def spin_state(self, timeout_sec: float = 8.0, *, after_sequence: int | None = None):
        # Every caller must see a new callback, even if the cached pose matches.
        baseline = self.state_sequence if after_sequence is None else after_sequence
        deadline = time.monotonic() + timeout_sec
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state_is_fresh(baseline):
                return self.state
        raise RuntimeError("no fresh FR5 state received (stale or unchanged sequence)")

    @staticmethod
    def safety_error(state) -> str | None:
        checks = {
            "emg": getattr(state, "emg", 0),
            "abnormal_stop": getattr(state, "abnormal_stop", 0),
            "main_error": getattr(state, "main_error_code", 0),
            "sub_error": getattr(state, "sub_error_code", 0),
            "collision": getattr(state, "collision_err", 0),
            "alarm": getattr(state, "alarm", 0),
            "safety_door": getattr(state, "safetydoor_alarm", 0),
            "motion_alarm": getattr(state, "motionalarm", 0),
            "safety_plane": getattr(state, "safetyplanealarm", 0),
            "interference": getattr(state, "interferealarm", 0),
            "soft_limit": getattr(state, "out_sflimit_err", 0),
            "strange_pose": getattr(state, "strangeposflag", 0),
            "control_box": getattr(state, "ctrlboxerror", 0),
            "command_point": getattr(state, "cmdpointerror", 0),
            "parameter": getattr(state, "paraerror", 0),
        }
        active = [f"{key}={value}" for key, value in checks.items() if float(value) != 0.0]
        return ", ".join(active) if active else None

    def snapshot(self) -> list[float]:
        state = self.spin_state()
        error = self.safety_error(state)
        if error:
            raise RuntimeError("FR5 safety state is not clear: " + error)
        return self.state_tcp(state)

    @staticmethod
    def state_tcp(state) -> list[float]:
        return [
            float(state.cart_x_cur_pos),
            float(state.cart_y_cur_pos),
            float(state.cart_z_cur_pos),
            float(state.cart_a_cur_pos),
            float(state.cart_b_cur_pos),
            float(state.cart_c_cur_pos),
        ]

    def feedback_observation(self, state=None) -> dict:
        state = self.state if state is None else state
        return {
            "observed_unix": time.time(),
            "state_sequence": self.state_sequence,
            "state_age_sec": time.monotonic() - self.state_received_monotonic,
            "tcp": self.state_tcp(state),
            "robot_motion_done": int(state.robot_motion_done),
            "gripper_position": int(getattr(state, "gripper_position", -1)),
            "safety_error": self.safety_error(state),
        }

    def observe_stop(self, *, after_sequence: int, timeout_sec=STOP_FEEDBACK_TIMEOUT_SEC) -> dict:
        from feedback_settle import FeedbackSettle
        settle = FeedbackSettle(duration=0.5)
        deadline = time.monotonic() + timeout_sec
        anchor = None
        observation = {"feedback_verified_stopped": False, "latest_feedback": None}
        baseline = after_sequence
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if not self.state_is_fresh(baseline):
                continue
            baseline = self.state_sequence
            state = self.state
            observation["latest_feedback"] = self.feedback_observation(state)
            pose = np.asarray(self.state_tcp(state))
            if anchor is None:
                anchor = pose.copy()
            stable = (int(state.robot_motion_done) == 1 and np.all(np.isfinite(pose))
                      and np.max(abs(pose[:3] - anchor[:3])) <= 0.2
                      and np.max(abs((pose[3:] - anchor[3:] + 180) % 360 - 180)) <= 0.1)
            if not stable:
                anchor = pose.copy()
            if settle.update(baseline, time.monotonic(), stable):
                observation["feedback_verified_stopped"] = True
                return observation
        observation["error"] = "fresh stationary feedback not verified before stop observation timeout"
        return observation

    def service(self, command: str, *, timeout_sec: float | None = None, state_validator=None) -> str:
        motion = command.startswith(("MoveJ(", "MoveL(", "MoveCart("))
        hook = getattr(self, "command_event_hook", None)
        journalled = motion or command.startswith("MoveGripper(")
        if hook and journalled:
            hook("requested", command, None)
        # Durable journalling can take time: refresh after it, immediately
        # before issuing the actuator command.
        if journalled:
            state = self.spin_state(timeout_sec=STATE_MAX_AGE_SEC)
            error = self.safety_error(state)
            if error or int(state.robot_motion_done) != 1:
                raise RuntimeError("FR5 is not ready for actuator command: " + (error or "robot moving"))
            if state_validator is not None:
                state_validator(state)
        request = RemoteCmdInterface.Request()
        request.cmd_str = command
        future = self.client.call_async(request)
        # A long, blocking MoveCart service call can legitimately take more
        # than ten seconds even though the controller accepted the command.
        # Keep the client alive long enough to receive the real result; pose
        # verification below still independently checks motion completion.
        if timeout_sec is None:
            timeout_sec = STOP_RPC_TIMEOUT_SEC if command == "StopMotion()" else 90.0
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_sec)
        if not future.done() or future.result() is None:
            raise RuntimeError(f"FR5 command timeout: {command}")
        result = str(future.result().cmd_res)
        if result.split(",", 1)[0] != "0":
            raise RuntimeError(f"FR5 rejected {command}: {result}")
        if hook and journalled:
            hook("accepted", command, result)
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
        if not J6_OPERATIONAL_MIN_DEG <= reference[5] <= J6_OPERATIONAL_MAX_DEG:
            raise RuntimeError(
                f"current J6={reference[5]:.3f}deg is outside operational envelope "
                f"[{J6_OPERATIONAL_MIN_DEG:.1f}, {J6_OPERATIONAL_MAX_DEG:.1f}]"
            )
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
        if not J6_OPERATIONAL_MIN_DEG <= joints[5] <= J6_OPERATIONAL_MAX_DEG:
            raise RuntimeError(
                f"target J6={joints[5]:.3f}deg is outside operational envelope "
                f"[{J6_OPERATIONAL_MIN_DEG:.1f}, {J6_OPERATIONAL_MAX_DEG:.1f}]"
            )
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
        *,
        after_sequence: int | None = None,
    ) -> list[float]:
        deadline = time.monotonic() + timeout_sec
        baseline = self.state_sequence if after_sequence is None else after_sequence
        last_new_feedback = time.monotonic()
        target_rotation = Rotation.from_euler("xyz", target[3:], degrees=True)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if not self.state_is_fresh(baseline):
                if time.monotonic() - last_new_feedback > STATE_MAX_AGE_SEC:
                    raise RuntimeError("stale FR5 state during pose verification")
                continue
            baseline = self.state_sequence
            last_new_feedback = time.monotonic()
            state = self.state
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
                # Return exactly the sample that passed, without spinning again.
                self.last_pose_verification = self.feedback_observation(state)
                return self.state_tcp(state)
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
        from feedback_settle import FeedbackSettle
        self.assert_gripper_ready()
        # Require stationary fresh TCP before changing the gripper.
        settle=FeedbackSettle(duration=.5)
        anchor=None;deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=.05)
            s=self.state;now=time.monotonic()
            if s is None or now-self.state_received_monotonic>.25:continue
            error=self.safety_error(s)
            if error:raise RuntimeError(error)
            pose=np.array([s.cart_x_cur_pos,s.cart_y_cur_pos,s.cart_z_cur_pos,s.cart_a_cur_pos,s.cart_b_cur_pos,s.cart_c_cur_pos])
            if anchor is None:anchor=pose.copy()
            stable=(int(s.robot_motion_done)==1 and np.max(abs(pose[:3]-anchor[:3]))<=.2
                    and np.max(abs((pose[3:]-anchor[3:]+180)%360-180))<=.1)
            if not stable:anchor=pose.copy()
            if settle.update(self.state_sequence,now,stable):break
        else:raise RuntimeError('TCP did not settle before gripper command')
        print(f"{label}: MoveGripper(1,{position})", flush=True)
        self.service(f"MoveGripper(1,{position})")
        after_ack_sequence=self.state_sequence
        accepted_after=time.monotonic()+.2
        settle=FeedbackSettle(duration=1.0)
        deadline = time.monotonic() + 8.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            state = self.state
            if state is None:
                continue
            now=time.monotonic()
            if self.state_sequence<=after_ack_sequence or now<accepted_after or now-self.state_received_monotonic>.25:
                continue
            error = self.safety_error(state)
            if error:
                raise RuntimeError("FR5 safety fault during gripper command: " + error)
            valid=(
                bool(getattr(state, "gripper_feedback_valid", False))
                and int(getattr(state, "grip_motion_done", 0)) == 1
                and int(getattr(state, "gripperfaultnum", 0)) == 0
                and int(getattr(state, "grippererro", 0)) == 0
                and int(state.gripper_position) == position
                and int(state.robot_motion_done)==1
            )
            if settle.update(self.state_sequence,now,valid):
                print(f"SETTLED {label}: gripper={position}, continuous_feedback>=1s; physical grasp unverified", flush=True)
                return
        raise RuntimeError(f"gripper verification timeout for position {position}")

    def assert_gripper_ready(self) -> None:
        state = self.spin_state()
        if not bool(getattr(state, "gripper_feedback_valid", False)):
            raise RuntimeError("gripper feedback is invalid or the gripper is inactive")
        faults = {
            "gripperfaultnum": int(getattr(state, "gripperfaultnum", 0)),
            "grippererro": int(getattr(state, "grippererro", 0)),
        }
        active_faults = [f"{key}={value}" for key, value in faults.items() if value]
        if active_faults:
            raise RuntimeError("gripper fault is active: " + ", ".join(active_faults))
        activation = self.response_values(
            self.service("GetGripperActivateStatus()"), 2, "gripper activation"
        )
        if int(activation[0]) != 0 or int(activation[1]) & 1 == 0:
            raise RuntimeError(
                "gripper 1 is not active: "
                f"fault={int(activation[0])}, status_bits={int(activation[1])}"
            )


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
        node.assert_gripper_ready()

        for index, item in enumerate(plan, 1):
            slot = item["slot_code"]
            pick = item["pick_final_tcp"]
            place = item["place_final_tcp"]
            print(f"\n=== {index}/4 {slot} ===", flush=True)

            node.vertical(args.transfer_z_mm, 40, f"{slot} pre-pick safe vertical")
            node.move(
                [pick[0], pick[1], args.transfer_z_mm, *pick[3:]],
                30,
                f"{slot} combined body-turn transfer to tray",
                linear=False,
            )
            node.vertical(pick[2] + 100.0, 40, f"{slot} pick 100mm hover")
            node.gripper(item["release_position"], f"{slot} pre-pick open")
            node.vertical(pick[2], 20, f"{slot} final pick descent")
            node.gripper(item["grip_position"], f"{slot} grasp")
            node.vertical(pick[2] + 100.0, 20, f"{slot} post-grasp 100mm lift")
            node.vertical(args.transfer_z_mm, 40, f"{slot} carry safe vertical")
            actual_abc = node.snapshot()[3:]
            orientation_error = math.degrees(
                (
                    Rotation.from_euler("xyz", pick[3:], degrees=True).inv()
                    * Rotation.from_euler("xyz", actual_abc, degrees=True)
                ).magnitude()
            )
            if orientation_error > 1.0:
                raise RuntimeError(
                    f"{slot} pick orientation changed by {orientation_error:.3f}deg "
                    "before board transfer"
                )
            place[3:] = actual_abc
            record["actual_orientation_decisions"].append(
                {
                    "slot_code": slot,
                    "mode": "preserve_pick_tcp_orientation",
                    "rotation_commanded": False,
                    "pick_to_carry_orientation_error_deg": orientation_error,
                    "actual_tcp_abc_deg": actual_abc,
                }
            )
            atomic_write(args.run_record, record)
            print(
                f"VERIFIED {slot}: preserving actual pick ABC; no post-grasp "
                f"rotation ({orientation_error:.3f}deg drift)", flush=True
            )
            node.move(
                [place[0], place[1], args.transfer_z_mm, *place[3:]],
                30,
                f"{slot} combined body-turn transfer to board",
                linear=False,
            )
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
