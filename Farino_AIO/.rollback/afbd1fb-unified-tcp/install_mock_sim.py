#!/usr/bin/env python3
"""AIO MoveJ-like mock command using MoveIt Pilz PTP."""

import argparse
import math
import sys
import time

import rclpy
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
INITIAL_JOINTS_DEG = (0.0, -90.0, 90.0, -90.0, -90.0, 0.0)
GRIPPER_CLOSED_METERS = 0.021


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


def self_check_tool_math():
    identity = (0.0, 0.0, 0.0, 1.0)
    assert rotate_vector(identity, (1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)
    assert quaternion_multiply(identity, identity) == identity
    assert gripper_position(100.0) == 0.0
    assert gripper_position(0.0) == GRIPPER_CLOSED_METERS


class MockMoveJ(Node):
    def __init__(self, args):
        super().__init__("mock_movej")
        self.args = args
        scaling_descriptor = ParameterDescriptor(
            floating_point_range=[
                FloatingPointRange(from_value=0.01, to_value=1.0, step=0.0)
            ]
        )
        self.declare_parameter("mock_topSpeed", 0.7, scaling_descriptor)
        self.declare_parameter("mock_accelerSpeed", 0.7, scaling_descriptor)
        self.joint_state = None
        self.create_subscription(JointState, "/joint_states", self.on_joint_state, 10)
        self.pending_joint_target = None
        self.pending_pose_target = None
        self.pending_gripper_target = None
        if args.listen_unity:
            self.create_subscription(
                JointState, "/unity/joint_target", self.on_joint_target, 10
            )
            self.create_subscription(
                PoseStamped, "/unity/tcp_target",
                lambda message: self.on_pose_target(message, True), 10
            )
            self.create_subscription(
                PoseStamped, "/twin_visual/movel_target",
                lambda message: self.on_pose_target(message, False), 10
            )
            self.create_subscription(
                Float32, "/unity/gripper_target", self.on_gripper_target, 10
            )
        self.move_client = ActionClient(self, MoveGroup, "/move_action")
        self.execute_client = ActionClient(self, ExecuteTrajectory, "/execute_trajectory")
        self.gripper_client = ActionClient(
            self, FollowJointTrajectory,
            "/gripper_controller/follow_joint_trajectory"
        )
        self.cartesian_client = self.create_client(GetCartesianPath, "/compute_cartesian_path")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.display_publisher = self.create_publisher(
            DisplayTrajectory, "/display_planned_path", qos
        )
        self.preview_publisher = self.create_publisher(
            JointTrajectory, "/twin_visual/movel_preview", 10
        )
        self.status_publisher = self.create_publisher(String, "/twin_visual/status", 10)

    def on_joint_state(self, message):
        self.joint_state = message

    def motion_scaling(self):
        return (
            self.get_parameter("mock_topSpeed").value,
            self.get_parameter("mock_accelerSpeed").value,
        )

    def on_gripper_target(self, message):
        if not math.isfinite(message.data) or not 0.0 <= message.data <= 100.0:
            self.publish_status("error: gripper target must be between 0 and 100 percent")
            return
        self.pending_gripper_target = message.data

    def on_joint_target(self, message):
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
        self.pending_pose_target = (message, execute_mock)

    def publish_status(self, value):
        self.status_publisher.publish(String(data=value))
        self.get_logger().info(value)

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

    def make_pose_goal(self):
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

        # 1단계: AIO CARTPoint처럼 입력 Pose를 Tool TCP의 목표로 해석한다.
        target = self.tool_target_to_wrist_target(target)

        region_pose = Pose()
        region_pose.position = target.position
        region_pose.orientation.w = 1.0
        sphere = SolidPrimitive(type=SolidPrimitive.SPHERE, dimensions=[0.001])

        position = PositionConstraint()
        position.header.frame_id = self.args.frame
        position.link_name = self.args.tip
        position.constraint_region = BoundingVolume(
            primitives=[sphere], primitive_poses=[region_pose]
        )
        position.weight = 1.0

        orientation = OrientationConstraint()
        orientation.header.frame_id = self.args.frame
        orientation.link_name = self.args.tip
        orientation.orientation = target.orientation
        orientation.absolute_x_axis_tolerance = 0.01
        orientation.absolute_y_axis_tolerance = 0.01
        orientation.absolute_z_axis_tolerance = 0.01
        orientation.weight = 1.0

        return Constraints(
            position_constraints=[position], orientation_constraints=[orientation]
        )

    def tool_target_to_wrist_target(self, tcp_target):
        """등록 Tool TCP 목표를 MoveIt wrist3_link 목표로 변환한다."""
        x, y, z, rx, ry, rz = self.args.tool_offset
        tool_rotation = quaternion_from_rpy(
            math.radians(rx), math.radians(ry), math.radians(rz)
        )
        tcp_rotation = (
            tcp_target.orientation.x,
            tcp_target.orientation.y,
            tcp_target.orientation.z,
            tcp_target.orientation.w,
        )

        # 2단계: wrist 회전 = 목표 TCP 회전 * 등록 Tool 회전의 역회전.
        wrist_rotation = quaternion_multiply(
            tcp_rotation,
            (-tool_rotation[0], -tool_rotation[1], -tool_rotation[2], tool_rotation[3]),
        )

        # 3단계: Tool 길이를 목표 TCP에서 빼 wrist3_link의 목표 위치를 구한다.
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

    def plan(self):
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
            self.make_joint_goal() if self.args.joints else self.make_pose_goal()
        ]
        goal.planning_options.plan_only = True

        future = self.move_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle or not handle.accepted:
            raise RuntimeError("MoveIt rejected the PTP planning request")

        future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, future)
        result = future.result().result
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

        # 4단계: Unity가 보낸 TCP 목표를 실제 MoveIt tip(wrist3_link) 목표로 바꾼다.
        target.pose = self.tool_target_to_wrist_target(target.pose)

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
        rclpy.spin_until_future_complete(self, future)
        response = future.result()
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

    def execute(self, trajectory):
        node_names = {name for name, _ in self.get_node_names_and_namespaces()}
        if "fakesystem" not in node_names:
            raise RuntimeError("execution blocked: /fakesystem is not running")
        if not self.execute_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("/execute_trajectory is unavailable")

        time.sleep(self.args.preview_seconds)
        self.publish_status("execution: sending trajectory to mock controller")
        future = self.execute_client.send_goal_async(
            ExecuteTrajectory.Goal(trajectory=trajectory)
        )
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle or not handle.accepted:
            raise RuntimeError("mock controller rejected the trajectory")

        future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, future)
        result = future.result().result
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"mock execution failed: MoveIt code {result.error_code.val}")
        rclpy.spin_once(self, timeout_sec=0.2)
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

    def run_linear(self, target, execute_mock):
        self.wait_for_joint_state()
        self.log_joint_state("start")
        trajectory = self.plan_linear(target)
        if self.args.plan_only or not execute_mock:
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
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle or not handle.accepted:
            raise RuntimeError("gripper controller rejected the trajectory")
        future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, future)
        if future.result().result.error_code != FollowJointTrajectory.Result.SUCCESSFUL:
            raise RuntimeError("gripper execution failed")
        self.publish_status("gripper: complete")

    def listen(self):
        self.args.joints = INITIAL_JOINTS_DEG
        self.publish_status("initializing: moving to initial joint pose")
        self.run()
        self.args.joints = None
        self.publish_status("ready: waiting for Unity MoveJ or MoveL target")
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.pending_joint_target is not None:
                self.args.joints = self.pending_joint_target
                self.pending_joint_target = None
                operation = self.run
            elif self.pending_pose_target is not None:
                target, execute_mock = self.pending_pose_target
                self.pending_pose_target = None
                operation = lambda: self.run_linear(target, execute_mock)
            elif self.pending_gripper_target is not None:
                target = self.pending_gripper_target
                self.pending_gripper_target = None
                operation = lambda: self.run_gripper(target)
            else:
                continue
            try:
                operation()
            except Exception as error:
                self.preview_publisher.publish(JointTrajectory())
                self.publish_status(f"error: {error}")


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
        default=(3.3, 0.0, 165.5, 0.0, 0.0, 0.0),
        metavar=("X", "Y", "Z", "RX", "RY", "RZ"),
        help="wrist3_link to Tool TCP offset in mm/degrees",
    )
    parser.add_argument("--preview-seconds", type=float, default=2.0)
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
    if not all(math.isfinite(value) for value in args.tool_offset):
        parser.error("tool-offset values must be finite")
    return args


def main():
    # 5단계: 노드 시작 전에 Tool 변환의 최소 수학 검증을 수행한다.
    self_check_tool_math()
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
