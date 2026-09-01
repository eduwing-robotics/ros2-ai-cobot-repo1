#!/usr/bin/env python3
"""MoveIt mock control plus the minimal Unity assembly callback contract."""

import argparse
import json
import math
import sys
import time
import uuid
from pathlib import Path

import rclpy
import yaml
from controller_manager_msgs.srv import ListHardwareComponents
from fairino_msgs.srv import RemoteCmdInterface
from lifecycle_msgs.msg import State
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

from geometry_msgs.msg import Pose, PoseStamped
from control_msgs.action import FollowJointTrajectory
from moveit_msgs.action import ExecuteTrajectory, MoveGroup
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
    "PCB_PICKED", "PCB_PLACED", "COMPLETED", "FAILED",
}
STEP_STATES = {"PICKED", "PLACED"}


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
    if not isinstance(command, dict) or set(command) != {
        "command", "request_id", "recipe_version", "observations",
    }:
        raise ValueError(
            "command, request_id, recipe_version and observations are required"
        )
    if command["command"] != "start":
        raise ValueError("command must be start")
    request_id = command["request_id"]
    if not isinstance(request_id, str) or len(request_id) > 64:
        raise ValueError("request_id must be a UUID string")
    try:
        uuid.UUID(request_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("request_id must be a UUID string") from error
    recipe_version = command["recipe_version"]
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise ValueError("recipe_version must be a non-empty string")
    return (
        request_id, recipe_version,
        validate_observations(command["observations"]),
    )


def parse_transfer_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if not isinstance(command, dict) or set(command) != {
        "command", "request_id", "assembled_pcb",
    }:
        raise ValueError(
            "command, request_id and assembled_pcb are required"
        )
    if command["command"] != "transfer_assembled_pcb":
        raise ValueError("command must be transfer_assembled_pcb")
    request_id = command["request_id"]
    if not isinstance(request_id, str) or len(request_id) > 64:
        raise ValueError("request_id must be a UUID string")
    try:
        uuid.UUID(request_id)
    except (ValueError, AttributeError) as error:
        raise ValueError("request_id must be a UUID string") from error
    return request_id, validate_assembled_pcb(command["assembled_pcb"])


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


def validate_observations(observations):
    if not isinstance(observations, list) or not observations:
        raise ValueError("observations must be a non-empty list")
    pose_fields = {"order", "part_id", "source", "target"}
    legacy_gripper_fields = {
        "gripper_grasp_opening_percent",
        "gripper_release_opening_percent",
    }
    validated = []
    for expected_order, observation in enumerate(observations, 1):
        if not isinstance(observation, dict) or set(observation) not in (
            pose_fields, pose_fields | legacy_gripper_fields
        ):
            raise ValueError(
                f"observation {expected_order} must contain order, part_id, "
                "source and target"
            )
        if isinstance(observation["order"], bool) \
                or not isinstance(observation["order"], int) \
                or observation["order"] != expected_order:
            raise ValueError("observation order must be consecutive integers from 1")
        part_id = observation["part_id"]
        if not isinstance(part_id, str) or not part_id.strip():
            raise ValueError(f"observation {expected_order} part_id must be non-empty")
        validated.append({
            "order": expected_order,
            "part_id": part_id,
            "source": validate_ros_pose(
                observation["source"], f"observation {expected_order}.source"
            ),
            "target": validate_ros_pose(
                observation["target"], f"observation {expected_order}.target"
            ),
        })
    return validated


def validate_assembled_pcb(value):
    pose_fields = {"source", "target"}
    legacy_gripper_fields = {
        "gripper_grasp_opening_percent",
        "gripper_release_opening_percent",
    }
    if not isinstance(value, dict) or set(value) not in (
        pose_fields, pose_fields | legacy_gripper_fields
    ):
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


def validate_recipe(recipe, expected_version):
    if not isinstance(recipe, dict):
        raise ValueError("recipe must be a YAML object")
    if recipe.get("recipe_version") != expected_version:
        raise ValueError("recipe_version does not match the start request")
    if recipe.get("frame") != "base_link":
        raise ValueError("recipe frame must be base_link")
    joint_points = recipe.get("joint_points")
    if not isinstance(joint_points, dict) or set(joint_points) != {
        "home", "item_ready", "assembly_ready"
    }:
        raise ValueError(
            "joint_points must contain home, item_ready and assembly_ready"
        )
    for name in ("home", "item_ready", "assembly_ready"):
        validate_joint_point(joint_points[name], f"joint_points.{name}")

    motion = recipe.get("motion")
    if not isinstance(motion, dict) or set(motion) != {
        "approach_dz_mm", "retract_dz_mm",
        "assembled_pcb_drop_approach_dz_mm",
    }:
        raise ValueError(
            "motion must contain approach_dz_mm, retract_dz_mm and "
            "assembled_pcb_drop_approach_dz_mm"
        )
    for name in (
        "approach_dz_mm", "retract_dz_mm",
        "assembled_pcb_drop_approach_dz_mm",
    ):
        if _finite_number(motion[name], f"motion.{name}") <= 0.0:
            raise ValueError(f"motion.{name} must be greater than zero")

    sequence = recipe.get("sequence")
    expected_before_all = ["ensure_camera_calibrated"]
    expected_per_step = [
        "home", "item_ready", "pick", "home", "assembly_ready", "place"
    ]
    expected_after_all = ["transfer_assembled_pcb"]
    if not isinstance(sequence, dict) \
            or sequence.get("before_all") != expected_before_all \
            or sequence.get("per_step") != expected_per_step \
            or sequence.get("after_all") != expected_after_all:
        raise ValueError(
            "sequence must ensure camera calibration, preserve the component cycle "
            "and finish with transfer_assembled_pcb without Home"
        )

    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("recipe steps must be a non-empty list")
    slot_codes = set()
    for expected_order, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise ValueError(f"step {expected_order} must be an object")
        if isinstance(step.get("order"), bool) \
                or not isinstance(step.get("order"), int) \
                or step["order"] != expected_order:
            raise ValueError("step order must be consecutive integers from 1")
        for field in ("part_id", "slot_code"):
            if not isinstance(step.get(field), str) or not step[field].strip():
                raise ValueError(f"step {expected_order} {field} must be non-empty")
        if step["slot_code"] in slot_codes:
            raise ValueError(f"duplicate slot_code: {step['slot_code']}")
        slot_codes.add(step["slot_code"])

    gripper = recipe.get("gripper")
    if not isinstance(gripper, dict) or set(gripper) != {
        "parts", "assembled_pcb"
    }:
        raise ValueError("gripper must contain parts and assembled_pcb")
    part_profiles = gripper["parts"]
    part_ids = {step["part_id"] for step in steps}
    if not isinstance(part_profiles, dict) or set(part_profiles) != part_ids:
        raise ValueError("gripper.parts must contain exactly the recipe part IDs")
    profiles = list(part_profiles.items())
    profiles.append(("assembled_pcb", gripper["assembled_pcb"]))
    for name, profile in profiles:
        if not isinstance(profile, dict) or set(profile) != {
            "grasp_opening_percent", "release_opening_percent"
        }:
            raise ValueError(
                f"gripper.{name} must contain grasp_opening_percent and "
                "release_opening_percent"
            )
        for field, value in profile.items():
            value = _finite_number(value, f"gripper.{name}.{field}")
            if not 0.0 <= value <= 100.0:
                raise ValueError(
                    f"gripper.{name}.{field} must be between 0 and 100"
                )
    return recipe


def load_recipe(path, expected_version):
    recipe_path = Path(path)
    if recipe_path.stem != expected_version:
        raise ValueError("recipe_version does not match the recipe filename")
    with recipe_path.open(encoding="utf-8") as stream:
        recipe = yaml.safe_load(stream)
    return validate_recipe(recipe, expected_version)


def resolve_observations(recipe, observations):
    recipe_steps = recipe["steps"]
    if len(recipe_steps) != len(observations):
        raise ValueError("Unity observation count does not match the recipe")
    resolved = []
    for recipe_step, observation in zip(recipe_steps, observations):
        if recipe_step["order"] != observation["order"]:
            raise ValueError("Unity observation order does not match the recipe")
        if recipe_step["part_id"] != observation["part_id"]:
            raise ValueError(
                f"Unity observation part_id does not match recipe step "
                f"{recipe_step['order']}"
            )
        gripper = recipe["gripper"]["parts"][recipe_step["part_id"]]
        resolved.append({
            "step": recipe_step,
            "gripper_grasp_opening_percent": gripper["grasp_opening_percent"],
            "gripper_release_opening_percent": gripper["release_opening_percent"],
            "source": observation["source"],
            "target": observation["target"],
        })
    return resolved


def vertical_offset(value, dz_mm):
    return {
        "xyz_mm": [value["xyz_mm"][0], value["xyz_mm"][1],
                   value["xyz_mm"][2] + dz_mm],
        "xyzw": list(value["xyzw"]),
    }


def assembly_feedback(request_id, state, step=None, error_code="", message=""):
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
        "request_id": request_id,
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
        "request_id": "",
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
        "request_id": feedback["request_id"],
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
    assert arm_joint_positions(JointState(
        name=list(JOINTS), position=[0.0] * len(JOINTS)
    )) == (0.0,) * len(JOINTS)
    assert arm_joint_positions(JointState(
        name=list(JOINTS[1:]), position=[0.0] * (len(JOINTS) - 1)
    )) is None
    request_id = "12345678-1234-5678-1234-567812345678"
    observations = [{
        "order": 1,
        "part_id": "part",
        "gripper_grasp_opening_percent": 18,
        "gripper_release_opening_percent": 25,
        "source": {"xyz_mm": [350, -150, 250], "xyzw": [0, 0, 0, 1]},
        "target": {"xyz_mm": [350, 150, 250], "xyzw": [0, 0, 0, 1]},
    }]
    assembled_pcb = {
        "gripper_grasp_opening_percent": 0,
        "gripper_release_opening_percent": 100,
        "source": {"xyz_mm": [450, 0, 200], "xyzw": [0, 0, 0, 1]},
        "target": {"xyz_mm": [350, 350, 200], "xyzw": [0, 0, 0, 1]},
    }
    parsed = parse_start_command(json.dumps({
        "command": "start",
        "request_id": request_id,
        "recipe_version": "assembly-r1",
        "observations": observations,
    }))
    assert parsed[:2] == (request_id, "assembly-r1")
    transfer = parse_transfer_command(json.dumps({
        "command": "transfer_assembled_pcb",
        "request_id": request_id,
        "assembled_pcb": assembled_pcb,
    }))
    assert transfer[0] == request_id
    recipe = validate_recipe({
        "recipe_version": "assembly-r1",
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
        "sequence": {
            "before_all": ["ensure_camera_calibrated"],
            "per_step": [
                "home", "item_ready", "pick",
                "home", "assembly_ready", "place",
            ],
            "after_all": ["transfer_assembled_pcb"],
        },
        "gripper": {
            "parts": {
                "part": {
                    "grasp_opening_percent": 20,
                    "release_opening_percent": 30,
                },
            },
            "assembled_pcb": {
                "grasp_opening_percent": 0,
                "release_opening_percent": 100,
            },
        },
        "steps": [{
            "order": 1,
            "part_id": "part",
            "slot_code": "slot-01",
        }],
    }, "assembly-r1")
    resolved = resolve_observations(recipe, parsed[2])
    assert transfer[1]["target"]["xyz_mm"] == [350.0, 350.0, 200.0]
    assert "source" not in recipe["steps"][0]
    assert (
        resolved[0]["gripper_grasp_opening_percent"],
        resolved[0]["gripper_release_opening_percent"],
    ) == (20, 30)
    assert resolved[0]["source"]["xyz_mm"] == [350.0, -150.0, 250.0]
    approach = vertical_offset(
        resolved[0]["source"], recipe["motion"]["approach_dz_mm"]
    )
    assert approach["xyz_mm"] == [350.0, -150.0, 350.0]
    assert resolved[0]["source"]["xyz_mm"] == [350.0, -150.0, 250.0]
    pcb_drop_approach = vertical_offset(
        transfer[1]["target"],
        recipe["motion"]["assembled_pcb_drop_approach_dz_mm"],
    )
    assert pcb_drop_approach["xyz_mm"] == [350.0, 350.0, 350.0]
    feedback = assembly_feedback(request_id, "PICKED", recipe["steps"][0])
    assert feedback["step_order"] == 1 and feedback["part_id"] == "part"
    terminal = assembly_feedback(request_id, "COMPLETED")
    assert terminal["step_order"] == 0 and terminal["slot_code"] == ""
    snapshot = advance_assembly_snapshot(
        empty_assembly_snapshot(),
        assembly_feedback(request_id, "STARTED"),
        "assembly-r1",
        1,
    )
    snapshot = advance_assembly_snapshot(snapshot, feedback, "assembly-r1", 1)
    assert snapshot["active"] and snapshot["held_step_order"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot,
        assembly_feedback(request_id, "PLACED", recipe["steps"][0]),
        "assembly-r1",
        1,
    )
    assert snapshot["placed_count"] == 1 and snapshot["held_step_order"] == 0
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(request_id, "ASSEMBLY_COMPLETED"), "assembly-r1", 1
    )
    assert snapshot["active"] and snapshot["placed_count"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(request_id, "PCB_PICKED"), "assembly-r1", 1
    )
    assert snapshot["active"] and snapshot["placed_count"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(request_id, "PCB_PLACED"), "assembly-r1", 1
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
        assembly_feedback(request_id, "PICKED")
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
        self.execute_client = ActionClient(self, ExecuteTrajectory, "/execute_trajectory")
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
    def start_response(response, accepted, request_id="", error_code="", message=""):
        response.cmd_res = json.dumps({
            "accepted": accepted,
            "request_id": request_id,
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

        if isinstance(command, dict) \
                and command.get("command") == "transfer_assembled_pcb":
            try:
                request_id, assembled_pcb = parse_transfer_command(request.cmd_str)
            except ValueError as error:
                return self.start_response(
                    response, False, error_code="INVALID_REQUEST", message=str(error)
                )
            if self.execution_faulted:
                return self.start_response(
                    response, False, request_id, "FAULTED", FAULT_RESTART_MESSAGE
                )
            job = self.active_assembly
            if job is None or job["request_id"] != request_id:
                return self.start_response(
                    response, False, request_id, "NOT_ACTIVE",
                    "matching assembly is not active",
                )
            if job["phase"] != "awaiting_transfer":
                return self.start_response(
                    response, False, request_id, "BUSY",
                    "assembly is not ready for PCB transfer",
                )
            if self.args.plan_only:
                return self.start_response(
                    response, False, request_id, "PLAN_ONLY",
                    "PCB transfer requires execution mode",
                )
            job["assembled_pcb"] = assembled_pcb
            job["phase"] = "transferring"
            return self.start_response(response, True, request_id)

        try:
            request_id, recipe_version, observations = parse_start_command(
                request.cmd_str
            )
        except ValueError as error:
            return self.start_response(
                response, False, error_code="INVALID_REQUEST", message=str(error)
            )
        if self.execution_faulted:
            return self.start_response(
                response, False, request_id, "FAULTED", FAULT_RESTART_MESSAGE
            )
        if self.active_assembly is not None or self.manual_executing \
                or self.manual_command_pending():
            return self.start_response(
                response, False, request_id, "BUSY", "robot is already executing"
            )
        if self.args.plan_only:
            return self.start_response(
                response, False, request_id, "PLAN_ONLY", "assembly requires execution mode"
            )
        try:
            recipe = load_recipe(self.args.recipe, recipe_version)
            resolved_steps = resolve_observations(recipe, observations)
        except (OSError, ValueError, yaml.YAMLError) as error:
            return self.start_response(
                response, False, request_id, "INVALID_RECIPE", str(error)
            )

        self.active_assembly = {
            "request_id": request_id,
            "recipe": recipe,
            "resolved_steps": resolved_steps,
            "phase": "assembling",
        }
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            assembly_feedback(request_id, "STARTED"),
            recipe_version,
            len(resolved_steps),
        )
        return self.start_response(response, True, request_id)

    def publish_assembly_feedback(
        self, request_id, state, step=None, error_code="", message=""
    ):
        payload = assembly_feedback(request_id, state, step, error_code, message)
        job = self.active_assembly
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            payload,
            job["recipe"]["recipe_version"],
            len(job["resolved_steps"]),
        )
        self.assembly_feedback_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )
        self.get_logger().info(f"assembly {state}: request_id={request_id}")

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
            target = pose_target.pose
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
        if len(points) < 2:
            raise RuntimeError(f"{label} returned fewer than two trajectory points")
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
        self.require_mock_hardware()
        if not self.execute_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("/execute_trajectory is unavailable")

        time.sleep(self.args.preview_seconds)
        self.publish_status("execution: sending trajectory to mock controller")
        future = self.execute_client.send_goal_async(
            ExecuteTrajectory.Goal(trajectory=trajectory)
        )
        handle = self.wait_for_future(future, "trajectory goal acceptance")
        if not handle or not handle.accepted:
            raise RuntimeError("mock controller rejected the trajectory")

        future = handle.get_result_async()
        result = self.wait_for_future(future, "trajectory execution").result
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"mock execution failed: MoveIt code {result.error_code.val}")
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
        future = handle.get_result_async()
        result = self.wait_for_future(future, "gripper execution").result
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
        request_id = job["request_id"]
        recipe = job["recipe"]
        try:
            self.require_mock_hardware()
            self.publish_assembly_feedback(request_id, "STARTED")
            joint_points = recipe["joint_points"]
            motion = recipe["motion"]
            for command in recipe["sequence"]["before_all"]:
                if command != "ensure_camera_calibrated":
                    raise RuntimeError(f"unknown preflight command: {command}")
                self.publish_status("camera calibration: simulated valid (Mock)")
            for resolved in job["resolved_steps"]:
                step = resolved["step"]
                grasp_opening_percent = resolved[
                    "gripper_grasp_opening_percent"
                ]
                release_opening_percent = resolved[
                    "gripper_release_opening_percent"
                ]
                source = self.request_pose(recipe, resolved["source"])
                target = self.request_pose(recipe, resolved["target"])
                source_approach = self.request_pose(
                    recipe,
                    vertical_offset(
                        resolved["source"], motion["approach_dz_mm"]
                    ),
                )
                source_retract = self.request_pose(
                    recipe,
                    vertical_offset(
                        resolved["source"], motion["retract_dz_mm"]
                    ),
                )
                target_approach = self.request_pose(
                    recipe,
                    vertical_offset(
                        resolved["target"], motion["approach_dz_mm"]
                    ),
                )
                target_retract = self.request_pose(
                    recipe,
                    vertical_offset(
                        resolved["target"], motion["retract_dz_mm"]
                    ),
                )

                for command in recipe["sequence"]["per_step"]:
                    if command == "home":
                        self.run_joint_target(joint_points["home"])
                    elif command == "item_ready":
                        self.run_joint_target(joint_points["item_ready"])
                    elif command == "pick":
                        self.run_gripper(release_opening_percent)
                        self.run_ptp_pose(source_approach)
                        self.run_linear(source, True)
                        self.run_gripper(grasp_opening_percent)
                        self.publish_assembly_feedback(request_id, "PICKED", step)
                        self.run_linear(source_retract, True)
                    elif command == "assembly_ready":
                        self.run_joint_target(joint_points["assembly_ready"])
                    elif command == "place":
                        self.run_ptp_pose(target_approach)
                        self.run_linear(target, True)
                        self.run_gripper(release_opening_percent)
                        self.publish_assembly_feedback(request_id, "PLACED", step)
                        self.run_linear(target_retract, True)
                    else:
                        raise RuntimeError(f"unknown assembly command: {command}")

            self.publish_assembly_feedback(request_id, "ASSEMBLY_COMPLETED")
            job["phase"] = "awaiting_transfer"
        except Exception as error:
            self.preview_publisher.publish(JointTrajectory())
            message = str(error)[:512]
            self.publish_status(f"error: assembly failed: {message}")
            try:
                self.publish_assembly_feedback(
                    request_id, "FAILED", error_code="EXECUTION_FAILED",
                    message=message,
                )
            finally:
                self.active_assembly = None

    def run_assembled_pcb_transfer(self, job):
        request_id = job["request_id"]
        recipe = job["recipe"]
        terminal_state = "FAILED"
        error_code = "INTERRUPTED"
        message = "assembled PCB transfer interrupted"
        try:
            self.require_mock_hardware()
            motion = recipe["motion"]
            gripper = recipe["gripper"]["assembled_pcb"]
            for command in recipe["sequence"]["after_all"]:
                if command != "transfer_assembled_pcb":
                    raise RuntimeError(f"unknown final assembly command: {command}")
                transfer = job["assembled_pcb"]
                source = self.request_pose(recipe, transfer["source"])
                target = self.request_pose(recipe, transfer["target"])
                source_approach = self.request_pose(
                    recipe,
                    vertical_offset(
                        transfer["source"], motion["approach_dz_mm"]
                    ),
                )
                source_retract = self.request_pose(
                    recipe,
                    vertical_offset(
                        transfer["source"], motion["retract_dz_mm"]
                    ),
                )
                target_approach = self.request_pose(
                    recipe,
                    vertical_offset(
                        transfer["target"],
                        motion["assembled_pcb_drop_approach_dz_mm"],
                    ),
                )
                target_retract = self.request_pose(
                    recipe,
                    vertical_offset(
                        transfer["target"], motion["retract_dz_mm"]
                    ),
                )
                self.run_gripper(
                    gripper["release_opening_percent"]
                )
                self.run_ptp_pose(source_approach)
                self.run_linear(source, True)
                self.run_gripper(
                    gripper["grasp_opening_percent"]
                )
                self.publish_assembly_feedback(request_id, "PCB_PICKED")
                self.run_linear(source_retract, True)
                self.run_ptp_pose(target_approach)
                self.run_linear(target, True)
                self.run_gripper(
                    gripper["release_opening_percent"]
                )
                self.publish_assembly_feedback(request_id, "PCB_PLACED")
                self.run_linear(target_retract, True)
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
                    request_id, terminal_state, error_code=error_code, message=message
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
    parser.add_argument("--velocity", type=float, default=10.0, choices=range(1, 101))
    parser.add_argument("--acceleration", type=float, default=10.0, choices=range(1, 101))
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
    parser.add_argument(
        "--recipe",
        help="AssemblySequencer-owned Recipe YAML path",
    )
    args = parser.parse_args(argv)
    if not args.listen_unity and args.joints is None and args.pose is None:
        parser.error("one of --joints, --pose or --listen-unity is required")
    if args.listen_unity and not args.recipe:
        parser.error("--recipe is required with --listen-unity")
    if args.preview_seconds < 0.0 or args.max_step <= 0.0 or args.max_joint_step <= 0.0:
        parser.error("preview-seconds must be nonnegative and Cartesian steps positive")
    if args.min_j3_deg < 0.0:
        parser.error("min-j3-deg must be greater than or equal to 0")
    if not all(math.isfinite(value) for value in args.tool_offset):
        parser.error("tool-offset values must be finite")
    return args


def main():
    self_check()
    args = parse_args(rclpy.utilities.remove_ros_args(args=sys.argv)[1:])
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
