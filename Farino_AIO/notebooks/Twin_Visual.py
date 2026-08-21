#!/usr/bin/env python3
"""Unity 목표와 장애물을 MoveIt에서 검증해 MoveL 미리보기 경로를 반환한다.

기본값은 로봇을 움직이지 않는다. --execute-mock 사용 시 Ghost 미리보기 시간 뒤
Fake controller에 같은 경로를 실행한다. 실제 로봇에는 사용하지 않는다.

입력:
  /twin_visual/movel_target       geometry_msgs/PoseStamped
  /twin_visual/obstacles          visualization_msgs/MarkerArray (Unity용)
  /twin_visual/collision_object   moveit_msgs/CollisionObject

출력:
  /twin_visual/movel_preview      trajectory_msgs/JointTrajectory
  /twin_visual/status             std_msgs/String

장애물 좌표는 base_link 같은 ROS planning frame 기준, 길이는 m 단위여야 한다.

사용 예:
  source /opt/ros/jazzy/setup.bash
  source ../install/setup.bash
  python3 notebooks/Twin_Visual.py
  python3 notebooks/Twin_Visual.py --execute-mock
  python3 notebooks/Twin_Visual.py --self-test
"""

import argparse
import math

import rclpy
from control_msgs.action import FollowJointTrajectory
from geometry_msgs.msg import Pose, PoseStamped
from moveit_msgs.msg import CollisionObject, MoveItErrorCodes, PlanningScene
from moveit_msgs.srv import ApplyPlanningScene, GetCartesianPath
from rclpy.action import ActionClient
from rclpy.node import Node
from shape_msgs.msg import SolidPrimitive
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from visualization_msgs.msg import Marker, MarkerArray


TARGET_TOPIC = "/twin_visual/movel_target"
OBSTACLE_TOPIC = "/twin_visual/collision_object"
OBSTACLE_MARKERS_TOPIC = "/twin_visual/obstacles"
PREVIEW_TOPIC = "/twin_visual/movel_preview"
STATUS_TOPIC = "/twin_visual/status"
CARTESIAN_SERVICE = "/compute_cartesian_path"
PLANNING_SCENE_SERVICE = "/apply_planning_scene"
DEFAULT_CONTROLLER_ACTION = "/fairino5_controller/follow_joint_trajectory"


