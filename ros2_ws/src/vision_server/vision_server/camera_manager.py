from functools import partial
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from .config_utils import default_path, load_yaml


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)


class CameraManager(Node):
    """Give physical camera topics stable, easy-to-read vision topic names."""

    def __init__(self) -> None:
        super().__init__('camera_manager')
        self.declare_parameter('config_file', default_path('config/cameras.yaml'))
        config = load_yaml(self.get_parameter('config_file').value)
        self._publishers = []
        self._subscriptions = []
        self._last_relay = {}

        for camera, settings in config.get('cameras', {}).items():
            if not settings.get('enabled', False):
                continue

            source = str(settings['source_topic'])
            output = str(settings['output_topic'])
            transport = str(settings.get('transport', 'compressed'))
            max_fps = max(
                0.1,
                float(settings.get('relay_max_fps', settings.get('max_fps', 30.0))),
            )
            msg_type = CompressedImage if transport == 'compressed' else Image
            publisher = self.create_publisher(msg_type, output, SENSOR_QOS)
            subscription = self.create_subscription(
                msg_type,
                source,
                partial(
                    self._relay,
                    camera=camera,
                    publisher=publisher,
                    minimum_period=1.0 / max_fps,
                ),
                SENSOR_QOS,
            )
            self._publishers.append(publisher)
            self._subscriptions.append(subscription)
            self.get_logger().info(
                f'{camera}: {source} -> {output} | max={max_fps:g} FPS | '
                f'role={settings.get("role", "-")}'
            )

    def _relay(self, message, camera: str, publisher, minimum_period: float) -> None:
        now = time.monotonic()
        if now - self._last_relay.get(camera, 0.0) < minimum_period:
            return
        self._last_relay[camera] = now
        publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CameraManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
