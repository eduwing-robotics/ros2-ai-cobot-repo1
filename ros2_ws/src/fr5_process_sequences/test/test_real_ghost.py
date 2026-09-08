import math

from builtin_interfaces.msg import Time
from rclpy.qos import DurabilityPolicy, ReliabilityPolicy
from sensor_msgs.msg import JointState

from fr5_process_sequences.real_ghost import (
    GHOST_JOINT_NAMES,
    GHOST_TARGET_TOPIC,
    RealGhostTargetPublisher,
    joint_degrees_to_radians,
)


class FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


class FakePublisher:
    def __init__(self, fail=False):
        self.messages = []
        self.fail = fail

    def publish(self, message):
        if self.fail:
            raise RuntimeError("transport unavailable")
        self.messages.append(message)


class FakeNow:
    @staticmethod
    def to_msg():
        return Time(sec=123, nanosec=456)


class FakeClock:
    @staticmethod
    def now():
        return FakeNow()


class FakeNode:
    def __init__(self, fail=False):
        self.publisher = FakePublisher(fail=fail)
        self.created = []
        self.logger = FakeLogger()

    def create_publisher(self, message_type, topic, qos):
        self.created.append((message_type, topic, qos))
        return self.publisher

    @staticmethod
    def get_clock():
        return FakeClock()

    def get_logger(self):
        return self.logger


def test_converts_six_joint_degrees_to_radians():
    result = joint_degrees_to_radians((0, 90, -90, 180, -180, 45))
    assert result == (
        0.0,
        math.pi / 2,
        -math.pi / 2,
        math.pi,
        -math.pi,
        math.pi / 4,
    )


def test_real_mode_publishes_joint_state_once():
    node = FakeNode()
    publisher = RealGhostTargetPublisher(node, backend="real")

    assert publisher.publish_joint_target((0, 10, 20, 30, 40, 50)) is True
    assert len(node.publisher.messages) == 1
    message = node.publisher.messages[0]
    assert isinstance(message, JointState)
    assert message.name == list(GHOST_JOINT_NAMES)
    assert list(message.position) == [
        math.radians(value) for value in (0, 10, 20, 30, 40, 50)
    ]
    assert list(message.velocity) == []
    assert list(message.effort) == []
    assert node.created[0][0] is JointState
    assert node.created[0][1] == GHOST_TARGET_TOPIC
    assert node.created[0][2].reliability is ReliabilityPolicy.RELIABLE
    assert node.created[0][2].durability is DurabilityPolicy.VOLATILE


def test_non_real_mode_creates_no_publisher_and_emits_nothing():
    node = FakeNode()
    publisher = RealGhostTargetPublisher(node, backend="simulation")
    assert publisher.enabled is False
    assert publisher.publish_joint_target((0, 0, 0, 0, 0, 0)) is False
    assert node.created == []


def test_invalid_target_and_transport_failure_never_raise():
    node = FakeNode()
    publisher = RealGhostTargetPublisher(node, backend="real")
    assert publisher.publish_joint_target((0, 0, 0)) is False
    assert publisher.publish_joint_target((0, 0, 0, 0, 0, math.nan)) is False

    failing_node = FakeNode(fail=True)
    failing = RealGhostTargetPublisher(failing_node, backend="real")
    assert failing.publish_joint_target((0, 0, 0, 0, 0, 0)) is False
    assert len(node.logger.warnings) == 2
    assert len(failing_node.logger.warnings) == 1
