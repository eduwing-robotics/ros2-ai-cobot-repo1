"""Convert S22 board polygons to fixed FR5 Base-plane poses; no motion."""

import json
import math
import os
from pathlib import Path
import time

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PolygonStamped, PoseStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String

from .config_utils import default_path, load_yaml
from .s22_homography import polygon_base_pose


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)


def resolve_project_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    project_root = Path(os.environ.get('KSMC_ROOT', Path.home() / 'KSMC'))
    return project_root / path


class S22BoardLocalizer(Node):
    def __init__(self):
        super().__init__('s22_board_localizer')
        config = load_yaml(default_path('s22_board_localizer.yaml'))[
            's22_board_localizer'
        ]
        calibration_path = resolve_project_path(config['calibration_file'])
        calibration = json.loads(calibration_path.read_text(encoding='utf-8'))
        quality = calibration.get('quality', {})
        if config.get('require_quality_pass', True) and not quality.get(
            'passed', False
        ):
            raise RuntimeError(
                f'S22 plane calibration did not pass quality checks: '
                f'{calibration_path}'
            )
        self.image_to_base_mm = np.asarray(
            calibration['homography_normalized_image_to_base_mm'], dtype=float
        ).reshape(3, 3)
        self.plane_z_mm = float(calibration['plane_z_mm'])
        self.coverage_hull = np.asarray(
            calibration['coverage_hull_normalized'], dtype=np.float32
        ).reshape(-1, 2)
        self.coverage_margin = float(
            config.get('coverage_margin_normalized', 0.01)
        )
        self.base_frame = str(config.get('base_frame', 'base'))
        self.timeout_sec = float(config.get('detection_timeout_sec', 0.75))
        self.expected_long_mm = float(config.get('board_long_mm', 139.0))
        self.expected_short_mm = float(config.get('board_short_mm', 110.0))
        self.max_size_error_mm = float(config.get('max_size_error_mm', 30.0))
        self.last_seen = {}
        self.publishers = {}
        self.subscriptions = []
        stations = config.get('stations', ['assembly', 'inspection'])
        for station in stations:
            prefix = f'/vision/board/{station}'
            self.publishers[station] = {
                'pose': self.create_publisher(PoseStamped, f'{prefix}_pose', 1),
                'position_valid': self.create_publisher(
                    Bool, f'{prefix}_position_valid', 1
                ),
                'heading_valid': self.create_publisher(
                    Bool, f'{prefix}_heading_valid', 1
                ),
                'status': self.create_publisher(String, f'{prefix}_status', 1),
            }
            topic = f'/vision/conveyor/{station}/board_polygon_normalized'
            self.subscriptions.append(self.create_subscription(
                PolygonStamped,
                topic,
                lambda message, name=station: self.polygon_cb(name, message),
                SENSOR_QOS,
            ))
            self.last_seen[station] = 0.0
        self.create_timer(0.25, self.timeout_cb)
        self.get_logger().info(
            'NO MOTION S22 localizer: normalized image -> FR5 Base XY; '
            f'calibration={calibration_path}, plane Z={self.plane_z_mm:.3f} mm'
        )
        self.get_logger().warning(
            'Board yaw is modulo 180 degrees until the fixture handle/board '
            'direction resolver is validated; heading_valid remains false'
        )

    def polygon_cb(self, station: str, message: PolygonStamped):
        points = np.asarray(
            [[point.x, point.y] for point in message.polygon.points], dtype=float
        )
        publishers = self.publishers[station]
        try:
            _, center_mm, yaw, long_mm, short_mm = polygon_base_pose(
                points, self.image_to_base_mm
            )
        except (ValueError, cv2.error) as error:
            publishers['position_valid'].publish(Bool(data=False))
            publishers['heading_valid'].publish(Bool(data=False))
            publishers['status'].publish(String(data=json.dumps({
                'station': station, 'valid': False, 'reason': str(error)
            })))
            return

        size_error_mm = max(
            abs(long_mm - self.expected_long_mm),
            abs(short_mm - self.expected_short_mm),
        )
        center_normalized = np.mean(points, axis=0)
        coverage_distance = float(cv2.pointPolygonTest(
            self.coverage_hull,
            (float(center_normalized[0]), float(center_normalized[1])),
            True,
        ))
        inside_calibrated_area = coverage_distance >= -self.coverage_margin
        position_valid = bool(
            np.all(np.isfinite(center_mm))
            and size_error_mm <= self.max_size_error_mm
            and inside_calibrated_area
        )
        pose = PoseStamped()
        pose.header.stamp = message.header.stamp
        pose.header.frame_id = self.base_frame
        pose.pose.position.x = float(center_mm[0] / 1000.0)
        pose.pose.position.y = float(center_mm[1] / 1000.0)
        pose.pose.position.z = float(self.plane_z_mm / 1000.0)
        pose.pose.orientation.z = math.sin(yaw * 0.5)
        pose.pose.orientation.w = math.cos(yaw * 0.5)
        publishers['pose'].publish(pose)
        publishers['position_valid'].publish(Bool(data=position_valid))
        publishers['heading_valid'].publish(Bool(data=False))
        status = {
            'station': station,
            'position_valid': position_valid,
            'heading_valid': False,
            'heading_definition': 'board_long_axis_modulo_180_degrees',
            'base_center_mm': [
                float(center_mm[0]), float(center_mm[1]), self.plane_z_mm
            ],
            'yaw_mod_180_deg': math.degrees(yaw),
            'measured_size_mm': [long_mm, short_mm],
            'size_error_mm': size_error_mm,
            'inside_calibrated_area': inside_calibrated_area,
            'coverage_distance_normalized': coverage_distance,
            'transform': 'H_baseXY_from_S22_normalized_image',
        }
        publishers['status'].publish(
            String(data=json.dumps(status, separators=(',', ':')))
        )
        self.last_seen[station] = time.monotonic()

    def timeout_cb(self):
        now = time.monotonic()
        for station, last_seen in self.last_seen.items():
            if last_seen and now - last_seen <= self.timeout_sec:
                continue
            publishers = self.publishers[station]
            publishers['position_valid'].publish(Bool(data=False))
            publishers['heading_valid'].publish(Bool(data=False))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = S22BoardLocalizer()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
