from dataclasses import dataclass

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, Float32

from .config_utils import default_path, load_yaml


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)


@dataclass(frozen=True)
class NormalizedLine:
    axis: str
    position: float
    span_start: float
    span_end: float


@dataclass(frozen=True)
class BoardDetection:
    points: np.ndarray
    trailing_edge_px: float
    area_fraction: float
    aspect_ratio: float
    rectangularity: float


def normalized_line_to_pixels(
    line: NormalizedLine, image_width: int, image_height: int
):
    if image_width <= 0 or image_height <= 0:
        raise ValueError('image dimensions must be positive')
    if line.axis not in ('x', 'y'):
        raise ValueError("line axis must be 'x' or 'y'")

    position = float(np.clip(line.position, 0.0, 1.0))
    span_start = float(np.clip(line.span_start, 0.0, 1.0))
    span_end = float(np.clip(line.span_end, 0.0, 1.0))
    if span_end <= span_start:
        raise ValueError('line span_end must be greater than span_start')

    if line.axis == 'x':
        x = int(round(position * (image_width - 1)))
        y1 = int(round(span_start * (image_height - 1)))
        y2 = int(round(span_end * (image_height - 1)))
        return (x, y1), (x, y2)

    y = int(round(position * (image_height - 1)))
    x1 = int(round(span_start * (image_width - 1)))
    x2 = int(round(span_end * (image_width - 1)))
    return (x1, y), (x2, y)


def detect_dark_board(
    image,
    *,
    search_bounds,
    dark_threshold: int,
    close_kernel_px: int,
    min_area_fraction: float,
    max_area_fraction: float,
    min_aspect_ratio: float,
    max_aspect_ratio: float,
    min_rectangularity: float,
    travel_direction: str,
):
    height, width = image.shape[:2]
    x1 = int(round(np.clip(search_bounds[0], 0.0, 1.0) * width))
    x2 = int(round(np.clip(search_bounds[1], 0.0, 1.0) * width))
    y1 = int(round(np.clip(search_bounds[2], 0.0, 1.0) * height))
    y2 = int(round(np.clip(search_bounds[3], 0.0, 1.0) * height))
    if x2 <= x1 or y2 <= y1:
        raise ValueError('invalid board search bounds')

    crop = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)[1]
    kernel_size = max(3, int(close_kernel_px) | 1)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (kernel_size, kernel_size)
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    image_area = float(width * height)
    candidates = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        area_fraction = area / image_area
        if not min_area_fraction <= area_fraction <= max_area_fraction:
            continue

        center, dimensions, angle = cv2.minAreaRect(contour)
        rect_width, rect_height = dimensions
        if min(rect_width, rect_height) <= 1.0:
            continue
        aspect_ratio = max(rect_width, rect_height) / min(rect_width, rect_height)
        if not min_aspect_ratio <= aspect_ratio <= max_aspect_ratio:
            continue
        rectangularity = area / max(rect_width * rect_height, 1.0)
        if rectangularity < min_rectangularity:
            continue

        translated_center = (center[0] + x1, center[1] + y1)
        points = cv2.boxPoints((translated_center, dimensions, angle))
        if travel_direction == 'positive_x':
            trailing_edge = float(np.min(points[:, 0]))
        elif travel_direction == 'negative_x':
            trailing_edge = float(np.max(points[:, 0]))
        else:
            raise ValueError('travel_direction must be positive_x or negative_x')
        candidates.append(
            BoardDetection(
                points=points,
                trailing_edge_px=trailing_edge,
                area_fraction=area_fraction,
                aspect_ratio=aspect_ratio,
                rectangularity=rectangularity,
            )
        )

    if not candidates:
        return None
    return max(candidates, key=lambda item: item.area_fraction)


