"""ROS 2 Action endpoints consumed by the Real Orchestrator and Unity.

The node only validates and converts Vision observations. It never commands the
robot or conveyor; Home and AssemblyReadyPoint remain orchestrator preconditions.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import rclpy
from geometry_msgs.msg import Pose
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String

from vision_interfaces.action import CalibratePcbPose, DetectTrayParts

from .config_utils import default_path, load_yaml
from .orchestration_contract import (
    ContractFailure,
    PcbSnapshot,
    TraySnapshot,
    pcb_snapshot,
    tray_snapshot,
)


class OrchestrationActionServer(Node):
    def __init__(self) -> None:
        super().__init__("vision_orchestration_action_server")
        self.declare_parameter(
            "contract_config", default_path("config/orchestration_api.yaml")
        )
        config_path = str(self.get_parameter("contract_config").value)
        root = load_yaml(config_path).get("orchestration_api", {})
        if not isinstance(root, dict):
            raise RuntimeError("orchestration_api configuration is missing")
        self.config = root
        self.timeout_sec = float(root.get("detection_timeout_sec", 5.0))
        self.maximum_age_sec = float(root.get("source_max_age_sec", 2.5))
        self.tray_config = root["tray"]
        self.pcb_config = root["pcb"]
        topics = root["topics"]
        endpoints = root["endpoints"]

        self._lock = threading.Lock()
        self._tray_payload: dict[str, Any] | None = None
        self._pcb_payload: dict[str, Any] | None = None
        self._tray_parse_error: str | None = None
        self._pcb_parse_error: str | None = None
        self._conveyor_stopped: bool | None = None

        callback_group = ReentrantCallbackGroup()
        self.create_subscription(
            String,
            str(topics["tray_state"]),
            self._tray_callback,
            10,
            callback_group=callback_group,
        )
        self.create_subscription(
            String,
            str(topics["pcb_state"]),
            self._pcb_callback,
            10,
            callback_group=callback_group,
        )
        stopped_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            Bool,
            str(topics["conveyor_stopped"]),
            self._conveyor_callback,
            stopped_qos,
            callback_group=callback_group,
        )

        self._tray_server = ActionServer(
            self,
            DetectTrayParts,
            str(endpoints["detect_tray_parts"]),
            execute_callback=self._execute_tray,
            goal_callback=self._accept_goal,
            cancel_callback=self._accept_cancel,
            callback_group=callback_group,
        )
        self._pcb_server = ActionServer(
            self,
            CalibratePcbPose,
            str(endpoints["calibrate_pcb_pose"]),
            execute_callback=self._execute_pcb,
            goal_callback=self._accept_goal,
            cancel_callback=self._accept_cancel,
            callback_group=callback_group,
        )
        self.get_logger().info(
            "Vision orchestration Actions ready; this node sends no robot or "
            "conveyor motion commands"
        )

    @staticmethod
    def _accept_goal(_goal_request) -> GoalResponse:
        # Malformed content is returned as an explicit Action result rather than
        # silently rejected, so clients receive error_code and message.
        return GoalResponse.ACCEPT

    @staticmethod
    def _accept_cancel(_goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    def _json_callback(self, message: String, kind: str) -> None:
        try:
            payload = json.loads(message.data)
            if not isinstance(payload, dict):
                raise ValueError("top-level JSON is not an object")
        except (json.JSONDecodeError, ValueError) as exc:
            with self._lock:
                if kind == "tray":
                    self._tray_parse_error = str(exc)
                else:
                    self._pcb_parse_error = str(exc)
            return
        with self._lock:
            if kind == "tray":
                self._tray_payload = payload
                self._tray_parse_error = None
            else:
                self._pcb_payload = payload
                self._pcb_parse_error = None

    def _tray_callback(self, message: String) -> None:
        self._json_callback(message, "tray")

    def _pcb_callback(self, message: String) -> None:
        self._json_callback(message, "pcb")

    def _conveyor_callback(self, message: Bool) -> None:
        with self._lock:
            self._conveyor_stopped = bool(message.data)

    def _latest(self, kind: str):
        with self._lock:
            if kind == "tray":
                return self._tray_payload, self._tray_parse_error
            return self._pcb_payload, self._pcb_parse_error

    @staticmethod
    def _assign_stamp(header, stamp_ns: int) -> None:
        header.stamp.sec = int(stamp_ns // 1_000_000_000)
        header.stamp.nanosec = int(stamp_ns % 1_000_000_000)
        header.frame_id = "base_link"

    @staticmethod
    def _pose_message(value) -> Pose:
        pose = Pose()
        pose.position.x, pose.position.y, pose.position.z = value.position_m
        (
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        ) = value.orientation_xyzw
        return pose

    @staticmethod
    def _tray_failure(goal_handle, failure: ContractFailure, cancelled=False):
        result = DetectTrayParts.Result()
        result.success = False
        result.error_code = failure.code
        result.message = failure.message
        if cancelled:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return result

    @staticmethod
    def _pcb_failure(goal_handle, failure: ContractFailure, cancelled=False):
        result = CalibratePcbPose.Result()
        result.success = False
        result.error_code = failure.code
        result.message = failure.message
        result.pcb_pose.header.frame_id = "base_link"
        if cancelled:
            goal_handle.canceled()
        else:
            goal_handle.abort()
        return result

    def _execute_tray(self, goal_handle):
        job_id = str(goal_handle.request.job_id).strip()
        if not job_id:
            return self._tray_failure(
                goal_handle,
                ContractFailure("INVALID_REQUEST", "job_id is required"),
            )

        deadline = time.monotonic() + self.timeout_sec
        next_feedback = 0.0
        last_failure = ContractFailure(
            "CAMERA_NOT_READY", "no tray Vision result has been received"
        )
        while rclpy.ok() and time.monotonic() < deadline:
            if goal_handle.is_cancel_requested:
                return self._tray_failure(
                    goal_handle,
                    ContractFailure("CANCELLED", "tray detection was cancelled"),
                    cancelled=True,
                )
            payload, parse_error = self._latest("tray")
            now = time.monotonic()
            if now >= next_feedback:
                feedback = DetectTrayParts.Feedback()
                feedback.stage = "WAITING_FOR_STABLE_TRAY"
                if isinstance(payload, dict) and isinstance(payload.get("parts"), list):
                    feedback.detected_count = len(payload["parts"])
                goal_handle.publish_feedback(feedback)
                next_feedback = now + 0.5

            if parse_error:
                last_failure = ContractFailure(
                    "CAMERA_NOT_READY", f"invalid tray JSON: {parse_error}"
                )
            elif payload is not None:
                try:
                    snapshot = tray_snapshot(
                        payload,
                        self.tray_config["part_mappings"],
                        now_ns=self.get_clock().now().nanoseconds,
                        maximum_age_sec=self.maximum_age_sec,
                        minimum_observation_frames=int(
                            self.tray_config.get("minimum_observation_frames", 5)
                        ),
                    )
                except ContractFailure as failure:
                    last_failure = failure
                    if failure.code in (
                        "UNKNOWN_PART",
                        "FRAME_TRANSFORM_FAILED",
                        "CALIBRATION_NOT_READY",
                    ):
                        return self._tray_failure(goal_handle, failure)
                else:
                    return self._complete_tray(goal_handle, job_id, snapshot)
            time.sleep(0.05)

        if last_failure.code == "CAMERA_NOT_READY" and self._latest("tray")[0] is not None:
            last_failure = ContractFailure(
                "DETECTION_TIMEOUT", "tray detection did not become ready before timeout"
            )
        return self._tray_failure(goal_handle, last_failure)

    def _complete_tray(
        self, goal_handle, job_id: str, snapshot: TraySnapshot
    ):
        result = DetectTrayParts.Result()
        result.success = True
        self._assign_stamp(result.header, snapshot.stamp_ns)
        result.part_ids = list(snapshot.part_ids)
        result.part_poses = [
            self._pose_message(pose) for pose in snapshot.poses
        ]
        result.error_code = ""
        result.message = (
            f"job {job_id}: {len(snapshot.part_ids)} stable tray parts"
        )
        feedback = DetectTrayParts.Feedback()
        feedback.stage = "COMPLETED"
        feedback.detected_count = len(snapshot.part_ids)
        goal_handle.publish_feedback(feedback)
        goal_handle.succeed()
        return result

    def _execute_pcb(self, goal_handle):
        request = goal_handle.request
        job_id = str(request.job_id).strip()
        if not job_id:
            return self._pcb_failure(
                goal_handle,
                ContractFailure("INVALID_REQUEST", "job_id is required"),
            )

        if bool(self.pcb_config.get("require_conveyor_stopped", True)):
            with self._lock:
                stopped = self._conveyor_stopped
            if stopped is not True:
                return self._pcb_failure(
                    goal_handle,
                    ContractFailure(
                        "CONVEYOR_NOT_STOPPED",
                        "Real Orchestrator has not asserted conveyor_stopped=true",
                    ),
                )

        deadline = time.monotonic() + self.timeout_sec
        next_feedback = 0.0
        last_failure = ContractFailure(
            "CAMERA_NOT_READY", "no PCB Vision result has been received"
        )
        while rclpy.ok() and time.monotonic() < deadline:
            if goal_handle.is_cancel_requested:
                return self._pcb_failure(
                    goal_handle,
                    ContractFailure("CANCELLED", "PCB calibration was cancelled"),
                    cancelled=True,
                )
            if bool(self.pcb_config.get("require_conveyor_stopped", True)):
                with self._lock:
                    stopped = self._conveyor_stopped
                if stopped is not True:
                    return self._pcb_failure(
                        goal_handle,
                        ContractFailure(
                            "CONVEYOR_NOT_STOPPED",
                            "conveyor stopped state was cleared during calibration",
                        ),
                    )

            now = time.monotonic()
            if now >= next_feedback:
                feedback = CalibratePcbPose.Feedback()
                feedback.stage = "WAITING_FOR_STABLE_PCB_POSE"
                goal_handle.publish_feedback(feedback)
                next_feedback = now + 0.5
            payload, parse_error = self._latest("pcb")
            if parse_error:
                last_failure = ContractFailure(
                    "CAMERA_NOT_READY", f"invalid PCB JSON: {parse_error}"
                )
            elif payload is not None:
                try:
                    snapshot = pcb_snapshot(
                        payload,
                        requested_product_code=str(request.product_code).strip(),
                        requested_product_version=str(request.product_version).strip(),
                        expected_product_code=str(
                            self.pcb_config["expected_product_code"]
                        ),
                        expected_product_version=str(
                            self.pcb_config["expected_product_version"]
                        ),
                        now_ns=self.get_clock().now().nanoseconds,
                        maximum_age_sec=self.maximum_age_sec,
                        maximum_hole_fit_rms_mm=float(
                            self.pcb_config["maximum_hole_fit_rms_mm"]
                        ),
                        maximum_plane_mad_mm=float(
                            self.pcb_config["maximum_plane_mad_mm"]
                        ),
                        minimum_plane_inliers=int(
                            self.pcb_config["minimum_plane_inliers"]
                        ),
                    )
                except ContractFailure as failure:
                    last_failure = failure
                    if failure.code in (
                        "WRONG_PCB",
                        "FRAME_TRANSFORM_FAILED",
                        "CALIBRATION_NOT_READY",
                        "INVALID_REQUEST",
                    ):
                        return self._pcb_failure(goal_handle, failure)
                else:
                    return self._complete_pcb(goal_handle, job_id, snapshot)
            time.sleep(0.05)
        return self._pcb_failure(goal_handle, last_failure)

    def _complete_pcb(
        self, goal_handle, job_id: str, snapshot: PcbSnapshot
    ):
        result = CalibratePcbPose.Result()
        result.success = True
        self._assign_stamp(result.pcb_pose.header, snapshot.stamp_ns)
        result.pcb_pose.pose = self._pose_message(snapshot.pose)
        result.error_code = ""
        result.message = f"job {job_id}: stable absolute PCB pose"
        feedback = CalibratePcbPose.Feedback()
        feedback.stage = "COMPLETED"
        goal_handle.publish_feedback(feedback)
        goal_handle.succeed()
        return result

    def destroy_node(self):
        self._tray_server.destroy()
        self._pcb_server.destroy()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OrchestrationActionServer()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
