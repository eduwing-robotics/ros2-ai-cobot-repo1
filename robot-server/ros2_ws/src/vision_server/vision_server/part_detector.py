import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, CompressedImage, Image

from vision_interfaces.msg import Detections, Part, VisionStatus

from .config_utils import default_path, load_yaml, resolve_package_path
from .depth_utils import deproject_pixel, robust_box_depth
from .detectors.yolo_backend import YoloBackend


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)


class PartDetector(Node):
    def __init__(self) -> None:
        super().__init__('part_detector')
        self.declare_parameter('camera_config', default_path('config/cameras.yaml'))
        self.declare_parameter('yolo_config', default_path('config/yolo.yaml'))

        camera_config = load_yaml(self.get_parameter('camera_config').value)
        yolo_config = load_yaml(self.get_parameter('yolo_config').value)['yolo']

        self._output = self.create_publisher(
            Detections, str(yolo_config['output_topic']), 10
        )
        self._status = self.create_publisher(
            VisionStatus, str(yolo_config['status_topic']), 10
        )
        self._last_frame = {}
        self._last_seen = {}
        self._camera_names = []
        self._required_camera_names = []
        self._subscriptions = []
        self._detector = None
        self._model_message = 'YOLO model is not loaded'
        self._camera_timeout = max(
            0.2, float(yolo_config.get('camera_timeout_sec', 2.0))
        )
        self._inference_count = 0
        self._depth_camera = None
        self._depth_image = None
        self._depth_scale_config = 0.001
        self._depth_image_scale = 1.0
        self._depth_received_at = 0.0
        self._depth_stamp = None
        self._depth_camera_matrix = None
        self._depth_camera_info_size = None
        self._depth_max_age = 0.15
        self._depth_sync_tolerance = 0.10
        self._depth_roi_fraction = 0.35
        self._depth_min_m = 0.02
        self._depth_max_m = 2.0

        try:
            self._detector = YoloBackend(
                model_path=resolve_package_path(str(yolo_config['model_path'])),
                image_size=int(yolo_config['image_size']),
                confidence=float(yolo_config['confidence']),
                iou=float(yolo_config['iou']),
                device=str(yolo_config.get('device', 'auto')),
            )
            self._model_message = 'YOLO model loaded'
            self.get_logger().info(self._model_message)
        except Exception as exc:
            self._model_message = str(exc)
            self.get_logger().warning(self._model_message)

        for camera, settings in camera_config.get('cameras', {}).items():
            if not settings.get('enabled', False) or not settings.get('run_yolo', False):
                continue
            topic = str(settings['output_topic'])
            transport = str(settings.get('transport', 'compressed'))
            max_fps = max(
                0.1,
                float(settings.get('yolo_max_fps', settings.get('max_fps', 5.0))),
            )
            msg_type = CompressedImage if transport == 'compressed' else Image
            subscription = self.create_subscription(
                msg_type,
                topic,
                lambda msg, camera=camera, max_fps=max_fps: self._on_image(
                    msg, camera, max_fps
                ),
                SENSOR_QOS,
            )
            self._subscriptions.append(subscription)
            self._camera_names.append(camera)
            if settings.get('required_for_ready', True):
                self._required_camera_names.append(camera)
            self.get_logger().info(f'YOLO input: {topic} ({camera}, max {max_fps:g} FPS)')

            depth_topic = settings.get('depth_topic')
            camera_info_topic = settings.get('camera_info_topic')
            if depth_topic and camera_info_topic:
                if self._depth_camera is not None:
                    raise RuntimeError('Only one aligned depth camera is currently supported')
                self._depth_camera = camera
                self._depth_scale_config = float(
                    settings.get('depth_scale_m_per_unit', 0.001)
                )
                self._depth_max_age = max(
                    0.01, float(settings.get('depth_max_age_sec', 0.15))
                )
                self._depth_sync_tolerance = max(
                    0.0, float(settings.get('depth_sync_tolerance_sec', 0.10))
                )
                self._depth_roi_fraction = float(
                    settings.get('depth_roi_fraction', 0.35)
                )
                self._depth_min_m = float(settings.get('depth_min_m', 0.02))
                self._depth_max_m = float(settings.get('depth_max_m', 2.0))
                self._subscriptions.append(
                    self.create_subscription(
                        Image, str(depth_topic), self._on_depth, SENSOR_QOS
                    )
                )
                self._subscriptions.append(
                    self.create_subscription(
                        CameraInfo,
                        str(camera_info_topic),
                        self._on_depth_camera_info,
                        SENSOR_QOS,
                    )
                )
                self.get_logger().info(
                    f'Aligned depth: {depth_topic} + {camera_info_topic} ({camera})'
                )

        self.create_timer(2.0, self._publish_status)
        self._publish_status()

    def _publish_status(self) -> None:
        now = time.monotonic()
        active = sorted(
            camera
            for camera in self._camera_names
            if now - self._last_seen.get(camera, 0.0) <= self._camera_timeout
        )
        missing = sorted(
            camera for camera in self._required_camera_names if camera not in active
        )
        message = VisionStatus()
        message.header.stamp = self.get_clock().now().to_msg()
        message.ready = (
            self._detector is not None
            and bool(self._camera_names)
            and not missing
        )
        message.model_loaded = self._detector is not None
        message.cameras = list(self._camera_names)
        message.active_cameras = active
        message.missing_cameras = missing
        message.inference_count = self._inference_count
        details = [self._model_message]
        if missing:
            details.append('missing camera input: ' + ', '.join(missing))
        message.message = '; '.join(details)
        self._status.publish(message)

    def _on_image(self, message, camera: str, max_fps: float) -> None:
        now = time.monotonic()
        self._last_seen[camera] = now
        if now - self._last_frame.get(camera, 0.0) < 1.0 / max_fps:
            return
        self._last_frame[camera] = now
        if self._detector is None:
            return

        image = self._decode(message)
        if image is None:
            self.get_logger().warning(f'Could not decode an image from {camera}')
            return

        try:
            detected = self._detector.detect(image)
        except Exception as exc:  # Keep camera callbacks alive after one inference error.
            self.get_logger().error(f'YOLO inference failed for {camera}: {exc}')
            return

        output = Detections()
        output.header = message.header
        output.camera = camera
        output.image_width = int(image.shape[1])
        output.image_height = int(image.shape[0])
        for item in detected:
            part = Part()
            part.name = item.name
            part.class_id = item.class_id
            part.score = item.score
            part.x = item.x
            part.y = item.y
            part.width = item.width
            part.height = item.height
            part.angle_deg = 0.0 if item.angle_deg is None else item.angle_deg
            part.angle_valid = item.angle_deg is not None
            part.depth_m = 0.0
            part.depth_valid = False
            part.camera_x_m = 0.0
            part.camera_y_m = 0.0
            part.camera_z_m = 0.0
            part.position_valid = False
            self._add_aligned_depth(part, message, image.shape[:2], camera)
            output.parts.append(part)
        self._output.publish(output)
        self._inference_count += 1

    @staticmethod
    def _stamp_seconds(message) -> float:
        stamp = message.header.stamp
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def _on_depth_camera_info(self, message: CameraInfo) -> None:
        self._depth_camera_matrix = np.asarray(message.k, dtype=float).reshape(3, 3)
        self._depth_camera_info_size = (int(message.width), int(message.height))

    def _on_depth(self, message: Image) -> None:
        enc = str(message.encoding).lower()
        if enc in ('16uc1', 'mono16'):
            dtype = np.dtype('>u2' if message.is_bigendian else '<u2')
            scale = self._depth_scale_config
        elif enc == '32fc1':
            dtype = np.dtype('>f4' if message.is_bigendian else '<f4')
            scale = 1.0
        else:
            self.get_logger().warning(f'Unsupported depth encoding: {message.encoding}')
            return
        items_per_row = int(message.step) // dtype.itemsize
        needed = int(message.height) * items_per_row
        values = np.frombuffer(message.data, dtype=dtype, count=needed)
        if values.size != needed or items_per_row < int(message.width):
            self.get_logger().warning('Invalid depth image stride/data length')
            return
        self._depth_image = values.reshape(int(message.height), items_per_row)[
            :, : int(message.width)
        ].copy()
        self._depth_image_scale = scale
        self._depth_received_at = time.monotonic()
        self._depth_stamp = self._stamp_seconds(message)

    def _add_aligned_depth(self, part, color_message, image_shape, camera: str) -> None:
        if camera != self._depth_camera:
            return
        if (
            self._depth_image is None
            or self._depth_camera_matrix is None
            or time.monotonic() - self._depth_received_at > self._depth_max_age
        ):
            return
        height, width = [int(value) for value in image_shape]
        if self._depth_image.shape != (height, width):
            return
        if self._depth_camera_info_size != (width, height):
            return
        color_stamp = self._stamp_seconds(color_message)
        if (
            color_stamp > 0.0
            and self._depth_stamp is not None
            and self._depth_stamp > 0.0
            and abs(color_stamp - self._depth_stamp) > self._depth_sync_tolerance
        ):
            return
        estimate = robust_box_depth(
            self._depth_image,
            (part.x, part.y, part.width, part.height),
            scale_m_per_unit=self._depth_image_scale,
            roi_fraction=self._depth_roi_fraction,
            min_depth_m=self._depth_min_m,
            max_depth_m=self._depth_max_m,
        )
        if estimate is None:
            return
        u, v, depth_m = estimate
        point = deproject_pixel(u, v, depth_m, self._depth_camera_matrix)
        if point is None:
            return
        part.depth_m = depth_m
        part.depth_valid = True
        part.camera_x_m = point.x_m
        part.camera_y_m = point.y_m
        part.camera_z_m = point.z_m
        part.position_valid = True

    @staticmethod
    def _decode(message):
        if isinstance(message, CompressedImage):
            data = np.frombuffer(message.data, dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)

        if not isinstance(message, Image) or message.height == 0 or message.width == 0:
            return None
        channels = 3 if message.encoding in ('bgr8', 'rgb8') else 1
        row = np.frombuffer(message.data, dtype=np.uint8).reshape(message.height, message.step)
        image = row[:, : message.width * channels].reshape(
            message.height, message.width, channels
        )
        if message.encoding == 'rgb8':
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PartDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
