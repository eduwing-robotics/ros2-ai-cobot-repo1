"""Publish final J1..J6 targets for the Unity Real Ghost.

Ghost is visualization-only. It has no robot command path and never waits for
a subscriber or acknowledgement.
"""

from __future__ import annotations

import math
import json
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

    def publish_stage_target(self, joints_deg, *, job_id, operation_id, action, phase, point_name=None, preview_only=False):
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
            message.data = json.dumps({
                "schema": "fr5.ghost_stage_target/v1", "job_id": job_id,
                "operation_id": operation_id, "target_id": f"{operation_id}:{phase}",
                "action": action, "phase": phase, "point_name": point_name,
                "timestamp_ros_ns": stamp.sec * 1000000000 + stamp.nanosec,
                "joint_names": list(GHOST_JOINT_NAMES), "positions_rad": list(radians),
                "positions_deg": list(joints_deg), "visualization_only": True, "preview_only": bool(preview_only),
            }, allow_nan=False)
            self._stage_publisher.publish(message)
        except Exception as error:
            self._warn(f"Ghost stage target was not published: {error}")
            return False
        return self.publish_joint_target(joints_deg)

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
