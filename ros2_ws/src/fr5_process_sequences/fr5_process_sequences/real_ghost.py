"""Publish final J1..J6 targets for the Unity Real Ghost.

Ghost is visualization-only. It has no robot command path and never waits for
a subscriber or acknowledgement.
"""

from __future__ import annotations

import math
import json
import copy
import threading
from uuid import uuid4
from std_msgs.msg import String
from typing import Any, Sequence

from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState


GHOST_TARGET_TOPIC = "/real/ghost/target"
GHOST_JOINT_NAMES = ("j1", "j2", "j3", "j4", "j5", "j6")
REAL_BACKEND = "real"


def joint_degrees_to_radians(joints_deg: Sequence[float]) -> tuple[float, ...]:
    """Validate J1..J6 degrees and return the ROS JointState representation."""
    if len(joints_deg) != 6:
        raise ValueError("Real Ghost target must contain J1 through J6")
    values = tuple(float(value) for value in joints_deg)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Real Ghost target contains a non-finite joint")
    return tuple(math.radians(value) for value in values)


class RealGhostTargetPublisher:
    """Best-effort JointState target publisher owned by the Real backend."""

    def __init__(
        self,
        node: Any,
        *,
        backend: str,
        topic: str = GHOST_TARGET_TOPIC,
    ) -> None:
        self._node = node
        self._target_lock = threading.RLock()
        self._target_sequence = 0
        self._instance_id = str(uuid4())
        self._latest_target = None
        self.context_resolver = lambda job_id: {}
        self._enabled = str(backend).strip().lower() == REAL_BACKEND
        self._publisher = None
        self._stage_publisher = None
        if self._enabled:
            qos = QoSProfile(
                depth=1,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE,
            )
            self._publisher = node.create_publisher(JointState, topic, qos)
            self._stage_publisher = node.create_publisher(String,
                "/real/ghost/stage_target", QoSProfile(depth=100,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE))

    def publish_stage_target(self, joints_deg, **context):
        with self._target_lock:
            return self._publish_stage_target(joints_deg, **context)

    def _publish_stage_target(self, joints_deg, *, job_id, operation_id, action, phase, point_name=None, preview_only=False, motion_plan_version=None):
        """Publish a self-contained correlated target plus the legacy JointState."""
        if not self._enabled:
            return False
        try:
            radians = joint_degrees_to_radians(joints_deg)
            if self._stage_publisher is None:
                self._stage_publisher = self._node.create_publisher(String,
                    "/real/ghost/stage_target", QoSProfile(depth=100,
                    reliability=ReliabilityPolicy.RELIABLE,
                    durability=DurabilityPolicy.VOLATILE))
            stamp = self._node.get_clock().now().to_msg()
            message = String()
            with self._target_lock:
                self._target_sequence += 1
                sequence = self._target_sequence
            context = self.context_resolver(job_id)
            payload = {
                "schema": "fr5.ghost_stage_target/v1", "job_id": job_id,
                "operation_id": operation_id,
                "target_id": f"{self._instance_id}:{sequence}",
                "target_sequence": sequence, "stage_id": phase,
                "server_instance_id": self._instance_id, "frame_id": "base_link",
                "target_state": "valid", "execution_id": context.get('execution_id'),
                "plan_sha256": context.get('plan_sha256'),
                "motion_plan_version": motion_plan_version,
                "action": action, "phase": phase, "point_name": point_name,
                "timestamp_ros_ns": stamp.sec * 1000000000 + stamp.nanosec,
                "joint_names": list(GHOST_JOINT_NAMES), "positions_rad": list(radians),
                "positions_deg": list(joints_deg), "visualization_only": True, "preview_only": bool(preview_only),
            }
            message.data = json.dumps(payload, allow_nan=False)
            with self._target_lock:
                self._latest_target = copy.deepcopy(payload)
            self._stage_publisher.publish(message)
        except Exception as error:
            self._warn(f"Ghost stage target was not published: {error}")
            return False
        return self.publish_joint_target(joints_deg)

    def snapshot(self):
        with self._target_lock:
            return copy.deepcopy(self._latest_target)

    def invalidate(self, operation_id, reason):
        """Retain an explicit invalid snapshot; never publish a motion target."""
        with self._target_lock:
            if not self._latest_target or self._latest_target['operation_id'] != operation_id:
                return
            self._target_sequence += 1
            self._latest_target.update(target_state='invalid', invalidation_reason=reason,
                                       target_sequence=self._target_sequence)
            payload = copy.deepcopy(self._latest_target)
        try:
            self._stage_publisher.publish(String(data=json.dumps(payload, allow_nan=False)))
        except Exception as error:
            self._warn(f'Ghost invalidation delivery failed: {error}')

    def resume_target(self, operation_id):
        with self._target_lock:
            target = self._latest_target
            if (not target or target['operation_id'] != operation_id
                    or target.get('invalidation_reason') != 'PAUSE_CONFIRMED'):
                return
            self._target_sequence += 1
            target.update(target_state='valid', target_sequence=self._target_sequence)
            target.pop('invalidation_reason', None)
            try:
                self._stage_publisher.publish(String(data=json.dumps(target, allow_nan=False)))
            except Exception as error:
                self._warn(f'Ghost resume delivery failed: {error}')

    @property
    def enabled(self) -> bool:
        return self._enabled

    def publish_joint_target(self, joints_deg: Sequence[float]) -> bool:
        """Publish one final target without waiting for Ghost feedback."""
        if not self._enabled or self._publisher is None:
            return False
        try:
            message = JointState()
            message.header.stamp = self._node.get_clock().now().to_msg()
            message.header.frame_id = "base_link"
            message.name = list(GHOST_JOINT_NAMES)
            message.position = list(joint_degrees_to_radians(joints_deg))
            self._publisher.publish(message)
            return True
        except Exception as error:
            self._warn(f"Real Ghost target was not published: {error}")
            return False

    def _warn(self, message: str) -> None:
        try:
            self._node.get_logger().warning(message)
        except Exception:
            pass
