#!/usr/bin/env python3
"""MoveIt mock control plus the minimal Unity assembly callback contract."""

import argparse
import copy
import json
import math
import sys
import time
import uuid
from collections import Counter

import rclpy
from controller_manager_msgs.srv import ListHardwareComponents
from fairino_msgs.srv import RemoteCmdInterface
from lifecycle_msgs.msg import State
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

from geometry_msgs.msg import Pose, PoseStamped
from control_msgs.action import FollowJointTrajectory
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import (
    BoundingVolume,
    Constraints,
    DisplayTrajectory,
    JointConstraint,
    MoveItErrorCodes,
    OrientationConstraint,
    PositionConstraint,
)
from moveit_msgs.srv import GetCartesianPath
from rcl_interfaces.msg import FloatingPointRange, ParameterDescriptor
from sensor_msgs.msg import JointState
from shape_msgs.msg import SolidPrimitive
from std_msgs.msg import Float32, String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


JOINTS = ("j1", "j2", "j3", "j4", "j5", "j6")
INITIAL_JOINTS_DEG = (-4.689, -86.951, 84.467, -87.516, -90.0, -4.688)
GRIPPER_CLOSED_METERS = 0.021
DEFAULT_TOOL_OFFSET = (0.0, 0.0, 274.073, 0.0, 0.0, 0.0)
FUTURE_TIMEOUT_SECONDS = 60.0
FAULT_RESTART_MESSAGE = "execution state is unknown after a timeout; restart the mock node"
ASSEMBLY_STATES = {
    "STARTED", "PICKED", "PLACED", "ASSEMBLY_COMPLETED",
    "PCB_PICKED", "PCB_PLACED", "PAUSED", "COMPLETED", "FAILED",
}
STEP_STATES = {"PICKED", "PLACED"}
WORKFLOW_ACTIONS = {
    "before_all": (
        ("conveyor.move_to", "ASSEMBLY"),
        ("vision.resolve_targets", "recipe_steps"),
    ),
    "per_step": (
        ("robot.move_joint", "home"),
        ("robot.move_joint", "item_ready"),
        ("robot.pick", "current_part"),
        ("robot.move_joint", "home"),
        ("robot.move_joint", "assembly_ready"),
        ("robot.place", "current_slot"),
    ),
    "after_all": (
        ("conveyor.move_to", "INSPECTION"),
        ("inspection.run", "assembled_pcb"),
        ("robot.transfer", "assembled_pcb"),
    ),
}


class AssemblyPaused(Exception):
    """The active Mock controller goal stopped after an accepted pause request."""