class ConveyorStopLine(Node):
    def __init__(self) -> None:
        super().__init__('conveyor_stop_line')
        self.declare_parameter('config_file', default_path('config/conveyor_roi.yaml'))
        config = load_yaml(self.get_parameter('config_file').value).get(
            'conveyor_roi', {}
        )

        line_config = config.get('stop_line', {})
        self._stop_line = NormalizedLine(
            axis=str(line_config.get('axis', 'x')).lower(),
            position=float(line_config.get('position', 0.70)),
            span_start=float(line_config.get('span_start', 0.18)),
            span_end=float(line_config.get('span_end', 0.82)),
        )
        if self._stop_line.axis not in ('x', 'y'):
            raise ValueError("stop_line.axis must be 'x' or 'y'")

        detector = config.get('board_detection', {})
        self._travel_direction = str(
            detector.get('travel_direction', 'positive_x')
        )
        self._search_bounds = (
            float(detector.get('search_x_start', 0.30)),
            float(detector.get('search_x_end', 0.84)),
            float(detector.get('search_y_start', 0.30)),
            float(detector.get('search_y_end', 0.84)),
        )
        self._detector_settings = {
            'dark_threshold': int(detector.get('dark_threshold', 105)),
            'close_kernel_px': int(detector.get('close_kernel_px', 13)),
            'min_area_fraction': float(detector.get('min_area_fraction', 0.05)),
            'max_area_fraction': float(detector.get('max_area_fraction', 0.30)),
            'min_aspect_ratio': float(detector.get('min_aspect_ratio', 1.10)),
            'max_aspect_ratio': float(detector.get('max_aspect_ratio', 2.20)),
            'min_rectangularity': float(detector.get('min_rectangularity', 0.60)),
            'travel_direction': self._travel_direction,
        }
        self._stable_frames_required = max(
            1, int(detector.get('stable_crossing_frames', 5))
        )
        self._reset_missing_frames = max(
            1, int(detector.get('reset_missing_frames', 15))
        )
        self._rearm_frames_required = max(
            1, int(detector.get('rearm_upstream_frames', 5))
        )
        self._rearm_margin_px = max(
            1.0, float(detector.get('rearm_margin_px', 30.0))
        )
        self._crossing_frames = 0
        self._rearm_frames = 0
        self._missing_frames = 0
        self._trigger_latched = False

        self._thickness = max(2, int(line_config.get('thickness_px', 6)))
        self._jpeg_quality = int(np.clip(config.get('jpeg_quality', 92), 50, 100))
        image_topic = str(config.get('image_topic', '/camera2/image_raw/compressed'))
        annotated_topic = str(
            config.get(
                'annotated_topic', '/vision/conveyor/stop_image/compressed'
            )
        )

        self._image_pub = self.create_publisher(
            CompressedImage, annotated_topic, SENSOR_QOS
        )
        self._line_pub = self.create_publisher(
            Float32, '/vision/conveyor/stop_line_normalized', 1
        )
        self._detected_pub = self.create_publisher(
            Bool, '/vision/conveyor/board_detected', 1
        )
        self._trigger_pub = self.create_publisher(
            Bool, '/vision/conveyor/stop_trigger', 1
        )
        self._edge_pub = self.create_publisher(
            Float32, '/vision/conveyor/trailing_edge_px', 1
        )
        self._distance_pub = self.create_publisher(
            Float32, '/vision/conveyor/distance_to_stop_px', 1
        )
        self._ready_pub = self.create_publisher(
            Bool, '/vision/conveyor/stop_line_ready', 1
        )
        self._subscription = self.create_subscription(
            CompressedImage, image_topic, self._image_cb, SENSOR_QOS
        )

        self.get_logger().info(
            f'NO MOTION stop-line overlay: {image_topic} -> {annotated_topic}'
        )
        self.get_logger().info(
            f'Stop line axis={self._stop_line.axis}, '
            f'position={self._stop_line.position:.3f}; board detector dry-run; '
            'no /cmd_vel publisher'
        )

    def _image_cb(self, message: CompressedImage) -> None:
        encoded = np.frombuffer(message.data, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            self.get_logger().warning(
                'Failed to decode camera2 compressed frame',
                throttle_duration_sec=3.0,
            )
            self._ready_pub.publish(Bool(data=False))
            return

        height, width = image.shape[:2]
        point1, point2 = normalized_line_to_pixels(self._stop_line, width, height)
        detection = detect_dark_board(
            image,
            search_bounds=self._search_bounds,
            **self._detector_settings,
        )
        line_position_px = float(point1[0] if self._stop_line.axis == 'x' else point1[1])

        if detection is None:
            self._missing_frames += 1
            self._crossing_frames = 0
            self._rearm_frames = 0
            if self._missing_frames >= self._reset_missing_frames:
                self._trigger_latched = False
            crossed = False
            distance_px = float('nan')
        else:
            self._missing_frames = 0
            if self._travel_direction == 'positive_x':
                distance_px = line_position_px - detection.trailing_edge_px
                crossed = detection.trailing_edge_px >= line_position_px
            else:
                distance_px = detection.trailing_edge_px - line_position_px
                crossed = detection.trailing_edge_px <= line_position_px
            self._crossing_frames = (
                min(self._crossing_frames + 1, self._stable_frames_required)
                if crossed else 0
            )
            if self._crossing_frames >= self._stable_frames_required:
                self._trigger_latched = True
            if not crossed and distance_px >= self._rearm_margin_px:
                self._rearm_frames = min(
                    self._rearm_frames + 1, self._rearm_frames_required
                )
                if self._rearm_frames >= self._rearm_frames_required:
                    self._trigger_latched = False
            else:
                self._rearm_frames = 0

        overlay = image.copy()

        # Dark outline preserves visibility on the current bright aluminium frame.
        cv2.line(
            overlay, point1, point2, (12, 18, 24), self._thickness + 6, cv2.LINE_AA
        )
        cv2.line(
            overlay, point1, point2, (60, 235, 80), self._thickness, cv2.LINE_AA
        )

        label_origin = (max(20, point1[0] - 300), max(42, point1[1] - 16))
        cv2.putText(
            overlay,
            'STOP LINE - BOARD TRAILING EDGE',
            label_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.78,
            (12, 18, 24),
            5,
            cv2.LINE_AA,
        )

        if detection is not None:
            points = np.rint(detection.points).astype(np.int32)
            cv2.polylines(overlay, [points], True, (255, 120, 40), 4, cv2.LINE_AA)
            edge_x = int(round(detection.trailing_edge_px))
            edge_y = int(round(np.mean(detection.points[:, 1])))
            cv2.drawMarker(
                overlay,
                (edge_x, edge_y),
                (0, 0, 255),
                cv2.MARKER_CROSS,
                30,
                4,
                cv2.LINE_AA,
            )
            status = 'STOP TRIGGER (DRY RUN)' if self._trigger_latched else 'BOARD TRACKING'
            status_color = (0, 0, 255) if self._trigger_latched else (255, 180, 40)
            cv2.putText(
                overlay,
                f'{status} | edge={edge_x}px | remain={distance_px:.1f}px | '
                f'stable={self._crossing_frames}/{self._stable_frames_required}',
                (24, 82),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                (12, 18, 24),
                5,
                cv2.LINE_AA,
            )
            cv2.putText(
                overlay,
                f'{status} | edge={edge_x}px | remain={distance_px:.1f}px | '
                f'stable={self._crossing_frames}/{self._stable_frames_required}',
                (24, 82),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.72,
                status_color,
                2,
                cv2.LINE_AA,
            )
        else:
            cv2.putText(
                overlay,
                'BOARD NOT DETECTED',
                (24, 82),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.78,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.putText(
            overlay,
            'STOP LINE - BOARD TRAILING EDGE',
            label_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.78,
            (60, 235, 80),
            2,
            cv2.LINE_AA,
        )

        if self._stop_line.axis == 'x':
            arrow_y = int(round((point1[1] + point2[1]) * 0.5))
            arrow_end_x = max(40, point1[0] - 28)
            arrow_start_x = max(15, arrow_end_x - 170)
            cv2.arrowedLine(
                overlay,
                (arrow_start_x, arrow_y),
                (arrow_end_x, arrow_y),
                (0, 210, 255),
                4,
                cv2.LINE_AA,
                tipLength=0.12,
            )
            cv2.putText(
                overlay,
                'BELT',
                (arrow_start_x, arrow_y - 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 210, 255),
                2,
                cv2.LINE_AA,
            )

        cv2.putText(
            overlay,
            'LINE SETUP ONLY | NO MOTOR COMMAND',
            (24, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.82,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        success, output = cv2.imencode(
            '.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        if not success:
            self._ready_pub.publish(Bool(data=False))
            return

        annotated = CompressedImage()
        annotated.header = message.header
        annotated.format = 'jpeg'
        annotated.data = output.tobytes()
        self._image_pub.publish(annotated)
        self._line_pub.publish(Float32(data=float(self._stop_line.position)))
        self._detected_pub.publish(Bool(data=detection is not None))
        self._trigger_pub.publish(Bool(data=self._trigger_latched))
        if detection is not None:
            self._edge_pub.publish(Float32(data=float(detection.trailing_edge_px)))
            self._distance_pub.publish(Float32(data=float(distance_px)))
        self._ready_pub.publish(Bool(data=True))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ConveyorStopLine()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
