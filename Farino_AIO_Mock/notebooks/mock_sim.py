#!/usr/bin/env python3
"""MoveIt Mock equipment backend for one semantic robot operation at a time."""

import argparse
import copy
import json
import math
import sys
import time
import uuid

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
    "STARTED", "PICKED", "PLACED",
    "PCB_PICKED", "PCB_PLACED", "PAUSED", "COMPLETED", "FAILED",
}
STEP_STATES = {"PICKED", "PLACED"}
ROBOT_ACTIONS = {
    "robot.move_joint", "robot.pick", "robot.place", "robot.transfer",
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


def _uuid(value, label):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError(f"{label} must be a UUID string")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{label} must be a UUID string") from error


def parse_start_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    required = {"command", "job_id", "recipe_version", "expected_step_count"}
    if not isinstance(command, dict) or set(command) != required:
        raise ValueError(
            "command, job_id, recipe_version and expected_step_count are required"
        )
    if command["command"] != "start":
        raise ValueError("command must be start")
    recipe_version = command["recipe_version"]
    if not isinstance(recipe_version, str) or not recipe_version.strip():
        raise ValueError("recipe_version must be a non-empty string")
    expected = command["expected_step_count"]
    if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
        raise ValueError("expected_step_count must be a positive integer")
    return _uuid(command["job_id"], "job_id"), recipe_version, expected


def parse_execute_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    required = {"command", "job_id", "operation_id", "action", "arguments"}
    if not isinstance(command, dict) or set(command) != required:
        raise ValueError(
            "command, job_id, operation_id, action and arguments are required"
        )
    if command["command"] != "execute":
        raise ValueError("command must be execute")
    action = command["action"]
    if action not in ROBOT_ACTIONS:
        raise ValueError(f"unsupported robot action: {action}")
    return {
        "job_id": _uuid(command["job_id"], "job_id"),
        "operation_id": _uuid(command["operation_id"], "operation_id"),
        "action": action,
        "arguments": validate_operation_arguments(action, command["arguments"]),
    }


def parse_pause_command(raw):
    try:
        command = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("cmd_str must be a JSON object") from error
    if not isinstance(command, dict) or set(command) != {"command", "job_id"}:
        raise ValueError("command and job_id are required")
    if command["command"] not in {"pause", "resume"}:
        raise ValueError("command must be pause or resume")
    return command["command"], _uuid(command["job_id"], "job_id")


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _positive_number(value, label):
    value = _finite_number(value, label)
    if value <= 0.0:
        raise ValueError(f"{label} must be greater than zero")
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


def validate_joint_point(value, label):
    if not isinstance(value, list) or len(value) != len(JOINTS):
        raise ValueError(f"{label} must contain six numbers")
    return [
        _finite_number(number, f"{label}[{index}]")
        for index, number in enumerate(value)
    ]


def validate_gripper_profile(profile, label):
    required = {"grasp_opening_percent", "release_opening_percent"}
    if not isinstance(profile, dict) or set(profile) != required:
        raise ValueError(
            f"{label} must contain grasp_opening_percent and "
            "release_opening_percent"
        )
    normalized = {}
    for field, value in profile.items():
        value = _finite_number(value, f"{label}.{field}")
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{label}.{field} must be between 0 and 100")
        normalized[field] = value
    return normalized


def validate_step(step):
    if not isinstance(step, dict) or set(step) != {"order", "part_id", "slot_code"}:
        raise ValueError("step must contain order, part_id and slot_code")
    order = step["order"]
    if isinstance(order, bool) or not isinstance(order, int) or order <= 0:
        raise ValueError("step order must be a positive integer")
    for field in ("part_id", "slot_code"):
        if not isinstance(step[field], str) or not step[field].strip():
            raise ValueError(f"step {field} must be a non-empty string")
    return dict(step)


def validate_operation_arguments(action, value):
    if not isinstance(value, dict):
        raise ValueError("operation arguments must be an object")
    if action == "robot.move_joint":
        if set(value) != {"joint_point"}:
            raise ValueError("robot.move_joint requires joint_point")
        return {"joint_point": validate_joint_point(
            value["joint_point"], "joint_point"
        )}

    if action in {"robot.pick", "robot.place"}:
        pose_name = "source" if action == "robot.pick" else "target"
        required = {
            "step", "frame", pose_name, "approach_dz_mm", "retract_dz_mm",
            "gripper",
        }
        if set(value) != required:
            raise ValueError(f"{action} arguments are invalid")
        if value["frame"] != "base_link":
            raise ValueError(f"{action} frame must be base_link")
        return {
            "step": validate_step(value["step"]),
            "frame": value["frame"],
            pose_name: validate_ros_pose(value[pose_name], pose_name),
            "approach_dz_mm": _positive_number(
                value["approach_dz_mm"], "approach_dz_mm"
            ),
            "retract_dz_mm": _positive_number(
                value["retract_dz_mm"], "retract_dz_mm"
            ),
            "gripper": validate_gripper_profile(value["gripper"], "gripper"),
        }

    required = {
        "frame", "source", "target", "approach_dz_mm", "retract_dz_mm",
        "drop_approach_dz_mm", "gripper",
    }
    if set(value) != required:
        raise ValueError("robot.transfer arguments are invalid")
    if value["frame"] != "base_link":
        raise ValueError("robot.transfer frame must be base_link")
    return {
        "frame": value["frame"],
        "source": validate_ros_pose(value["source"], "source"),
        "target": validate_ros_pose(value["target"], "target"),
        "approach_dz_mm": _positive_number(
            value["approach_dz_mm"], "approach_dz_mm"
        ),
        "retract_dz_mm": _positive_number(
            value["retract_dz_mm"], "retract_dz_mm"
        ),
        "drop_approach_dz_mm": _positive_number(
            value["drop_approach_dz_mm"], "drop_approach_dz_mm"
        ),
        "gripper": validate_gripper_profile(value["gripper"], "gripper"),
    }

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

    job_id = "12345678-1234-5678-1234-567812345678"
    operation_id = "87654321-4321-8765-4321-876543218765"
    source = {"xyz_mm": [350, -150, 250], "xyzw": [0, 0, 0, 1]}
    target = {"xyz_mm": [350, 150, 250], "xyzw": [0, 0, 0, 1]}
    step = {"order": 1, "part_id": "part", "slot_code": "slot-01"}
    gripper = {
        "grasp_opening_percent": 20,
        "release_opening_percent": 30,
    }

    assert parse_start_command(json.dumps({
        "command": "start",
        "job_id": job_id,
        "recipe_version": "assembly-r1",
        "expected_step_count": 1,
    })) == (job_id, "assembly-r1", 1)
    assert parse_pause_command(json.dumps({
        "command": "pause", "job_id": job_id,
    })) == ("pause", job_id)

    def parse_operation(action, arguments):
        return parse_execute_command(json.dumps({
            "command": "execute",
            "job_id": job_id,
            "operation_id": operation_id,
            "action": action,
            "arguments": arguments,
        }))

    joint = parse_operation("robot.move_joint", {
        "joint_point": list(INITIAL_JOINTS_DEG),
    })
    assert joint["arguments"]["joint_point"] == list(INITIAL_JOINTS_DEG)
    pick = parse_operation("robot.pick", {
        "step": step,
        "frame": "base_link",
        "source": source,
        "approach_dz_mm": 100,
        "retract_dz_mm": 120,
        "gripper": gripper,
    })
    assert pick["arguments"]["source"]["xyz_mm"] == [350.0, -150.0, 250.0]
    place = parse_operation("robot.place", {
        "step": step,
        "frame": "base_link",
        "target": target,
        "approach_dz_mm": 100,
        "retract_dz_mm": 120,
        "gripper": gripper,
    })
    assert place["arguments"]["step"] == step
    transfer = parse_operation("robot.transfer", {
        "frame": "base_link",
        "source": source,
        "target": target,
        "approach_dz_mm": 100,
        "retract_dz_mm": 120,
        "drop_approach_dz_mm": 150,
        "gripper": gripper,
    })
    assert transfer["operation_id"] == operation_id
    assert vertical_offset(source, 100)["xyz_mm"] == [350, -150, 350]

    feedback = assembly_feedback(job_id, "PICKED", step)
    assert feedback["step_order"] == 1 and feedback["part_id"] == "part"
    snapshot = advance_assembly_snapshot(
        empty_assembly_snapshot(), assembly_feedback(job_id, "STARTED"),
        "assembly-r1", 1,
    )
    snapshot = advance_assembly_snapshot(snapshot, feedback, "assembly-r1", 1)
    assert snapshot["active"] and snapshot["held_step_order"] == 1
    snapshot = advance_assembly_snapshot(
        snapshot, assembly_feedback(job_id, "PLACED", step), "assembly-r1", 1
    )
    assert snapshot["placed_count"] == 1 and snapshot["held_step_order"] == 0

    tcp_target = Pose()
    tcp_target.orientation.w = 1.0
    wrist_target = MockMoveJ.tool_target_to_wrist_target(
        tcp_target, DEFAULT_TOOL_OFFSET
    )
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

        if isinstance(command, dict) and command.get("command") == "execute":
            try:
                operation = parse_execute_command(request.cmd_str)
            except ValueError as error:
                return self.start_response(
                    response, False, error_code="INVALID_REQUEST", message=str(error)
                )
            job_id = operation["job_id"]
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
                    response, False, job_id, "BUSY", "assembly is paused"
                )
            if job["operation"] is not None:
                return self.start_response(
                    response, False, job_id, "BUSY", "robot is already executing"
                )
            if self.args.plan_only:
                return self.start_response(
                    response, False, job_id, "PLAN_ONLY",
                    "assembly requires execution mode",
                )
            job["operation"] = operation
            return self.start_response(response, True, job_id)

        try:
            job_id, recipe_version, expected_step_count = parse_start_command(
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
            "expected_step_count": expected_step_count,
            "operation": None,
            "pause_requested": False,
            "paused": False,
            "resume_feedback": assembly_feedback(job_id, "STARTED"),
        }
        self.latest_assembly_snapshot = advance_assembly_snapshot(
            self.latest_assembly_snapshot,
            assembly_feedback(job_id, "STARTED"),
            recipe_version,
            expected_step_count,
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
            job["expected_step_count"],
        )
        self.assembly_feedback_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )
        self.get_logger().info(f"assembly {state}: job_id={job_id}")

    def publish_operation_result(self, job, operation, error=None):
        state = "COMPLETED" if error is None else "FAILED"
        payload = assembly_feedback(
            job["job_id"], state,
            error_code="" if error is None else "EXECUTION_FAILED",
            message="" if error is None else str(error)[:512],
        )
        payload["operation_id"] = operation["operation_id"]
        if error is not None or operation["action"] == "robot.transfer":
            self.latest_assembly_snapshot = advance_assembly_snapshot(
                self.latest_assembly_snapshot,
                payload,
                job["recipe_version"],
                job["expected_step_count"],
            )
        self.assembly_feedback_publisher.publish(
            String(data=json.dumps(payload, separators=(",", ":")))
        )
        self.get_logger().info(
            f"{operation['action']} {state}: job_id={job['job_id']}"
        )

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
            job["expected_step_count"],
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

    def request_pose(self, frame, value):
        return self.pose_stamped(frame, value["xyz_mm"], value["xyzw"])

    def run_operation(self, job):
        operation = job["operation"]
        action = operation["action"]
        arguments = operation["arguments"]
        failure = None
        try:
            self.require_mock_hardware()
            self.wait_if_paused(job)
            if action == "robot.move_joint":
                self.run_pauseable(
                    job,
                    lambda: self.run_joint_target(arguments["joint_point"]),
                )
            elif action == "robot.pick":
                source = self.request_pose(arguments["frame"], arguments["source"])
                approach = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["source"], arguments["approach_dz_mm"]
                    ),
                )
                retract = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["source"], arguments["retract_dz_mm"]
                    ),
                )
                gripper = arguments["gripper"]
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(gripper["release_opening_percent"]),
                )
                self.run_pauseable(job, lambda: self.run_ptp_pose(approach))
                self.run_pauseable(job, lambda: self.run_linear(source, True))
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(gripper["grasp_opening_percent"]),
                )
                self.publish_assembly_feedback(
                    job["job_id"], "PICKED", arguments["step"]
                )
                self.run_pauseable(job, lambda: self.run_linear(retract, True))
            elif action == "robot.place":
                target = self.request_pose(arguments["frame"], arguments["target"])
                approach = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["target"], arguments["approach_dz_mm"]
                    ),
                )
                retract = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["target"], arguments["retract_dz_mm"]
                    ),
                )
                self.run_pauseable(job, lambda: self.run_ptp_pose(approach))
                self.run_pauseable(job, lambda: self.run_linear(target, True))
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(
                        arguments["gripper"]["release_opening_percent"]
                    ),
                )
                self.publish_assembly_feedback(
                    job["job_id"], "PLACED", arguments["step"]
                )
                self.run_pauseable(job, lambda: self.run_linear(retract, True))
            elif action == "robot.transfer":
                source = self.request_pose(arguments["frame"], arguments["source"])
                target = self.request_pose(arguments["frame"], arguments["target"])
                source_approach = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["source"], arguments["approach_dz_mm"]
                    ),
                )
                source_retract = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["source"], arguments["retract_dz_mm"]
                    ),
                )
                target_approach = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["target"], arguments["drop_approach_dz_mm"]
                    ),
                )
                target_retract = self.request_pose(
                    arguments["frame"],
                    vertical_offset(
                        arguments["target"], arguments["retract_dz_mm"]
                    ),
                )
                gripper = arguments["gripper"]
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(gripper["release_opening_percent"]),
                )
                self.run_pauseable(job, lambda: self.run_ptp_pose(source_approach))
                self.run_pauseable(job, lambda: self.run_linear(source, True))
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(gripper["grasp_opening_percent"]),
                )
                self.publish_assembly_feedback(job["job_id"], "PCB_PICKED")
                self.run_pauseable(job, lambda: self.run_linear(source_retract, True))
                self.run_pauseable(job, lambda: self.run_ptp_pose(target_approach))
                self.run_pauseable(job, lambda: self.run_linear(target, True))
                self.run_pauseable(
                    job,
                    lambda: self.run_gripper(gripper["release_opening_percent"]),
                )
                self.publish_assembly_feedback(job["job_id"], "PCB_PLACED")
                self.run_pauseable(job, lambda: self.run_linear(target_retract, True))
            else:
                raise RuntimeError(f"unsupported robot action: {action}")
            self.wait_if_paused(job)
        except Exception as error:
            failure = error
            self.preview_publisher.publish(JointTrajectory())
            self.publish_status(f"error: {action} failed: {str(error)[:512]}")
        finally:
            try:
                self.publish_operation_result(job, operation, failure)
            finally:
                if self.active_assembly is job:
                    if failure is not None or action == "robot.transfer":
                        self.active_assembly = None
                    else:
                        job["operation"] = None

    def listen(self):
        self.args.joints = INITIAL_JOINTS_DEG
        self.publish_status("initializing: moving to initial joint pose")
        self.run()
        self.args.joints = None
        self.publish_status("ready: waiting for Unity MoveJ or MoveL target")
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            job = self.active_assembly
            if job is not None and job["pause_requested"]:
                self.wait_if_paused(job)
                continue
            is_assembly = job is not None and job["operation"] is not None
            if is_assembly:
                operation = lambda: self.run_operation(job)
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