def quaternion_from_rpy(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def quaternion_multiply(left, right):
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return (
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    )


def rotate_vector(quaternion, vector):
    rotated = quaternion_multiply(
        quaternion_multiply(quaternion, (*vector, 0.0)),
        (-quaternion[0], -quaternion[1], -quaternion[2], quaternion[3]),
    )
    return rotated[:3]


def gripper_position(opening_percent):
    return (100.0 - opening_percent) * GRIPPER_CLOSED_METERS / 100.0


def joint_target_reached(current_radians, target_degrees, tolerance_degrees=0.1):
    return len(current_radians) == len(target_degrees) == len(JOINTS) and all(
        abs(math.remainder(math.degrees(current) - target, 360.0))
        <= tolerance_degrees
        for current, target in zip(current_radians, target_degrees)
    )


def trajectory_target_reached(current_radians, joint_names, target_radians):
    if len(current_radians) != len(JOINTS) or len(joint_names) != len(target_radians):
        return False
    target_by_name = dict(zip(joint_names, target_radians))
    try:
        target_degrees = [math.degrees(target_by_name[name]) for name in JOINTS]
    except KeyError:
        return False
    return joint_target_reached(current_radians, target_degrees)


def arm_joint_positions(message):
    names = getattr(message, "name", None)
    positions = getattr(message, "position", None)
    if names is None or positions is None or len(names) != len(positions):
        return None
    values = dict(zip(names, positions))
    try:
        joints = tuple(values[name] for name in JOINTS)
    except KeyError:
        return None
    return joints if all(math.isfinite(value) for value in joints) else None


def parse_start_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    required_fields = {
        "command", "job_id", "recipe_version", "execution_plan",
    }
    if not isinstance(command, dict) or set(command) != required_fields:
        raise ValueError(
            "command, job_id, recipe_version and execution_plan are required"
        )
    if command["command"] != "start":
        raise ValueError("command must be start")
    job_id = command["job_id"]
    if not isinstance(job_id, str) or len(job_id) > 64:
        raise ValueError("job_id must be a UUID string")
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID string") from error
    recipe_version = command["recipe_version"]
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise ValueError("recipe_version must be a non-empty string")
    execution_plan = validate_execution_plan(command["execution_plan"])
    return job_id, recipe_version, execution_plan


def parse_transfer_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if not isinstance(command, dict) or set(command) != {
        "command", "job_id", "assembled_pcb",
    }:
        raise ValueError(
            "command, job_id and assembled_pcb are required"
        )
    if command["command"] != "transfer_assembled_pcb":
        raise ValueError("command must be transfer_assembled_pcb")
    job_id = command["job_id"]
    if not isinstance(job_id, str) or len(job_id) > 64:
        raise ValueError("job_id must be a UUID string")
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID string") from error
    return job_id, validate_assembled_pcb(command["assembled_pcb"])


def parse_pause_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if not isinstance(command, dict) or set(command) != {"command", "job_id"}:
        raise ValueError("command and job_id are required")
    if command["command"] not in {"pause", "resume"}:
        raise ValueError("command must be pause or resume")
    job_id = command["job_id"]
    if not isinstance(job_id, str) or len(job_id) > 64:
        raise ValueError("job_id must be a UUID string")
    try:
        uuid.UUID(job_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("job_id must be a UUID string") from error
    return command["command"], job_id


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def validate_ros_pose(value, label):
    if not isinstance(value, dict) or set(value) != {"xyz_mm", "xyzw"}:
        raise ValueError(f"{label} must contain xyz_mm and xyzw")
    xyz_mm = value["xyz_mm"]
    xyzw = value["xyzw"]
    if not isinstance(xyz_mm, list) or len(xyz_mm) != 3:
        raise ValueError(f"{label}.xyz_mm must contain three numbers")
    if not isinstance(xyzw, list) or len(xyzw) != 4:
        raise ValueError(f"{label}.xyzw must contain four numbers")
    xyz_mm = [
        _finite_number(number, f"{label}.xyz_mm[{index}]")
        for index, number in enumerate(xyz_mm)
    ]
    xyzw = [
        _finite_number(number, f"{label}.xyzw[{index}]")
        for index, number in enumerate(xyzw)
    ]
    norm = math.sqrt(sum(number * number for number in xyzw))
    if norm < 1e-9:
        raise ValueError(f"{label}.xyzw must not be zero")
    return {
        "xyz_mm": xyz_mm,
        "xyzw": [number / norm for number in xyzw],
    }


def validate_assembled_pcb(value):
    pose_fields = {"source", "target"}
    if not isinstance(value, dict) or set(value) != pose_fields:
        raise ValueError("assembled_pcb must contain source and target")
    return {
        "source": validate_ros_pose(value["source"], "assembled_pcb.source"),
        "target": validate_ros_pose(value["target"], "assembled_pcb.target"),
    }


def validate_joint_point(value, label):
    if not isinstance(value, list) or len(value) != len(JOINTS):
        raise ValueError(f"{label} must contain six numbers")
    for index, number in enumerate(value):
        _finite_number(number, f"{label}[{index}]")


def validate_workflow(workflow):
    if not isinstance(workflow, dict) or set(workflow) != set(WORKFLOW_ACTIONS):
        raise ValueError("workflow must contain before_all, per_step and after_all")
    for section, allowed in WORKFLOW_ACTIONS.items():
        commands = workflow[section]
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"workflow.{section} must be a non-empty list")
        actions = []
        for index, command in enumerate(commands):
            if not isinstance(command, dict) or len(command) != 1:
                raise ValueError(
                    f"workflow.{section}[{index}] must contain one action"
                )
            action = next(iter(command.items()))
            actions.append(action)
            if action not in allowed:
                raise ValueError(
                    f"unsupported workflow.{section} action: {command}"
                )
        if Counter(actions) != Counter(allowed):
            raise ValueError(
                f"workflow.{section} must contain each required action"
            )


def validate_execution_plan(value):
    required = {
        "frame", "joint_points", "motion", "workflow", "resolved_steps",
        "assembled_pcb_gripper",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(
            "execution_plan must contain frame, joint_points, motion, workflow, "
            "resolved_steps and assembled_pcb_gripper"
        )
    if value["frame"] != "base_link":
        raise ValueError("execution_plan frame must be base_link")

    joint_points = value["joint_points"]
    if not isinstance(joint_points, dict) or set(joint_points) != {
        "home", "item_ready", "assembly_ready"
    }:
        raise ValueError(
            "execution_plan joint_points must contain home, item_ready and "
            "assembly_ready"
        )
    for name in ("home", "item_ready", "assembly_ready"):
        validate_joint_point(joint_points[name], f"joint_points.{name}")

    motion = value["motion"]
    if not isinstance(motion, dict) or set(motion) != {
        "approach_dz_mm", "retract_dz_mm",
        "assembled_pcb_drop_approach_dz_mm",
    }:
        raise ValueError("execution_plan motion fields are invalid")
    for name, number in motion.items():
        if _finite_number(number, f"motion.{name}") <= 0.0:
            raise ValueError(f"motion.{name} must be greater than zero")

    validate_workflow(value["workflow"])
    assembled_profile = value["assembled_pcb_gripper"]
    validate_gripper_profile(assembled_profile, "assembled_pcb_gripper")

    resolved_steps = value["resolved_steps"]
    if not isinstance(resolved_steps, list) or not resolved_steps:
        raise ValueError("execution_plan resolved_steps must be a non-empty list")
    normalized = []
    slot_codes = set()
    required_step_fields = {
        "step", "gripper_grasp_opening_percent",
        "gripper_release_opening_percent", "source", "target",
    }
    for expected_order, resolved in enumerate(resolved_steps, 1):
        if not isinstance(resolved, dict) or set(resolved) != required_step_fields:
            raise ValueError(
                f"resolved step {expected_order} has invalid fields"
            )
        step = resolved["step"]
        if not isinstance(step, dict) or set(step) != {
            "order", "part_id", "slot_code"
        }:
            raise ValueError(
                f"resolved step {expected_order} identity is invalid"
            )
        if isinstance(step["order"], bool) \
                or not isinstance(step["order"], int) \
                or step["order"] != expected_order:
            raise ValueError("resolved step order must be consecutive from 1")
        if not isinstance(step["part_id"], str) or not step["part_id"].strip():
            raise ValueError(f"resolved step {expected_order} part_id is invalid")
        if not isinstance(step["slot_code"], str) or not step["slot_code"].strip():
            raise ValueError(f"resolved step {expected_order} slot_code is invalid")
        if step["slot_code"] in slot_codes:
            raise ValueError(f"duplicate resolved slot_code: {step['slot_code']}")
        slot_codes.add(step["slot_code"])
        grasp = _finite_number(
            resolved["gripper_grasp_opening_percent"],
            f"resolved step {expected_order} grasp opening",
        )
        release = _finite_number(
            resolved["gripper_release_opening_percent"],
            f"resolved step {expected_order} release opening",
        )
        if not 0.0 <= grasp <= 100.0 or not 0.0 <= release <= 100.0:
            raise ValueError("resolved gripper openings must be between 0 and 100")
        normalized.append({
            "step": dict(step),
            "gripper_grasp_opening_percent": grasp,
            "gripper_release_opening_percent": release,
            "source": validate_ros_pose(
                resolved["source"], f"resolved step {expected_order}.source"
            ),
            "target": validate_ros_pose(
                resolved["target"], f"resolved step {expected_order}.target"
            ),
        })
    return {
        "frame": value["frame"],
        "joint_points": joint_points,
        "motion": motion,
        "workflow": value["workflow"],
        "resolved_steps": normalized,
        "assembled_pcb_gripper": assembled_profile,
    }


def validate_gripper_profile(profile, label):
    if not isinstance(profile, dict) or set(profile) != {
        "grasp_opening_percent", "release_opening_percent"
    }:
        raise ValueError(
            f"{label} must contain grasp_opening_percent and "
            "release_opening_percent"
        )
    for field, value in profile.items():
        value = _finite_number(value, f"{label}.{field}")
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{label}.{field} must be between 0 and 100")


def vertical_offset(value, dz_mm):
    return {
        "xyz_mm": [value["xyz_mm"][0], value["xyz_mm"][1],
                   value["xyz_mm"][2] + dz_mm],
        "xyzw": list(value["xyzw"]),
    }


def assembly_feedback(job_id, state, step=None, error_code="", message=""):
    if state not in ASSEMBLY_STATES:
        raise ValueError(f"unknown assembly state: {state}")
    if state in STEP_STATES:
        if step is None:
            raise ValueError(f"{state} requires a recipe step")
        step_order = step["order"]
        part_id = step["part_id"]
        slot_code = step["slot_code"]
    else:
        step_order, part_id, slot_code = 0, "", ""
    return {
        "job_id": job_id,
        "state": state,
        "step_order": step_order,
        "part_id": part_id,
        "slot_code": slot_code,
        "error_code": error_code,
        "message": message,
    }


def empty_assembly_snapshot():
    return {
        "available": False,
        "active": False,
        "job_id": "",
        "recipe_version": "",
        "state": "IDLE",
        "placed_count": 0,
        "expected_step_count": 0,
        "held_step_order": 0,
        "held_part_id": "",
        "held_slot_code": "",
        "error_code": "",
        "message": "",
    }


def advance_assembly_snapshot(current, feedback, recipe_version, expected_step_count):
    snapshot = dict(current)
    state = feedback["state"]
    snapshot.update({
        "available": True,
        "active": state not in {"COMPLETED", "FAILED"},
        "job_id": feedback["job_id"],
        "recipe_version": recipe_version,
        "state": state,
        "expected_step_count": expected_step_count,
        "error_code": feedback["error_code"],
        "message": feedback["message"],
    })
    if state == "STARTED":
        snapshot.update({
            "placed_count": 0,
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
        })
    elif state == "PICKED":
        snapshot.update({
            "held_step_order": feedback["step_order"],
            "held_part_id": feedback["part_id"],
            "held_slot_code": feedback["slot_code"],
        })
    elif state == "PLACED":
        snapshot.update({
            "placed_count": feedback["step_order"],
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
        })
    elif state == "COMPLETED":
        snapshot.update({
            "placed_count": expected_step_count,
            "held_step_order": 0,
            "held_part_id": "",
            "held_slot_code": "",
        })
    return snapshot


def self_check():
    assert gripper_position(100.0) == 0.0
    assert gripper_position(0.0) == GRIPPER_CLOSED_METERS
    home_radians = [math.radians(value) for value in INITIAL_JOINTS_DEG]
    assert joint_target_reached(home_radians, INITIAL_JOINTS_DEG)
    home_radians[0] += math.radians(0.2)
    assert not joint_target_reached(home_radians, INITIAL_JOINTS_DEG)
    assert trajectory_target_reached(
        [math.radians(value) for value in INITIAL_JOINTS_DEG],
        JOINTS,
        [math.radians(value) for value in INITIAL_JOINTS_DEG],
    )
    assert arm_joint_positions(JointState(
        name=list(JOINTS), position=[0.0] * len(JOINTS)
    )) == (0.0,) * len(JOINTS)
    assert arm_joint_positions(JointState(
        name=list(JOINTS[1:]), position=[0.0] * (len(JOINTS) - 1)
    )) is None
    job_id = "12345678-1234-5678-1234-567812345678"
    source = {"xyz_mm": [350, -150, 250], "xyzw": [0, 0, 0, 1]}
    target = {"xyz_mm": [350, 150, 250], "xyzw": [0, 0, 0, 1]}
    assembled_pcb = {
        "source": {"xyz_mm": [450, 0, 200], "xyzw": [0, 0, 0, 1]},
        "target": {"xyz_mm": [350, 350, 200], "xyzw": [0, 0, 0, 1]},
    }
    transfer = parse_transfer_command(json.dumps({
        "command": "transfer_assembled_pcb",
        "job_id": job_id,
        "assembled_pcb": assembled_pcb,
    }))
    assert transfer[0] == job_id
    assert parse_pause_command(json.dumps({
        "command": "pause", "job_id": job_id,
    })) == ("pause", job_id)
    assert assembly_feedback(job_id, "PAUSED")["state"] == "PAUSED"
    sample_workflow = {
        "before_all": [
            {"conveyor.move_to": "ASSEMBLY"},
            {"vision.resolve_targets": "recipe_steps"},
        ],
        "per_step": [
            {"robot.move_joint": "home"},
            {"robot.move_joint": "item_ready"},
            {"robot.pick": "current_part"},
            {"robot.move_joint": "home"},
            {"robot.move_joint": "assembly_ready"},
            {"robot.place": "current_slot"},
        ],
        "after_all": [
            {"conveyor.move_to": "INSPECTION"},
            {"inspection.run": "assembled_pcb"},
            {"robot.transfer": "assembled_pcb"},
        ],
    }
    plan = validate_execution_plan({
        "frame": "base_link",
        "joint_points": {
            "home": [-4.689, -86.951, 84.467, -87.516, -90.000, -4.688],
            "item_ready": [-4.689, -86.951, 84.467, -87.516, -90.000, -4.688],
            "assembly_ready": [-4.689, -86.951, 84.467, -87.516, -90.000, -4.688],
        },
        "motion": {
            "approach_dz_mm": 100,
            "retract_dz_mm": 120,
            "assembled_pcb_drop_approach_dz_mm": 150,
        },
        "workflow": sample_workflow,
        "resolved_steps": [{
            "step": {
                "order": 1,
                "part_id": "part",
                "slot_code": "slot-01",
            },
            "gripper_grasp_opening_percent": 20,
            "gripper_release_opening_percent": 30,
            "source": source,
            "target": target,
        }],
        "assembled_pcb_gripper": {
            "grasp_opening_percent": 0,
            "release_opening_percent": 100,
        },
    })
    parsed = parse_start_command(json.dumps({
        "command": "start",
        "job_id": job_id,
        "recipe_version": "assembly-r1",
        "execution_plan": plan,
    }))
    assert parsed[:2] == (job_id, "assembly-r1")
    assert len(parsed[2]["resolved_steps"]) == 1
    resolved = parsed[2]["resolved_steps"]
    assert transfer[1]["target"]["xyz_mm"] == [350.0, 350.0, 200.0]
    assert (
        resolved[0]["gripper_grasp_opening_percent"],
        resolved[0]["gripper_release_opening_percent"],
    ) == (20, 30)
    assert resolved[0]["source"]["xyz_mm"] == [350.0, -150.0, 250.0]
    approach = vertical_offset(
        resolved[0]["source"], plan["motion"]["approach_dz_mm"]
    )
    assert approach["xyz_mm"] == [350.0, -150.0, 350.0]
    assert resolved[0]["source"]["xyz_mm"] == [350.0, -150.0, 250.0]
    pcb_drop_approach = vertical_offset(
        transfer[1]["target"],
        plan["motion"]["assembled_pcb_drop_approach_dz_mm"],
    )
    assert pcb_drop_approach["xyz_mm"] == [350.0, 350.0, 350.0]
    feedback = assembly_feedback(job_id, "PICKED", resolved[0]["step"])
    assert feedback["step_order"] == 1 and feedback["part_id"] == "part"
    terminal = assembly_feedback(job_id, "COMPLETED")
    assert terminal["step_order"] == 0 and terminal["slot_code"] == ""
    snapshot = advance_assembly_snapshot(
        empty_assembly_snapshot(),
        assembly_feedback(job_id, "STARTED"),
        "assembly-r1",
        1,
    )
    snapshot = advance_assembly_snapshot(snapshot, feedback, "assembly-r1", 1)
    assert snapshot["active"] and snapshot["held_step_order"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot,
        assembly_feedback(job_id, "PLACED", resolved[0]["step"]),
        "assembly-r1",
        1,
    )
    assert snapshot["placed_count"] == 1 and snapshot["held_step_order"] == 0
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(job_id, "ASSEMBLY_COMPLETED"), "assembly-r1", 1
    )
    assert snapshot["active"] and snapshot["placed_count"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(job_id, "PCB_PICKED"), "assembly-r1", 1
    )
    assert snapshot["active"] and snapshot["placed_count"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(job_id, "PCB_PLACED"), "assembly-r1", 1
    )
    assert snapshot["active"] and snapshot["placed_count"] == 1
    snapshot = advance_assembly_snapshot(snapshot, terminal, "assembly-r1", 1)
    assert not snapshot["active"] and snapshot["state"] == "COMPLETED"
    tcp_target = Pose()
    tcp_target.orientation.w = 1.0
    wrist_target = MockMoveJ.tool_target_to_wrist_target(
        tcp_target, DEFAULT_TOOL_OFFSET
    )
    assert wrist_target.position.x == 0.0
    assert wrist_target.position.y == 0.0
    assert math.isclose(wrist_target.position.z, -0.274073)
    assert wrist_target.orientation.w == 1.0
    try:
        parse_start_command("{}")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid assembly request was accepted")
    try:
        assembly_feedback(job_id, "PICKED")
    except ValueError:
        pass
    else:
        raise AssertionError("step callback without a step was accepted")


class MockMoveJ(Node):
    def __init__(self, args):
        super().__init__("mock_movej")
        self.args = args
        scaling_descriptor = ParameterDescriptor(
            floating_point_range=[
                FloatingPointRange(from_value=0.01, to_value=1.0, step=0.0)
            ]
        )
        self.declare_parameter(
            "mock_topSpeed", args.velocity / 100.0, scaling_descriptor
        )
        self.declare_parameter(
            "mock_accelerSpeed", args.acceleration / 100.0, scaling_descriptor
        )
        self.joint_state = None
        self.create_subscription(JointState, "/joint_states", self.on_joint_state, 10)
        self.pending_joint_target = None
        self.pending_pose_target = None
        self.pending_ptp_pose = None
        self.pending_gripper_target = None
        self.active_assembly = None
        self.active_motion_goal = None
        self.active_motion_cancel = None
        self.latest_assembly_snapshot = empty_assembly_snapshot()
        self.manual_executing = False
        self.execution_faulted = False
        self.assembly_feedback_publisher = self.create_publisher(
            String, "/unity/assembly/feedback", 10
        )
        if args.listen_unity:
            self.create_subscription(
                JointState, "/unity/joint_target", self.on_joint_target, 10
            )
            self.create_subscription(
                PoseStamped, "/unity/tcp_target",
                lambda message: self.on_pose_target(message, True), 10
            )
            self.create_subscription(
                PoseStamped, "/unity/movej_target", self.on_ptp_pose, 10
            )
            self.create_subscription(
                PoseStamped, "/twin_visual/movel_target",
                lambda message: self.on_pose_target(message, False), 10
            )
            self.create_subscription(
                Float32, "/unity/gripper_target", self.on_gripper_target, 10
            )
            self.create_service(
                RemoteCmdInterface,
                "/unity/assembly/start",
                self.on_start_assembly,
            )
        self.move_client = ActionClient(self, MoveGroup, "/move_action")
        self.arm_client = ActionClient(
            self, FollowJointTrajectory,
            "/fairino5_controller/follow_joint_trajectory"
        )
        self.gripper_client = ActionClient(
            self, FollowJointTrajectory,
            "/gripper_controller/follow_joint_trajectory"
        )
        self.cartesian_client = self.create_client(GetCartesianPath, "/compute_cartesian_path")
        self.hardware_components_client = self.create_client(
            ListHardwareComponents, "/controller_manager/list_hardware_components"
        )
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.display_publisher = self.create_publisher(
            DisplayTrajectory, "/display_planned_path", qos
        )
        self.preview_publisher = self.create_publisher(
            JointTrajectory, "/twin_visual/movel_preview", 10
        )
        self.status_publisher = self.create_publisher(String, "/twin_visual/status", 10)

    def on_joint_state(self, message):
        if arm_joint_positions(message) is not None:
            self.joint_state = message

    def motion_scaling(self):
        return (
            self.get_parameter("mock_topSpeed").value,
            self.get_parameter("mock_accelerSpeed").value,
        )

    def allow_manual_command(self):
        if self.execution_faulted:
            self.publish_status(f"error: FAULTED: {FAULT_RESTART_MESSAGE}")
            return False
        if self.active_assembly is None:
            return True
        self.publish_status("error: manual command rejected while assembly is active")
        return False

    def on_gripper_target(self, message):
        if not self.allow_manual_command():
            return
        if not math.isfinite(message.data) or not 0.0 <= message.data <= 100.0:
            self.publish_status("error: gripper target must be between 0 and 100 percent")
            return
        self.pending_gripper_target = message.data

    def on_joint_target(self, message):
        if not self.allow_manual_command():
            return
        try:
            if len(message.name) != len(message.position):
                raise ValueError("joint target names and positions have different lengths")
            positions = dict(zip(message.name, message.position))
            radians = [positions[name] for name in JOINTS]
            if not all(math.isfinite(value) for value in radians):
                raise ValueError("joint target contains NaN or infinity")
            self.pending_joint_target = [math.degrees(value) for value in radians]
        except (KeyError, ValueError) as error:
            self.get_logger().error(f"invalid /unity/joint_target: {error}")

    def on_pose_target(self, message, execute_mock):
        if not self.allow_manual_command():
            return
        self.pending_pose_target = (message, execute_mock)

    def on_ptp_pose(self, message):
        if not self.allow_manual_command():
            return
        self.pending_ptp_pose = message

    def manual_command_pending(self):
        return any(target is not None for target in (
            self.pending_joint_target,
            self.pending_pose_target,
            self.pending_ptp_pose,
            self.pending_gripper_target,
        ))

    @staticmethod
    def start_response(response, accepted, job_id="", error_code="", message=""):
        response.cmd_res = json.dumps({
            "accepted": accepted,
            "job_id": job_id,
            "error_code": error_code,
            "message": message,
        }, separators=(",", ":"))
        return response

    def on_start_assembly(self, request, response):
        try:
            command = json.loads(request.cmd_str)
        except (TypeError, json.JSONDecodeError):
            command = None
        if command == {"command": "status"}:
            response.cmd_res = json.dumps(
                self.latest_assembly_snapshot, separators=(",", ":")
            )
            return response

        if isinstance(command, dict) and command.get("command") in {
            "pause", "resume",
        }:
            try:
                control, job_id = parse_pause_command(request.cmd_str)
            except ValueError as error:
                return self.start_response(
                    response, False, error_code="INVALID_REQUEST", message=str(error)
                )
            job = self.active_assembly
            if job is None or job["job_id"] != job_id:
                return self.start_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if self.execution_faulted:
                return self.start_response(
                    response, False, job_id, "FAULTED", FAULT_RESTART_MESSAGE
                )
            job["pause_requested"] = control == "pause"
            if control == "pause":
                self.cancel_active_motion()
            return self.start_response(response, True, job_id)

        if isinstance(command, dict) \
                and command.get("command") == "transfer_assembled_pcb":
            try:
                job_id, assembled_pcb = parse_transfer_command(request.cmd_str)
            except ValueError as error:
                return self.start_response(
                    response, False, error_code="INVALID_REQUEST", message=str(error)
                )
            if self.execution_faulted:
                return self.start_response(
                    response, False, job_id, "FAULTED", FAULT_RESTART_MESSAGE
                )
            job = self.active_assembly
            if job is None or job["job_id"] != job_id:
                return self.start_response(
                    response, False, job_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if job["pause_requested"] or job["paused"]:
                return self.start_response(
                    response, False, job_id, "BUSY",
                    "assembly is paused",
                )
            if job["phase"] != "awaiting_transfer":
                return self.start_response(
                    response, False, job_id, "BUSY",
                    "assembly is not ready for PCB transfer",
                )
            if self.args.plan_only:
                return self.start_response(
                    response, False, job_id, "PLAN_ONLY",
                    "PCB transfer requires execution mode",
                )
            job["assembled_pcb"] = assembled_pcb
            job["phase"] = "transferring"
            return self.start_response(response, True, job_id)

        try:
            job_id, recipe_version, execution_plan = parse_start_command(
                request.cmd_str
            )
        except ValueError as error:
            return self.start_response(
                response, False, error_code="INVALID_REQUEST", message=str(error)
            )
        if self.execution_faulted:
            return self.start_response(
                response, False, job_id, "FAULTED", FAULT_RESTART_MESSAGE
            )
        if self.active_assembly is not None or self.manual_executing \
                or self.manual_command_pending():
            return self.start_response(
                response, False, job_id, "BUSY", "robot is already executing"
            )
        if self.args.plan_only:
            return self.start_response(
                response, False, job_id, "PLAN_ONLY", "assembly requires execution mode"
            )
        self.active_assembly = {
            "job_id": job_id,
            "recipe_version": recipe_version,
            "execution_plan": execution_plan,
            "phase": "assembling",
            "pause_requested": False,
            "paused": False,
            "resume_feedback": assembly_feedback(job_id, "STARTED"),
        }
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            assembly_feedback(job_id, "STARTED"),
            recipe_version,
            len(execution_plan["resolved_steps"]),
        )
        return self.start_response(response, True, job_id)

    def publish_assembly_feedback(
        self, job_id, state, step=None, error_code="", message=""
    ):
        payload = assembly_feedback(job_id, state, step, error_code, message)
        job = self.active_assembly
        if state != "PAUSED":
            job["resume_feedback"] = payload
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            payload,
            job["recipe_version"],
            len(job["execution_plan"]["resolved_steps"]),
        )
        self.assembly_feedback_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )
        self.get_logger().info(f"assembly {state}: job_id={job_id}")

    def wait_if_paused(self, job):
        if not job["pause_requested"]:
            return
        job["paused"] = True
        self.publish_assembly_feedback(job["job_id"], "PAUSED")
        while rclpy.ok() and job["pause_requested"]:
            rclpy.spin_once(self, timeout_sec=0.1)
        if not rclpy.ok() or self.active_assembly is not job:
            raise RuntimeError("assembly pause was interrupted")
        job["paused"] = False
        payload = job["resume_feedback"]
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            payload,
            job["recipe_version"],
            len(job["execution_plan"]["resolved_steps"]),
        )
        self.assembly_feedback_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )
        self.get_logger().info(f"assembly resumed: job_id={job['job_id']}")

    def cancel_active_motion(self):
        handle = self.active_motion_goal
        if handle is not None and self.active_motion_cancel is None:
            self.active_motion_cancel = handle.cancel_goal_async()

    def confirm_motion_cancellation(self, cancellation, label):
        if cancellation is None:
            return
        response = self.wait_for_future(cancellation, f"{label} cancellation")
        if response is None or not response.goals_canceling:
            self.get_logger().warning(
                f"{label} completed before the pause cancellation was accepted"
            )

    def pause_requested(self):
        return self.active_assembly is not None and self.active_assembly["pause_requested"]

    def run_pauseable(self, job, operation):
        while True:
            self.wait_if_paused(job)
            try:
                operation()
                return
            except AssemblyPaused:
                self.wait_if_paused(job)

    def publish_status(self, value):
        self.status_publisher.publish(String(data=value))
        self.get_logger().info(value)

    def wait_for_future(self, future, label):
        rclpy.spin_until_future_complete(
            self, future, timeout_sec=FUTURE_TIMEOUT_SECONDS
        )
        if not future.done():
            self.execution_faulted = True
            self.pending_joint_target = None
            self.pending_pose_target = None
            self.pending_ptp_pose = None
            self.pending_gripper_target = None
            raise RuntimeError(
                f"{label} timed out after {FUTURE_TIMEOUT_SECONDS:.0f} seconds"
            )
        return future.result()

    def wait_for_joint_state(self):
        deadline = time.monotonic() + 5.0
        while self.joint_state is None and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
        if self.joint_state is None:
            raise RuntimeError("/joint_states is unavailable")

    def log_joint_state(self, label):
        values = dict(zip(self.joint_state.name, self.joint_state.position))
        degrees = [math.degrees(values[name]) for name in JOINTS]
        self.get_logger().info(
            f"{label} joint_states [deg]: " + ", ".join(f"{v:.3f}" for v in degrees)
        )

    def make_joint_goal(self):
        radians = [math.radians(value) for value in self.args.joints]
        return Constraints(
            joint_constraints=[
                JointConstraint(
                    joint_name=name,
                    position=value,
                    tolerance_above=0.001,
                    tolerance_below=0.001,
                    weight=1.0,
                )
                for name, value in zip(JOINTS, radians)
            ]
        )

    def make_pose_goal(self, pose_target=None):
        if pose_target is None:
            x, y, z, rx, ry, rz = self.args.pose
            qx, qy, qz, qw = quaternion_from_rpy(
                math.radians(rx), math.radians(ry), math.radians(rz)
            )
            target = Pose()
            target.position.x = x / 1000.0
            target.position.y = y / 1000.0
            target.position.z = z / 1000.0
            target.orientation.x = qx
            target.orientation.y = qy
            target.orientation.z = qz
            target.orientation.w = qw
            frame = self.args.frame
        else:
            target = copy.deepcopy(pose_target.pose)
            frame = pose_target.header.frame_id or self.args.frame

        values = (
            target.position.x, target.position.y, target.position.z,
            target.orientation.x, target.orientation.y,
            target.orientation.z, target.orientation.w,
        )
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError("MoveJ target contains NaN or infinity")
        norm = math.sqrt(sum(value * value for value in values[3:]))
        if norm < 1e-9:
            raise RuntimeError("MoveJ target orientation has zero length")
        target.orientation.x /= norm
        target.orientation.y /= norm
        target.orientation.z /= norm
        target.orientation.w /= norm
        target = self.tool_target_to_wrist_target(target, self.args.tool_offset)

        region_pose = Pose()
        region_pose.position = target.position
        region_pose.orientation.w = 1.0
        sphere = SolidPrimitive(type=SolidPrimitive.SPHERE, dimensions=[0.001])

        position = PositionConstraint()
        position.header.frame_id = frame
        position.link_name = self.args.tip
        position.constraint_region = BoundingVolume(
            primitives=[sphere], primitive_poses=[region_pose]
        )
        position.weight = 1.0

        orientation = OrientationConstraint()
        orientation.header.frame_id = frame
        orientation.link_name = self.args.tip
        orientation.orientation = target.orientation
        orientation.absolute_x_axis_tolerance = 0.01
        orientation.absolute_y_axis_tolerance = 0.01
        orientation.absolute_z_axis_tolerance = 0.01
        orientation.weight = 1.0

        return Constraints(
            position_constraints=[position], orientation_constraints=[orientation]
        )

    @staticmethod
    def tool_target_to_wrist_target(tcp_target, tool_offset):
        x, y, z, rx, ry, rz = tool_offset
        tool_rotation = quaternion_from_rpy(
            math.radians(rx), math.radians(ry), math.radians(rz)
        )
        tcp_rotation = (
            tcp_target.orientation.x,
            tcp_target.orientation.y,
            tcp_target.orientation.z,
            tcp_target.orientation.w,
        )
        wrist_rotation = quaternion_multiply(
            tcp_rotation,
            (-tool_rotation[0], -tool_rotation[1], -tool_rotation[2], tool_rotation[3]),
        )
        offset = rotate_vector(wrist_rotation, (x / 1000.0, y / 1000.0, z / 1000.0))
        wrist_target = Pose()
        wrist_target.position.x = tcp_target.position.x - offset[0]
        wrist_target.position.y = tcp_target.position.y - offset[1]
        wrist_target.position.z = tcp_target.position.z - offset[2]
        wrist_target.orientation.x = wrist_rotation[0]
        wrist_target.orientation.y = wrist_rotation[1]
        wrist_target.orientation.z = wrist_rotation[2]
        wrist_target.orientation.w = wrist_rotation[3]
        return wrist_target

    def plan(self, pose_target=None):
        if not self.move_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("/move_action is unavailable; start the MoveIt mock demo first")

        goal = MoveGroup.Goal()
        goal.request.group_name = "fairino5_v6_group"
        goal.request.pipeline_id = "pilz_industrial_motion_planner"
        goal.request.planner_id = "PTP"
        goal.request.num_planning_attempts = 1
        goal.request.allowed_planning_time = 5.0
        velocity, acceleration = self.motion_scaling()
        goal.request.max_velocity_scaling_factor = velocity
        goal.request.max_acceleration_scaling_factor = acceleration
        goal.request.start_state.is_diff = True
        goal.request.goal_constraints = [
            self.make_pose_goal(pose_target) if pose_target is not None else (
                self.make_joint_goal() if self.args.joints else self.make_pose_goal()
            )
        ]
        goal.planning_options.plan_only = True

        future = self.move_client.send_goal_async(goal)
        handle = self.wait_for_future(future, "PTP goal acceptance")
        if not handle or not handle.accepted:
            raise RuntimeError("MoveIt rejected the PTP planning request")

        future = handle.get_result_async()
        result = self.wait_for_future(future, "PTP planning").result
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"PTP planning failed: MoveIt code {result.error_code.val}")

        return self.validate_and_publish(
            result.planned_trajectory, result.trajectory_start, "PTP"
        )

    def validate_and_publish(self, trajectory, trajectory_start, label):
        joint_trajectory = trajectory.joint_trajectory
        points = joint_trajectory.points
        if not points:
            raise RuntimeError(f"{label} returned no trajectory points")
        try:
            j3_index = joint_trajectory.joint_names.index("j3")
        except ValueError as error:
            raise RuntimeError(f"{label} trajectory is missing j3") from error
        min_j3 = math.radians(self.args.min_j3_deg)
        if any(
            len(point.positions) != len(joint_trajectory.joint_names)
            or not all(math.isfinite(value) for value in point.positions)
            for point in points
        ):
            raise RuntimeError(f"{label} trajectory contains invalid joint positions")
        if any(point.positions[j3_index] < min_j3 for point in points):
            raise RuntimeError(
                f"{label} rejected: j3 would move below {self.args.min_j3_deg:.1f} deg"
            )
        current = arm_joint_positions(self.joint_state)
        if len(points) == 1:
            if current is not None and trajectory_target_reached(
                current, joint_trajectory.joint_names, points[0].positions
            ):
                self.publish_status(f"execution: {label} target already reached")
                return None
            raise RuntimeError(f"{label} returned fewer than two trajectory points")
        duration = points[-1].time_from_start.sec + points[-1].time_from_start.nanosec / 1e9
        if duration <= 0.0:
            for index, point in enumerate(points):
                nanoseconds = round(index * 0.05 * 1_000_000_000)
                point.time_from_start.sec = nanoseconds // 1_000_000_000
                point.time_from_start.nanosec = nanoseconds % 1_000_000_000
            duration = max(0.05, (len(points) - 1) * 0.05)

        self.display_publisher.publish(
            DisplayTrajectory(trajectory_start=trajectory_start, trajectory=[trajectory])
        )
        self.preview_publisher.publish(joint_trajectory)
        self.publish_status(
            f"ready: {label} points={len(points)} duration={duration:.2f}s"
        )
        return trajectory

    def plan_linear(self, target):
        target = copy.deepcopy(target)
        if not self.cartesian_client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError("/compute_cartesian_path is unavailable")
        if not target.header.frame_id:
            target.header.frame_id = self.args.frame

        values = (
            target.pose.position.x, target.pose.position.y, target.pose.position.z,
            target.pose.orientation.x, target.pose.orientation.y,
            target.pose.orientation.z, target.pose.orientation.w,
        )
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError("MoveL target contains NaN or infinity")
        norm = math.sqrt(sum(value * value for value in values[3:]))
        if norm < 1e-9:
            raise RuntimeError("MoveL target orientation has zero length")
        target.pose.orientation.x /= norm
        target.pose.orientation.y /= norm
        target.pose.orientation.z /= norm
        target.pose.orientation.w /= norm
        target.pose = self.tool_target_to_wrist_target(target.pose, self.args.tool_offset)

        request = GetCartesianPath.Request()
        request.header = target.header
        request.start_state.is_diff = True
        request.group_name = "fairino5_v6_group"
        request.link_name = self.args.tip
        request.waypoints = [target.pose]
        request.max_step = self.args.max_step
        request.revolute_jump_threshold = self.args.max_joint_step
        request.avoid_collisions = True
        velocity, acceleration = self.motion_scaling()
        request.max_velocity_scaling_factor = velocity
        request.max_acceleration_scaling_factor = acceleration

        self.publish_status("planning: LIN")
        future = self.cartesian_client.call_async(request)
        response = self.wait_for_future(future, "MoveL planning")
        if response is None or response.error_code.val != MoveItErrorCodes.SUCCESS:
            code = response.error_code.val if response is not None else "no response"
            raise RuntimeError(f"MoveL planning failed: MoveIt code {code}")
        if response.fraction < 1.0 - 1e-6:
            raise RuntimeError(
                f"MoveL path is only {response.fraction * 100.0:.1f}% complete"
            )
        return self.validate_and_publish(
            response.solution, request.start_state, "LIN"
        )

    def require_mock_hardware(self):
        if not self.hardware_components_client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError("/controller_manager/list_hardware_components is unavailable")
        future = self.hardware_components_client.call_async(
            ListHardwareComponents.Request()
        )
        response = self.wait_for_future(future, "mock hardware inspection")
        active_mock = any(
            component.name == "FakeSystem"
            and component.plugin_name == "mock_components/GenericSystem"
            and component.state.id == State.PRIMARY_STATE_ACTIVE
            for component in response.component
        )
        if not active_mock:
            raise RuntimeError("execution blocked: active FakeSystem mock hardware is unavailable")

    def execute(self, trajectory):
        if trajectory is None:
            return
        self.require_mock_hardware()
        if not self.arm_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("arm controller is unavailable")
        if self.pause_requested():
            raise AssemblyPaused()

        time.sleep(self.args.preview_seconds)
        if self.pause_requested():
            raise AssemblyPaused()
        self.publish_status("execution: sending trajectory to mock controller")
        future = self.arm_client.send_goal_async(
            FollowJointTrajectory.Goal(trajectory=trajectory.joint_trajectory)
        )
        handle = self.wait_for_future(future, "trajectory goal acceptance")
        if not handle or not handle.accepted:
            raise RuntimeError("mock controller rejected the trajectory")

        self.active_motion_goal = handle
        self.active_motion_cancel = None
        if self.pause_requested():
            self.cancel_active_motion()
        try:
            future = handle.get_result_async()
            result = self.wait_for_future(future, "trajectory execution").result
        finally:
            if self.active_motion_goal is handle:
                self.active_motion_goal = None
        if self.pause_requested():
            self.confirm_motion_cancellation(
                self.active_motion_cancel, "trajectory"
            )
            self.joint_state = None
            self.wait_for_joint_state()
            raise AssemblyPaused()
        if result.error_code != FollowJointTrajectory.Result.SUCCESSFUL:
            raise RuntimeError("arm controller execution failed")
        self.joint_state = None
        self.wait_for_joint_state()
        self.publish_status("execution: complete")

    def run(self):
        self.wait_for_joint_state()
        self.log_joint_state("start")
        trajectory = self.plan()
        if self.args.plan_only:
            self.get_logger().info("plan-only: trajectory published to /display_planned_path")
            return
        self.execute(trajectory)
        self.log_joint_state("finish")

    def run_joint_target(self, joint_degrees):
        self.wait_for_joint_state()
        current = dict(zip(self.joint_state.name, self.joint_state.position))
        if joint_target_reached([current[name] for name in JOINTS], joint_degrees):
            self.publish_status("execution: joint target already reached")
            return

        previous = self.args.joints
        self.args.joints = joint_degrees
        try:
            self.run()
        finally:
            self.args.joints = previous

    def run_linear(self, target, execute_mock):
        self.wait_for_joint_state()
        self.log_joint_state("start")
        trajectory = self.plan_linear(target)
        if self.args.plan_only or not execute_mock:
            return
        self.execute(trajectory)
        self.log_joint_state("finish")

    def run_ptp_pose(self, target):
        self.wait_for_joint_state()
        self.log_joint_state("start")
        trajectory = self.plan(target)
        if self.args.plan_only:
            return
        self.execute(trajectory)
        self.log_joint_state("finish")

    def run_gripper(self, opening_percent):
        if not self.gripper_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("gripper controller is unavailable")
        if self.pause_requested():
            raise AssemblyPaused()
        point = JointTrajectoryPoint(
            positions=[gripper_position(opening_percent)]
        )
        point.time_from_start.sec = 1
        trajectory = JointTrajectory(
            joint_names=["finger_right_joint"], points=[point]
        )
        self.publish_status(f"gripper: moving to {opening_percent:.1f}% open")
        future = self.gripper_client.send_goal_async(
            FollowJointTrajectory.Goal(trajectory=trajectory)
        )
        handle = self.wait_for_future(future, "gripper goal acceptance")
        if not handle or not handle.accepted:
            raise RuntimeError("gripper controller rejected the trajectory")
        self.active_motion_goal = handle
        self.active_motion_cancel = None
        if self.pause_requested():
            self.cancel_active_motion()
        try:
            future = handle.get_result_async()
            result = self.wait_for_future(future, "gripper execution").result
        finally:
            if self.active_motion_goal is handle:
                self.active_motion_goal = None
        if self.pause_requested():
            self.confirm_motion_cancellation(self.active_motion_cancel, "gripper")
            raise AssemblyPaused()
        if result.error_code != FollowJointTrajectory.Result.SUCCESSFUL:
            raise RuntimeError("gripper execution failed")
        self.publish_status("gripper: complete")

    @staticmethod
    def pose_stamped(frame, xyz_mm, xyzw):
        target = PoseStamped()
        target.header.frame_id = frame
        target.pose.position.x = xyz_mm[0] / 1000.0
        target.pose.position.y = xyz_mm[1] / 1000.0
        target.pose.position.z = xyz_mm[2] / 1000.0
        target.pose.orientation.x = xyzw[0]
        target.pose.orientation.y = xyzw[1]
        target.pose.orientation.z = xyzw[2]
        target.pose.orientation.w = xyzw[3]
        return target

    def request_pose(self, recipe, value):
        return self.pose_stamped(recipe["frame"], value["xyz_mm"], value["xyzw"])

    def run_assembly(self, job):
        job_id = job["job_id"]
        execution_plan = job["execution_plan"]
        try:
            self.require_mock_hardware()
            self.publish_assembly_feedback(job_id, "STARTED")
            joint_points = execution_plan["joint_points"]
            motion = execution_plan["motion"]
            for command in execution_plan["workflow"]["before_all"]:
                self.wait_if_paused(job)
                action, argument = next(iter(command.items()))
                if (action, argument) == ("conveyor.move_to", "ASSEMBLY"):
                    self.publish_status("conveyor at assembly: confirmed by Unity")
                elif (action, argument) == (
                    "vision.resolve_targets", "recipe_steps"
                ):
                    self.publish_status("vision targets: simulated valid (Mock)")
                else:
                    raise RuntimeError(f"unknown preflight action: {command}")
                self.wait_if_paused(job)
            for resolved in execution_plan["resolved_steps"]:
                step = resolved["step"]
                grasp_opening_percent = resolved[
                    "gripper_grasp_opening_percent"
                ]
                release_opening_percent = resolved[
                    "gripper_release_opening_percent"
                ]
                source = self.request_pose(execution_plan, resolved["source"])
                target = self.request_pose(execution_plan, resolved["target"])
                source_approach = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        resolved["source"], motion["approach_dz_mm"]
                    ),
                )
                source_retract = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        resolved["source"], motion["retract_dz_mm"]
                    ),
                )
                target_approach = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        resolved["target"], motion["approach_dz_mm"]
                    ),
                )
                target_retract = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        resolved["target"], motion["retract_dz_mm"]
                    ),
                )

                for command in execution_plan["workflow"]["per_step"]:
                    self.wait_if_paused(job)
                    action, argument = next(iter(command.items()))
                    if action == "robot.move_joint":
                        self.run_pauseable(job, lambda: self.run_joint_target(joint_points[argument]))
                    elif (action, argument) == ("robot.pick", "current_part"):
                        self.run_pauseable(job, lambda: self.run_gripper(release_opening_percent))
                        self.run_pauseable(job, lambda: self.run_ptp_pose(source_approach))
                        self.run_pauseable(job, lambda: self.run_linear(source, True))
                        self.run_pauseable(job, lambda: self.run_gripper(grasp_opening_percent))
                        self.publish_assembly_feedback(job_id, "PICKED", step)
                        self.run_pauseable(job, lambda: self.run_linear(source_retract, True))
                    elif (action, argument) == ("robot.place", "current_slot"):
                        self.run_pauseable(job, lambda: self.run_ptp_pose(target_approach))
                        self.run_pauseable(job, lambda: self.run_linear(target, True))
                        self.run_pauseable(job, lambda: self.run_gripper(release_opening_percent))
                        self.publish_assembly_feedback(job_id, "PLACED", step)
                        self.run_pauseable(job, lambda: self.run_linear(target_retract, True))
                    else:
                        raise RuntimeError(f"unknown assembly action: {command}")
                    self.wait_if_paused(job)

            self.publish_assembly_feedback(job_id, "ASSEMBLY_COMPLETED")
            job["phase"] = "awaiting_transfer"
        except Exception as error:
            self.preview_publisher.publish(JointTrajectory())
            message = str(error)[:512]
            self.publish_status(f"error: assembly failed: {message}")
            try:
                self.publish_assembly_feedback(
                    job_id, "FAILED", error_code="EXECUTION_FAILED",
                    message=message,
                )
            finally:
                self.active_assembly = None

    def run_assembled_pcb_transfer(self, job):
        job_id = job["job_id"]
        execution_plan = job["execution_plan"]
        terminal_state = "FAILED"
        error_code = "INTERRUPTED"
        message = "assembled PCB transfer interrupted"
        try:
            self.require_mock_hardware()
            motion = execution_plan["motion"]
            gripper = execution_plan["assembled_pcb_gripper"]
            for command in execution_plan["workflow"]["after_all"]:
                self.wait_if_paused(job)
                action, argument = next(iter(command.items()))
                if (action, argument) in {
                    ("conveyor.move_to", "INSPECTION"),
                    ("inspection.run", "assembled_pcb"),
                }:
                    self.publish_status(f"{action}: confirmed externally")
                    continue
                if (action, argument) != ("robot.transfer", "assembled_pcb"):
                    raise RuntimeError(
                        f"unknown final assembly action: {command}"
                    )
                transfer = job["assembled_pcb"]
                source = self.request_pose(execution_plan, transfer["source"])
                target = self.request_pose(execution_plan, transfer["target"])
                source_approach = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        transfer["source"], motion["approach_dz_mm"]
                    ),
                )
                source_retract = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        transfer["source"], motion["retract_dz_mm"]
                    ),
                )
                target_approach = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        transfer["target"],
                        motion["assembled_pcb_drop_approach_dz_mm"],
                    ),
                )
                target_retract = self.request_pose(
                    execution_plan,
                    vertical_offset(
                        transfer["target"], motion["retract_dz_mm"]
                    ),
                )
                self.run_pauseable(
                    job, lambda: self.run_gripper(gripper["release_opening_percent"])
                )
                self.run_pauseable(job, lambda: self.run_ptp_pose(source_approach))
                self.run_pauseable(job, lambda: self.run_linear(source, True))
                self.run_pauseable(
                    job, lambda: self.run_gripper(gripper["grasp_opening_percent"])
                )
                self.publish_assembly_feedback(job_id, "PCB_PICKED")
                self.run_pauseable(job, lambda: self.run_linear(source_retract, True))
                self.run_pauseable(job, lambda: self.run_ptp_pose(target_approach))
                self.run_pauseable(job, lambda: self.run_linear(target, True))
                self.run_pauseable(
                    job, lambda: self.run_gripper(gripper["release_opening_percent"])
                )
                self.publish_assembly_feedback(job_id, "PCB_PLACED")
                self.run_pauseable(job, lambda: self.run_linear(target_retract, True))
                self.wait_if_paused(job)
            terminal_state = "COMPLETED"
            error_code = ""
            message = ""
        except Exception as error:
            self.preview_publisher.publish(JointTrajectory())
            error_code = "EXECUTION_FAILED"
            message = str(error)[:512]
            self.publish_status(f"error: assembled PCB transfer failed: {message}")
        finally:
            try:
                self.publish_assembly_feedback(
                    job_id, terminal_state, error_code=error_code, message=message
                )
            finally:
                self.active_assembly = None

    def listen(self):
        self.args.joints = INITIAL_JOINTS_DEG
        self.publish_status("initializing: moving to initial joint pose")
        self.run()
        self.args.joints = None
        self.publish_status("ready: waiting for Unity MoveJ or MoveL target")
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            job = self.active_assembly
            phase = job["phase"] if job is not None else None
            if job is not None and job["pause_requested"]:
                self.wait_if_paused(job)
                continue
            is_assembly = phase in {"assembling", "transferring"}
            if phase == "assembling":
                operation = lambda: self.run_assembly(job)
            elif phase == "transferring":
                operation = lambda: self.run_assembled_pcb_transfer(job)
            elif self.pending_joint_target is not None:
                self.args.joints = self.pending_joint_target
                self.pending_joint_target = None
                operation = self.run
            elif self.pending_pose_target is not None:
                target, execute_mock = self.pending_pose_target
                self.pending_pose_target = None
                operation = lambda: self.run_linear(target, execute_mock)
            elif self.pending_ptp_pose is not None:
                target = self.pending_ptp_pose
                self.pending_ptp_pose = None
                operation = lambda: self.run_ptp_pose(target)
            elif self.pending_gripper_target is not None:
                target = self.pending_gripper_target
                self.pending_gripper_target = None
                operation = lambda: self.run_gripper(target)
            else:
                continue
            try:
                self.manual_executing = not is_assembly
                operation()
            except Exception as error:
                self.preview_publisher.publish(JointTrajectory())
                self.publish_status(f"error: {error}")
            finally:
                self.manual_executing = False


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="FAIRINO AIO MoveJ-like mock using MoveIt Pilz PTP"
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--joints",
        nargs=6,
        type=float,
        metavar=("J1", "J2", "J3", "J4", "J5", "J6"),
        help="target joint angles in degrees (AIO JNTPoint-like)",
    )
    target.add_argument(
        "--pose",
        nargs=6,
        type=float,
        metavar=("X", "Y", "Z", "RX", "RY", "RZ"),
        help="target pose in mm/degrees (AIO CARTPoint-like; MoveIt solves IK)",
    )
    parser.add_argument("--velocity", type=float, default=100.0, choices=range(1, 101))
    parser.add_argument("--acceleration", type=float, default=100.0, choices=range(1, 101))
    parser.add_argument("--frame", default="base_link")
    parser.add_argument("--tip", default="wrist3_link")
    parser.add_argument(
        "--tool-offset",
        nargs=6,
        type=float,
        default=DEFAULT_TOOL_OFFSET,
        metavar=("X", "Y", "Z", "RX", "RY", "RZ"),
        help="wrist3_link to Tool TCP offset in mm/degrees",
    )
    parser.add_argument("--preview-seconds", type=float, default=0.0)
    parser.add_argument("--max-step", type=float, default=0.005)
    parser.add_argument("--max-joint-step", type=float, default=0.35)
    parser.add_argument("--min-j3-deg", type=float, default=0.0)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--listen-unity", action="store_true")
    args = parser.parse_args(argv)
    if not args.listen_unity and args.joints is None and args.pose is None:
        parser.error("one of --joints, --pose or --listen-unity is required")
    if args.preview_seconds < 0.0 or args.max_step <= 0.0 or args.max_joint_step <= 0.0:
        parser.error("preview-seconds must be nonnegative and Cartesian steps positive")
    if args.min_j3_deg < 0.0:
        parser.error("min-j3-deg must be greater than or equal to 0")
    if not all(math.isfinite(value) for value in args.tool_offset):
        parser.error("tool-offset values must be finite")
    return args


def main():
    args = parse_args(rclpy.utilities.remove_ros_args(args=sys.argv)[1:])
    try:
        self_check()
    except (ValueError, AssertionError) as error:
        raise SystemExit(f"mock startup validation failed: {error}") from error
    rclpy.init()
    node = MockMoveJ(args)
    try:
        node.listen() if args.listen_unity else node.run()
    except Exception as error:
        node.get_logger().error(str(error))
        sys.exit(1)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
