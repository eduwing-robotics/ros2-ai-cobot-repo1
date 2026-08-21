import rclpy
from rclpy.node import Node

from vision_interfaces.msg import Detections, Part

from .config_utils import default_path, load_yaml


class VisionMock(Node):
    """Publish detector-like results without cameras or a YOLO model."""

    def __init__(self) -> None:
        super().__init__('vision_mock')
        self.declare_parameter('parts_config', default_path('config/parts.yaml'))
        self.declare_parameter('scenario', 'pass')
        self.declare_parameter('camera', 's22')
        self.declare_parameter('rate', 2.0)

        self._catalog = load_yaml(self.get_parameter('parts_config').value)['parts']
        self._scenario = str(self.get_parameter('scenario').value)
        self._camera = str(self.get_parameter('camera').value)
        rate = max(0.2, float(self.get_parameter('rate').value))
        self._publisher = self.create_publisher(
            Detections, '/vision/detections', 10
        )
        self.create_timer(1.0 / rate, self._publish)
        self.get_logger().info(
            f'Mock detections: scenario={self._scenario}, camera={self._camera}'
        )

    def _observations(self):
        observations = []
        for name, settings in self._catalog.items():
            for _ in range(int(settings['expected'])):
                observations.append({'name': name, 'score': 0.95})

        if self._scenario == 'missing_hbm':
            self._remove_one(observations, 'hbm')
        elif self._scenario == 'extra_gpu':
            observations.append({'name': 'gpu', 'score': 0.95})
        elif self._scenario == 'low_score_hbm':
            for item in observations:
                if item['name'] == 'hbm':
                    item['score'] = 0.20
                    break
        elif self._scenario == 'unknown':
            observations.append({'name': 'unknown_part', 'score': 0.95})
        elif self._scenario != 'pass':
            self.get_logger().warning(
                f'Unknown scenario {self._scenario}; publishing PASS data'
            )
        return observations

    @staticmethod
    def _remove_one(observations, name: str) -> None:
        for index, item in enumerate(observations):
            if item['name'] == name:
                observations.pop(index)
                return

    def _publish(self) -> None:
        message = Detections()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = f'{self._camera}_optical_frame'
        message.camera = self._camera
        message.image_width = 640
        message.image_height = 480
        for index, observation in enumerate(self._observations()):
            part = Part()
            part.name = observation['name']
            part.class_id = int(
                self._catalog.get(observation['name'], {}).get('class_id', -1)
            )
            part.score = observation['score']
            part.x = 20 + (index % 8) * 70
            part.y = 20 + (index // 8) * 70
            part.width = 50
            part.height = 50
            part.angle_deg = 0.0
            part.angle_valid = False
            part.depth_m = 0.0
            part.depth_valid = False
            part.camera_x_m = 0.0
            part.camera_y_m = 0.0
            part.camera_z_m = 0.0
            part.position_valid = False
            message.parts.append(part)
        self._publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VisionMock()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
