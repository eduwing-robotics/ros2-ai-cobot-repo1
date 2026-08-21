#!/usr/bin/env python3
"""Minimal TWIN MVP bridge: PoseStamped -> MoveIt plan -> mock controller."""

import argparse

import rclpy
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.msg import Constraints, MoveItErrorCodes, OrientationConstraint, PositionConstraint
from moveit_msgs.srv import GetMotionPlan
from rclpy.action import ActionClient
from rclpy.node import Node
from shape_msgs.msg import SolidPrimitive
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory


def make_request(target, group, tip, tolerance, planning_time, speed):
    request = GetMotionPlan.Request()
    motion = request.motion_plan_request
    motion.group_name = group
    motion.num_planning_attempts = 5
    motion.allowed_planning_time = planning_time
    motion.max_velocity_scaling_factor = speed
    motion.max_acceleration_scaling_factor = speed
    motion.start_state.is_diff = True

    region = SolidPrimitive(type=SolidPrimitive.SPHERE, dimensions=[tolerance])
    position = PositionConstraint()
    position.header = target.header
    position.link_name = tip
    position.constraint_region.primitives = [region]
    position.constraint_region.primitive_poses = [
        Pose(position=target.pose.position)]
    position.weight = 1.0

    orientation = OrientationConstraint()
    orientation.header = target.header
    orientation.link_name = tip
    orientation.orientation = target.pose.orientation
    orientation.absolute_x_axis_tolerance = tolerance
    orientation.absolute_y_axis_tolerance = tolerance
    orientation.absolute_z_axis_tolerance = tolerance
    orientation.weight = 1.0

    motion.goal_constraints = [Constraints(
        position_constraints=[position],
        orientation_constraints=[orientation])]
    return request


class TwinMvpMoveItBridge(Node):
    def __init__(self, args):
        super().__init__("twin_mvp_moveit_bridge")
        self.args = args
        self.plan_client = self.create_client(GetMotionPlan, args.plan_service)
        self.controller = ActionClient(
            self, FollowJointTrajectory, args.controller_action)
        self.plan_result = self.create_publisher(
            JointTrajectory, "/twin_mvp/plan_result", 10)
        self.plan_status = self.create_publisher(String, "/twin_mvp/plan_status", 10)
        self.execution_status = self.create_publisher(
            String, "/twin_mvp/execution_status", 10)
        self.create_subscription(
            PoseStamped, "/twin_mvp/plan_request", self.on_plan, 10)
        self.create_subscription(
            JointTrajectory, "/twin_mvp/execution_request", self.on_execute, 10)
        self.planning = False
        self.executing = False

    def publish(self, publisher, value):
        publisher.publish(String(data=value))

    def on_plan(self, target):
        if self.planning:
            self.publish(self.plan_status, "error: planner busy")
            return
        if not self.plan_client.service_is_ready():
            self.publish(self.plan_status, "error: /plan_kinematic_path unavailable")
            return
        self.planning = True
        self.publish(self.plan_status, "planning")
        future = self.plan_client.call_async(make_request(
            target, self.args.group, self.args.tip, self.args.tolerance,
            self.args.planning_time, self.args.speed))
        future.add_done_callback(self.on_plan_done)

    def on_plan_done(self, future):
        self.planning = False
        try:
            response = future.result().motion_plan_response
            if response.error_code.val != MoveItErrorCodes.SUCCESS:
                self.publish(self.plan_status,
                             f"error: MoveIt code {response.error_code.val}")
                return
            trajectory = response.trajectory.joint_trajectory
            if not trajectory.points:
                self.publish(self.plan_status, "error: MoveIt returned no points")
                return
            self.plan_result.publish(trajectory)
            self.publish(self.plan_status, "ready")
        except Exception as error:  # ROS callback boundary
            self.publish(self.plan_status, f"error: {error}")

    def on_execute(self, trajectory):
        if self.executing:
            self.publish(self.execution_status, "error: controller busy")
            return
        if not self.controller.server_is_ready():
            self.publish(self.execution_status, "error: controller unavailable")
            return
        self.executing = True
        self.publish(self.execution_status, "executing")
        goal = FollowJointTrajectory.Goal(trajectory=trajectory)
        self.controller.send_goal_async(goal).add_done_callback(self.on_goal)

    def on_goal(self, future):
        handle = future.result()
        if not handle.accepted:
            self.executing = False
            self.publish(self.execution_status, "error: controller rejected trajectory")
            return
        handle.get_result_async().add_done_callback(self.on_execution_done)

    def on_execution_done(self, future):
        self.executing = False
        try:
            code = future.result().result.error_code
            if code == FollowJointTrajectory.Result.SUCCESSFUL:
                self.publish(self.execution_status, "completed")
            else:
                self.publish(self.execution_status, f"error: controller code {code}")
        except Exception as error:  # ROS callback boundary
            self.publish(self.execution_status, f"error: {error}")


def self_test():
    target = PoseStamped()
    target.header.frame_id = "base_link"
    target.pose.orientation.w = 1.0
    request = make_request(target, "fairino5_v6_group", "wrist3_link", 0.01, 3.0, 0.3)
    motion = request.motion_plan_request
    assert motion.group_name == "fairino5_v6_group"
    assert len(motion.goal_constraints[0].position_constraints) == 1
    assert len(motion.goal_constraints[0].orientation_constraints) == 1
    print("self-test passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", default="fairino5_v6_group")
    parser.add_argument("--tip", default="wrist3_link")
    parser.add_argument("--plan-service", default="/plan_kinematic_path")
    parser.add_argument("--controller-action", default="/fairino5_controller/follow_joint_trajectory")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--planning-time", type=float, default=3.0)
    parser.add_argument("--speed", type=float, default=0.3)
    parser.add_argument("--self-test", action="store_true")
    args, ros_args = parser.parse_known_args()
    if args.self_test:
        self_test()
        return

    rclpy.init(args=ros_args)
    node = TwinMvpMoveItBridge(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
