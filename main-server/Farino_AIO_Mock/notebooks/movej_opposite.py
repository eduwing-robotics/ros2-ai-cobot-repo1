#!/usr/bin/env python3
import math
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from moveit_msgs.action import ExecuteTrajectory, MoveGroup
from moveit_msgs.msg import Constraints, DisplayTrajectory, JointConstraint, MoveItErrorCodes
from sensor_msgs.msg import JointState


class MoveJOpposite(Node):
    def __init__(self):
        super().__init__("movej_opposite_sample")
        self.joint_state = None
        self.create_subscription(JointState, "/joint_states", self.on_joint_state, 1)
        self.move = ActionClient(self, MoveGroup, "/move_action")
        self.execute = ActionClient(self, ExecuteTrajectory, "/execute_trajectory")
        qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.display = self.create_publisher(DisplayTrajectory, "/display_planned_path", qos)

    def on_joint_state(self, message):
        self.joint_state = message

    def target_constraints(self):
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and self.joint_state is None:
            rclpy.spin_once(self, timeout_sec=0.1)
        if self.joint_state is None:
            raise RuntimeError("/joint_states is unavailable")

        current = dict(zip(self.joint_state.name, self.joint_state.position))
        target_j1 = (current["j1"] + 2.0 * math.pi) % (2.0 * math.pi) - math.pi
        target_j1 = max(-3.05, min(3.05, target_j1))
        targets = {name: current[name] for name in ("j1", "j2", "j3", "j4", "j5", "j6")}
        targets["j1"] = target_j1
        return Constraints(joint_constraints=[
            JointConstraint(joint_name=name, position=value, tolerance_above=0.001, tolerance_below=0.001, weight=1.0)
            for name, value in targets.items()
        ])

    def run(self):
        if not self.move.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("/move_action is unavailable")

        goal = MoveGroup.Goal()
        goal.request.group_name = "fairino5_v6_group"
        goal.request.pipeline_id = "pilz_industrial_motion_planner"
        goal.request.planner_id = "PTP"
        goal.request.num_planning_attempts = 1
        goal.request.allowed_planning_time = 5.0
        goal.request.max_velocity_scaling_factor = 0.1
        goal.request.max_acceleration_scaling_factor = 0.1
        goal.request.start_state.is_diff = True
        goal.request.goal_constraints = [self.target_constraints()]
        self.get_logger().info("joint target: " + str([(c.joint_name, c.position) for c in goal.request.goal_constraints[0].joint_constraints]))
        goal.planning_options.plan_only = True

        future = self.move.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle or not handle.accepted:
            raise RuntimeError("PTP planning goal was rejected")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"PTP planning failed: MoveIt code {result.error_code.val}")

        points = result.planned_trajectory.joint_trajectory.points
        if len(points) < 2:
            raise RuntimeError("PTP returned fewer than two trajectory points")
        duration = points[-1].time_from_start.sec + points[-1].time_from_start.nanosec / 1e9
        self.get_logger().info(f"PTP planned: {len(points)} points, {duration:.2f} s")
        self.display.publish(DisplayTrajectory(
            trajectory_start=result.trajectory_start,
            trajectory=[result.planned_trajectory],
        ))
        time.sleep(2.0)

        if not self.execute.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("/execute_trajectory is unavailable")
        future = self.execute.send_goal_async(ExecuteTrajectory.Goal(trajectory=result.planned_trajectory))
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle or not handle.accepted:
            raise RuntimeError("mock controller rejected the trajectory")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        if result.error_code.val != MoveItErrorCodes.SUCCESS:
            raise RuntimeError(f"mock execution failed: MoveIt code {result.error_code.val}")
        self.get_logger().info("Mock PTP execution complete")


def main():
    rclpy.init()
    node = MoveJOpposite()
    try:
        node.run()
    except Exception as error:
        node.get_logger().error(str(error))
        sys.exit(1)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