def normalized_pose(message):
    values = (
        message.position.x,
        message.position.y,
        message.position.z,
        message.orientation.x,
        message.orientation.y,
        message.orientation.z,
        message.orientation.w,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("target pose contains NaN or infinity")

    norm = math.sqrt(sum(value * value for value in values[3:]))
    if norm < 1e-9:
        raise ValueError("target orientation quaternion has zero length")

    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = values[:3]
    pose.orientation.x = values[3] / norm
    pose.orientation.y = values[4] / norm
    pose.orientation.z = values[5] / norm
    pose.orientation.w = values[6] / norm
    return pose


def make_cartesian_request(target, args):
    if not target.header.frame_id:
        raise ValueError("target frame_id is required")

    request = GetCartesianPath.Request()
    request.header = target.header
    request.start_state.is_diff = True
    request.group_name = args.group
    request.link_name = args.tip
    request.waypoints = [normalized_pose(target.pose)]
    request.max_step = args.max_step
    request.jump_threshold = 0.0
    request.prismatic_jump_threshold = 0.0
    request.revolute_jump_threshold = args.max_joint_step
    request.avoid_collisions = True
    request.max_velocity_scaling_factor = args.speed
    request.max_acceleration_scaling_factor = args.speed
    return request


def trajectory_error(trajectory, max_joint_step):
    joint_count = len(trajectory.joint_names)
    if joint_count == 0 or not trajectory.points:
        return "MoveIt returned an empty trajectory"

    previous = None
    for index, point in enumerate(trajectory.points):
        if len(point.positions) != joint_count:
            return f"trajectory point {index} has the wrong joint count"
        if not all(math.isfinite(value) for value in point.positions):
            return f"trajectory point {index} contains NaN or infinity"
        if previous is not None:
            jump = max(abs(current - old) for current, old in zip(point.positions, previous))
            if jump > max_joint_step:
                return (
                    f"joint jump {jump:.3f} rad exceeds "
                    f"{max_joint_step:.3f} rad at point {index}"
                )
        previous = point.positions
    return None


def ensure_trajectory_timing(trajectory, fallback_seconds_per_point):
    if trajectory.points:
        duration = trajectory.points[-1].time_from_start
        seconds = duration.sec + duration.nanosec * 1e-9
        if math.isfinite(seconds) and seconds > 0.0:
            return seconds

    for index, point in enumerate(trajectory.points):
        nanoseconds = round(index * fallback_seconds_per_point * 1_000_000_000)
        point.time_from_start.sec = nanoseconds // 1_000_000_000
        point.time_from_start.nanosec = nanoseconds % 1_000_000_000
    return max(
        fallback_seconds_per_point,
        (len(trajectory.points) - 1) * fallback_seconds_per_point,
    )


def obstacle_error(collision_object):
    if not collision_object.id:
        return "collision object id is required"
    if collision_object.operation == CollisionObject.REMOVE:
        return None
    if not collision_object.header.frame_id:
        return f"collision object '{collision_object.id}' frame_id is required"
    if len(collision_object.primitives) != len(collision_object.primitive_poses):
        return f"collision object '{collision_object.id}' primitive/pose count differs"
    if len(collision_object.meshes) != len(collision_object.mesh_poses):
        return f"collision object '{collision_object.id}' mesh/pose count differs"
    if len(collision_object.planes) != len(collision_object.plane_poses):
        return f"collision object '{collision_object.id}' plane/pose count differs"
    if collision_object.operation in (CollisionObject.ADD, CollisionObject.APPEND):
        if not (collision_object.primitives or collision_object.meshes or collision_object.planes):
            return f"collision object '{collision_object.id}' has no geometry"
        for primitive in collision_object.primitives:
            if not primitive.dimensions or not all(
                math.isfinite(value) and value > 0.0 for value in primitive.dimensions
            ):
                return f"collision object '{collision_object.id}' has invalid dimensions"
    return None


def collision_object_from_marker(marker):
    if marker.action == Marker.DELETEALL:
        raise ValueError("DELETEALL is not supported; send one DELETE marker per object")

    collision_object = CollisionObject()
    collision_object.header = marker.header
    collision_object.id = f"{marker.ns or 'unity'}/{marker.id}"
    if marker.action == Marker.DELETE:
        collision_object.operation = CollisionObject.REMOVE
        return collision_object
    if marker.action != Marker.ADD:
        raise ValueError(f"marker '{collision_object.id}' has unsupported action {marker.action}")

    dimensions = (marker.scale.x, marker.scale.y, marker.scale.z)
    if not all(math.isfinite(value) and value > 0.0 for value in dimensions):
        raise ValueError(f"marker '{collision_object.id}' has invalid scale")

    primitive = SolidPrimitive()
    if marker.type == Marker.CUBE:
        primitive.type = SolidPrimitive.BOX
        primitive.dimensions = list(dimensions)
    elif marker.type == Marker.SPHERE:
        primitive.type = SolidPrimitive.SPHERE
        primitive.dimensions = [max(dimensions) * 0.5]
    elif marker.type == Marker.CYLINDER:
        primitive.type = SolidPrimitive.CYLINDER
        primitive.dimensions = [marker.scale.z, max(marker.scale.x, marker.scale.y) * 0.5]
    else:
        raise ValueError(f"marker '{collision_object.id}' has unsupported type {marker.type}")

    identity = Pose()
    identity.orientation.w = 1.0
    collision_object.pose = marker.pose
    collision_object.primitives = [primitive]
    collision_object.primitive_poses = [identity]
    collision_object.operation = CollisionObject.ADD
    return collision_object


class TwinVisual(Node):
    def __init__(self, args):
        super().__init__("twin_visual")
        self.args = args
        self.planning = False
        self.pending_scene_updates = 0
        self.scene_revision = 0
        self.failed_scene_ids = set()
        self.execution_pending = False
        self.executing = False
        self.queued_target = None
        self.pending_trajectory = None
        self.pending_execution_revision = 0
        self.preview_timer = None

        self.cartesian = self.create_client(GetCartesianPath, CARTESIAN_SERVICE)
        self.apply_scene = self.create_client(ApplyPlanningScene, PLANNING_SCENE_SERVICE)
        self.controller = (
            ActionClient(self, FollowJointTrajectory, args.controller_action)
            if args.execute_mock
            else None
        )
        self.preview = self.create_publisher(JointTrajectory, PREVIEW_TOPIC, 10)
        self.status = self.create_publisher(String, STATUS_TOPIC, 10)
        self.create_subscription(PoseStamped, TARGET_TOPIC, self.on_target, 10)
        self.create_subscription(CollisionObject, OBSTACLE_TOPIC, self.on_obstacle, 10)
        self.create_subscription(MarkerArray, OBSTACLE_MARKERS_TOPIC, self.on_markers, 10)

        self.publish_status("ready: waiting for Unity target")
        if args.execute_mock:
            self.get_logger().warning(
                "Mock execution enabled; do not connect this node to real hardware"
            )

    def publish_status(self, value):
        self.status.publish(String(data=value))
        self.get_logger().info(value)

    def reject(self, detail):
        self.preview.publish(JointTrajectory())
        self.publish_status(f"error: {detail}")

    def on_obstacle(self, collision_object):
        if self.execution_pending or self.executing:
            self.reject("cannot change collision objects during mock execution")
            return
        error = obstacle_error(collision_object)
        if error:
            self.reject(error)
            return

        object_id = collision_object.id
        if not self.apply_scene.service_is_ready():
            self.failed_scene_ids.add(object_id)
            self.reject(f"{PLANNING_SCENE_SERVICE} unavailable for '{object_id}'")
            return

        request = ApplyPlanningScene.Request()
        request.scene = PlanningScene()
        request.scene.is_diff = True
        request.scene.world.collision_objects = [collision_object]

        self.pending_scene_updates += 1
        self.publish_status(f"scene: applying '{object_id}'")
        future = self.apply_scene.call_async(request)
        future.add_done_callback(
            lambda completed, requested_id=object_id: self.on_obstacle_done(
                completed, requested_id
            )
        )

    def on_markers(self, marker_array):
        for marker in marker_array.markers:
            try:
                self.on_obstacle(collision_object_from_marker(marker))
            except ValueError as error:
                self.reject(str(error))

    def on_obstacle_done(self, future, object_id):
        self.pending_scene_updates = max(0, self.pending_scene_updates - 1)
        try:
            response = future.result()
            if response is None or not response.success:
                self.failed_scene_ids.add(object_id)
                self.reject(f"MoveIt rejected collision object '{object_id}'")
                return
            self.failed_scene_ids.discard(object_id)
            self.scene_revision += 1
            if self.pending_scene_updates == 0:
                self.publish_status(f"scene: ready revision={self.scene_revision}")
            else:
                self.publish_status(f"scene: applied '{object_id}'")
        except Exception as error:  # ROS callback boundary
            self.failed_scene_ids.add(object_id)
            self.reject(f"failed to apply collision object '{object_id}': {error}")

    def on_target(self, target):
        if self.planning:
            self.reject("Cartesian planner is busy")
            return
        if self.execution_pending or self.executing:
            if self.queued_target is not None:
                self.reject("mock execution target queue is full")
                return
            self.queued_target = target
            self.publish_status("queued: waiting for mock execution")
            return

        self.start_planning(target)

    def start_planning(self, target):
        self.preview.publish(JointTrajectory())
        if self.pending_scene_updates:
            self.reject("collision objects are still being applied")
            return
        if self.failed_scene_ids:
            names = ", ".join(sorted(self.failed_scene_ids))
            self.reject(f"collision objects are not synchronized: {names}")
            return
        if not self.cartesian.service_is_ready():
            self.reject(f"{CARTESIAN_SERVICE} unavailable")
            return
        if self.controller is not None and not self.controller.server_is_ready():
            self.reject(f"{self.args.controller_action} unavailable")
            return

        try:
            request = make_cartesian_request(target, self.args)
        except ValueError as error:
            self.reject(str(error))
            return

        self.planning = True
        revision = self.scene_revision
        self.publish_status("planning")
        future = self.cartesian.call_async(request)
        future.add_done_callback(
            lambda completed, requested_revision=revision: self.on_plan_done(
                completed, requested_revision
            )
        )

    def on_plan_done(self, future, requested_revision):
        self.planning = False
        try:
            response = future.result()
            if response is None:
                self.reject("MoveIt returned no response")
                return
            if self.pending_scene_updates or requested_revision != self.scene_revision:
                self.reject("planning scene changed while the path was being computed")
                return
            if response.error_code.val != MoveItErrorCodes.SUCCESS:
                detail = response.error_code.message.strip()
                suffix = f": {detail}" if detail else ""
                self.reject(f"MoveIt code {response.error_code.val}{suffix}")
                return
            if response.fraction < 1.0 - 1e-6:
                self.reject(f"Cartesian path is only {response.fraction * 100.0:.1f}% complete")
                return

            trajectory = response.solution.joint_trajectory
            error = trajectory_error(trajectory, self.args.max_joint_step)
            if error:
                self.reject(error)
                return

            duration = ensure_trajectory_timing(
                trajectory, self.args.fallback_seconds_per_point
            )
            self.preview.publish(trajectory)
            status = (
                f"ready: fraction=1.000 points={len(trajectory.points)} "
                f"scene_revision={self.scene_revision}"
            )
            if self.controller is None:
                self.publish_status(status)
                return

            self.pending_trajectory = trajectory
            self.pending_execution_revision = self.scene_revision
            self.execution_pending = True
            self.preview_timer = self.create_timer(duration, self.begin_mock_execution)
            self.publish_status(f"{status} mock_execution_in={duration:.3f}s")
        except Exception as error:  # ROS callback boundary
            self.reject(f"Cartesian planning failed: {error}")

    def begin_mock_execution(self):
        self.preview_timer.cancel()
        self.destroy_timer(self.preview_timer)
        self.preview_timer = None
        self.execution_pending = False
        if self.pending_execution_revision != self.scene_revision:
            self.execution_failed("planning scene changed before mock execution")
            return

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = self.pending_trajectory
        self.executing = True
        self.publish_status("execution: sending trajectory to mock controller")
        future = self.controller.send_goal_async(goal)
        future.add_done_callback(self.on_goal_response)

    def on_goal_response(self, future):
        try:
            goal = future.result()
            if goal is None or not goal.accepted:
                self.execution_failed("mock controller rejected the trajectory")
                return
            goal.get_result_async().add_done_callback(self.on_execution_done)
        except Exception as error:  # ROS callback boundary
            self.execution_failed(f"failed to start mock execution: {error}")

    def on_execution_done(self, future):
        try:
            result = future.result().result
            if result.error_code != FollowJointTrajectory.Result.SUCCESSFUL:
                self.execution_failed(
                    f"mock execution failed code={result.error_code}: {result.error_string}"
                )
                return
            self.executing = False
            self.pending_trajectory = None
            self.publish_status("execution: complete")
            if self.queued_target is not None:
                target = self.queued_target
                self.queued_target = None
                self.start_planning(target)
        except Exception as error:  # ROS callback boundary
            self.execution_failed(f"mock execution failed: {error}")

    def execution_failed(self, detail):
        self.execution_pending = False
        self.executing = False
        self.pending_trajectory = None
        self.queued_target = None
        self.reject(detail)


def self_test(args):
    target = PoseStamped()
    target.header.frame_id = "base_link"
    target.pose.position.x = 0.4
    target.pose.orientation.w = 2.0
    request = make_cartesian_request(target, args)
    assert request.group_name == args.group
    assert request.link_name == args.tip
    assert request.avoid_collisions
    assert request.waypoints[0].orientation.w == 1.0

    trajectory = JointTrajectory()
    trajectory.joint_names = [f"j{index}" for index in range(1, 7)]
    first = JointTrajectoryPoint()
    first.positions = [0.0] * 6
    second = JointTrajectoryPoint()
    second.positions = [args.max_joint_step * 0.5] * 6
    trajectory.points = [first, second]
    assert trajectory_error(trajectory, args.max_joint_step) is None
    assert ensure_trajectory_timing(trajectory, 0.05) == 0.05
    assert trajectory.points[1].time_from_start.nanosec == 50_000_000
    second.positions[0] = args.max_joint_step * 2.0
    assert "joint jump" in trajectory_error(trajectory, args.max_joint_step)

    marker = Marker()
    marker.header.frame_id = "base_link"
    marker.ns = "test"
    marker.id = 1
    marker.type = Marker.CUBE
    marker.action = Marker.ADD
    marker.pose.orientation.w = 1.0
    marker.scale.x, marker.scale.y, marker.scale.z = 0.1, 0.2, 0.3
    obstacle = collision_object_from_marker(marker)
    assert obstacle.id == "test/1"
    assert list(obstacle.primitives[0].dimensions) == [0.1, 0.2, 0.3]
    print("Twin_Visual self-test passed")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", default="fairino5_v6_group")
    parser.add_argument("--tip", default="wrist3_link")
    parser.add_argument("--max-step", type=float, default=0.005, help="Cartesian sample step in m")
    parser.add_argument(
        "--max-joint-step",
        type=float,
        default=0.35,
        help="maximum joint change between samples in rad",
    )
    parser.add_argument("--speed", type=float, default=0.1)
    parser.add_argument(
        "--execute-mock",
        action="store_true",
        help="execute each preview on the fake fairino5 controller after Ghost playback",
    )
    parser.add_argument("--controller-action", default=DEFAULT_CONTROLLER_ACTION)
    parser.add_argument("--fallback-seconds-per-point", type=float, default=0.05)
    parser.add_argument("--self-test", action="store_true")
    args, ros_args = parser.parse_known_args()
    if args.max_step <= 0.0:
        parser.error("--max-step must be greater than zero")
    if args.max_joint_step <= 0.0:
        parser.error("--max-joint-step must be greater than zero")
    if not 0.0 < args.speed <= 1.0:
        parser.error("--speed must be in (0, 1]")
    if args.fallback_seconds_per_point <= 0.0:
        parser.error("--fallback-seconds-per-point must be greater than zero")
    return args, ros_args


def main():
    args, ros_args = parse_args()
    if args.self_test:
        self_test(args)
        return

    rclpy.init(args=ros_args)
    node = TwinVisual(args)
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
