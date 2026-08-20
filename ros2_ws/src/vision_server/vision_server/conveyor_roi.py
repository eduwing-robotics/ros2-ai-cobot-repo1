from dataclasses import dataclass

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, Float32, Int32

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
    center_px: tuple[float, float]
    trailing_edge_px: float
    travel_length_px: float
    area_fraction: float
    aspect_ratio: float
    rectangularity: float


@dataclass
class StopStation:
    name: str
    display_name: str
    line: NormalizedLine
    color: tuple[int, int, int]
    crossing_frames: int = 0
    rearm_frames: int = 0
    missing_frames: int = 0
    trigger_latched: bool = False


def travel_axis(travel_direction: str) -> str:
    if travel_direction in ('positive_x', 'negative_x'):
        return 'x'
    if travel_direction in ('positive_y', 'negative_y'):
        return 'y'
    raise ValueError(
        'travel_direction must be positive_x, negative_x, positive_y, or negative_y'
    )


def direction_is_positive(travel_direction: str) -> bool:
    travel_axis(travel_direction)
    return travel_direction.startswith('positive_')


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


def line_position_px(line: NormalizedLine, width: int, height: int) -> float:
    point1, _ = normalized_line_to_pixels(line, width, height)
    return float(point1[0] if line.axis == 'x' else point1[1])


def validate_station_layout(
    assembly_line: NormalizedLine,
    inspection_line: NormalizedLine,
    travel_direction: str,
    minimum_normalized_separation: float,
) -> float:
    axis = travel_axis(travel_direction)
    for name, line in (
        ('assembly', assembly_line),
        ('inspection', inspection_line),
    ):
        if line.axis != axis:
            raise ValueError(
                f'{name} stop line axis={line.axis!r} must match travel axis={axis!r}'
            )
        if not 0.0 <= line.position <= 1.0:
            raise ValueError(f'{name} stop line position must be between 0 and 1')
        if not 0.0 <= line.span_start < line.span_end <= 1.0:
            raise ValueError(
                f'{name} line span must satisfy 0 <= start < end <= 1'
            )

    minimum_normalized_separation = float(minimum_normalized_separation)
    if not 0.0 < minimum_normalized_separation < 1.0:
        raise ValueError('minimum_normalized_separation must be between 0 and 1')

    signed_separation = inspection_line.position - assembly_line.position
    if not direction_is_positive(travel_direction):
        signed_separation *= -1.0
    if signed_separation <= 0.0:
        raise ValueError(
            'inspection stop line must be downstream from the assembly stop line'
        )
    if signed_separation < minimum_normalized_separation:
        raise ValueError(
            'stop lines are too close: '
            f'{signed_separation:.4f} < {minimum_normalized_separation:.4f}'
        )
    return signed_separation


def station_separation_px(
    assembly_line: NormalizedLine,
    inspection_line: NormalizedLine,
    width: int,
    height: int,
) -> float:
    return abs(
        line_position_px(inspection_line, width, height)
        - line_position_px(assembly_line, width, height)
    )


def spacing_is_safe(
    separation_px: float,
    board_length_px: float,
    minimum_board_lengths: float,
    minimum_clearance_px: float,
) -> tuple[bool, float, float]:
    values = (
        separation_px,
        board_length_px,
        minimum_board_lengths,
        minimum_clearance_px,
    )
    if not all(np.isfinite(value) for value in values):
        raise ValueError('spacing values must be finite')
    if separation_px <= 0.0 or board_length_px <= 0.0:
        raise ValueError('separation_px and board_length_px must be positive')
    if minimum_board_lengths < 1.0 or minimum_clearance_px < 0.0:
        raise ValueError(
            'minimum_board_lengths must be >= 1 and clearance must be >= 0'
        )

    required_px = (
        board_length_px * minimum_board_lengths + minimum_clearance_px
    )
    board_length_ratio = separation_px / board_length_px
    return separation_px >= required_px, board_length_ratio, required_px


def _trailing_edge_and_length(
    points: np.ndarray, travel_direction: str
) -> tuple[float, float]:
    axis_index = 0 if travel_axis(travel_direction) == 'x' else 1
    coordinates = points[:, axis_index]
    if direction_is_positive(travel_direction):
        trailing_edge = float(np.min(coordinates))
    else:
        trailing_edge = float(np.max(coordinates))
    return trailing_edge, float(np.ptp(coordinates))


def _longest_true_run(values: np.ndarray) -> tuple[int, int] | None:
    best = None
    start = None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        if start is not None and (not value or index == len(values) - 1):
            end = index if value and index == len(values) - 1 else index - 1
            if best is None or end - start > best[1] - best[0]:
                best = (start, end)
            start = None
    return best


def fit_dominant_body_box(
    contour: np.ndarray,
    *,
    span_ratio: float = 0.68,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Fit the broad rectangular fixture body while ignoring a narrow handle.

    The S22 sees the PCB inside a dark fixture whose grip tab protrudes from one
    side. A plain minAreaRect includes that tab and shifts the reported centre.
    This helper rectifies the contour into its long/short-axis coordinates and
    keeps the longest short-axis run whose cross-section remains broad.
    """
    span_ratio = float(span_ratio)
    if not 0.40 <= span_ratio <= 0.95:
        raise ValueError('span_ratio must be between 0.40 and 0.95')

    contour = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
    preliminary_center, _, _ = cv2.minAreaRect(contour)
    preliminary_box = cv2.boxPoints(cv2.minAreaRect(contour))
    edges = np.roll(preliminary_box, -1, axis=0) - preliminary_box
    edge_lengths = np.linalg.norm(edges, axis=1)
    long_axis = edges[int(np.argmax(edge_lengths))]
    long_axis /= max(float(np.linalg.norm(long_axis)), 1e-9)
    short_axis = np.array((-long_axis[1], long_axis[0]), dtype=np.float32)

    x, y, width, height = cv2.boundingRect(contour.astype(np.int32))
    if width <= 1 or height <= 1:
        return preliminary_box, tuple(float(value) for value in preliminary_center)
    mask = np.zeros((height, width), dtype=np.uint8)
    shifted = np.rint(contour[:, 0, :] - np.array((x, y))).astype(np.int32)
    cv2.fillPoly(mask, [shifted], 255)
    pixel_y, pixel_x = np.nonzero(mask)
    if pixel_x.size < 16:
        return preliminary_box, tuple(float(value) for value in preliminary_center)

    pixels = np.column_stack((pixel_x + x, pixel_y + y)).astype(np.float32)
    origin = np.asarray(preliminary_center, dtype=np.float32)
    relative = pixels - origin
    long_values = relative @ long_axis
    short_values = relative @ short_axis

    short_min = float(np.floor(np.min(short_values)))
    short_bins = np.rint(short_values - short_min).astype(np.int32)
    bin_count = int(np.max(short_bins)) + 1
    minimum_long = np.full(bin_count, np.inf, dtype=np.float32)
    maximum_long = np.full(bin_count, -np.inf, dtype=np.float32)
    np.minimum.at(minimum_long, short_bins, long_values)
    np.maximum.at(maximum_long, short_bins, long_values)
    spans = maximum_long - minimum_long
    populated = np.isfinite(spans) & (spans > 0.0)
    if not np.any(populated):
        return preliminary_box, tuple(float(value) for value in preliminary_center)

    reference_span = float(np.quantile(spans[populated], 0.95))
    broad = populated & (spans >= reference_span * span_ratio)
    run = _longest_true_run(broad)
    if run is None or run[1] - run[0] + 1 < max(4, int(bin_count * 0.30)):
        return preliminary_box, tuple(float(value) for value in preliminary_center)

    run_short_min = short_min + run[0] - 0.5
    run_short_max = short_min + run[1] + 0.5
    selected = (short_values >= run_short_min) & (short_values <= run_short_max)
    selected_long = long_values[selected]
    if selected_long.size < 16:
        return preliminary_box, tuple(float(value) for value in preliminary_center)

    run_long_min, run_long_max = np.quantile(selected_long, (0.003, 0.997))
    center_long = float((run_long_min + run_long_max) * 0.5)
    center_short = float((run_short_min + run_short_max) * 0.5)
    center = origin + long_axis * center_long + short_axis * center_short
    corners = []
    for long_coordinate, short_coordinate in (
        (run_long_min, run_short_min),
        (run_long_max, run_short_min),
        (run_long_max, run_short_max),
        (run_long_min, run_short_max),
    ):
        corners.append(
            origin
            + long_axis * float(long_coordinate)
            + short_axis * float(short_coordinate)
        )
    return np.asarray(corners, dtype=np.float32), (
        float(center[0]),
        float(center[1]),
    )


def detect_dark_boards(
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
    body_span_ratio: float = 0.68,
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

        translated_contour = contour.astype(np.float32).copy()
        translated_contour[:, 0, 0] += x1
        translated_contour[:, 0, 1] += y1
        points, translated_center = fit_dominant_body_box(
            translated_contour,
            span_ratio=body_span_ratio,
        )
        trailing_edge, travel_length = _trailing_edge_and_length(
            points, travel_direction
        )
        candidates.append(
            BoardDetection(
                points=points,
                center_px=(float(translated_center[0]), float(translated_center[1])),
                trailing_edge_px=trailing_edge,
                travel_length_px=travel_length,
                area_fraction=area_fraction,
                aspect_ratio=aspect_ratio,
                rectangularity=rectangularity,
            )
        )

    axis_index = 0 if travel_axis(travel_direction) == 'x' else 1
    return sorted(candidates, key=lambda item: item.center_px[axis_index])


def detect_dark_board(image, **kwargs):
    """Backward-compatible helper that returns the largest detected board."""
    detections = detect_dark_boards(image, **kwargs)
    if not detections:
        return None
    return max(detections, key=lambda item: item.area_fraction)


def station_distance_px(
    trailing_edge_px: float, stop_line_px: float, travel_direction: str
) -> float:
    if direction_is_positive(travel_direction):
        return stop_line_px - trailing_edge_px
    return trailing_edge_px - stop_line_px


def closest_detection_to_station(
    detections: list[BoardDetection],
    stop_line_px: float,
    travel_direction: str,
):
    if not detections:
        return None
    return min(
        detections,
        key=lambda item: abs(
            station_distance_px(
                item.trailing_edge_px, stop_line_px, travel_direction
            )
        ),
    )


class ConveyorStopLine(Node):
    def __init__(self) -> None:
        super().__init__('conveyor_stop_line')
        self.declare_parameter('config_file', default_path('config/conveyor_roi.yaml'))
        config = load_yaml(self.get_parameter('config_file').value).get(
            'conveyor_roi', {}
        )

        detector = config.get('board_detection', {})
        self._travel_direction = str(
            detector.get('travel_direction', 'positive_x')
        ).lower()
        travel_axis(self._travel_direction)

        lines_config = config.get('stop_lines')
        if not lines_config:
            legacy = config.get('stop_line', {})
            assembly_position = float(legacy.get('position', 0.46))
            offset = 0.32 if direction_is_positive(self._travel_direction) else -0.32
            lines_config = {
                'assembly': legacy,
                'inspection': {
                    **legacy,
                    'position': float(np.clip(assembly_position + offset, 0.05, 0.95)),
                },
            }
            self.get_logger().warning(
                'Legacy stop_line config detected; using a provisional inspection line'
            )

        self._stations = {
            'assembly': self._make_station(
                'assembly', 'ASSEMBLY', lines_config.get('assembly', {}), (60, 235, 80)
            ),
            'inspection': self._make_station(
                'inspection',
                'VISION INSPECTION',
                lines_config.get('inspection', {}),
                (255, 190, 40),
            ),
        }

        spacing = config.get('station_spacing', {})
        self._minimum_normalized_separation = float(
            spacing.get('minimum_normalized_separation', 0.25)
        )
        self._minimum_board_lengths = float(
            spacing.get('minimum_board_lengths', 1.10)
        )
        self._minimum_clearance_px = float(
            spacing.get('minimum_clearance_px', 20.0)
        )
        self._normalized_separation = validate_station_layout(
            self._stations['assembly'].line,
            self._stations['inspection'].line,
            self._travel_direction,
            self._minimum_normalized_separation,
        )
        if self._minimum_board_lengths < 1.0:
            raise ValueError('minimum_board_lengths must be >= 1.0')
        if self._minimum_clearance_px < 0.0:
            raise ValueError('minimum_clearance_px must be >= 0')

        self._search_bounds = (
            float(detector.get('search_x_start', 0.02)),
            float(detector.get('search_x_end', 0.98)),
            float(detector.get('search_y_start', 0.20)),
            float(detector.get('search_y_end', 0.90)),
        )
        self._detector_settings = {
            'dark_threshold': int(detector.get('dark_threshold', 105)),
            'close_kernel_px': int(detector.get('close_kernel_px', 13)),
            'min_area_fraction': float(detector.get('min_area_fraction', 0.03)),
            'max_area_fraction': float(detector.get('max_area_fraction', 0.30)),
            'min_aspect_ratio': float(detector.get('min_aspect_ratio', 1.10)),
            'max_aspect_ratio': float(detector.get('max_aspect_ratio', 2.20)),
            'min_rectangularity': float(detector.get('min_rectangularity', 0.60)),
            'travel_direction': self._travel_direction,
            'body_span_ratio': float(detector.get('body_span_ratio', 0.68)),
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

        self._jpeg_quality = int(np.clip(config.get('jpeg_quality', 90), 50, 100))
        image_topic = str(config.get('image_topic', '/camera2/image_raw/compressed'))
        annotated_topic = str(
            config.get(
                'annotated_topic', '/vision/conveyor/stop_image/compressed'
            )
        )

        self._image_pub = self.create_publisher(
            CompressedImage, annotated_topic, SENSOR_QOS
        )
        self._station_publishers = {}
        for name in self._stations:
            prefix = f'/vision/conveyor/{name}'
            self._station_publishers[name] = {
                'line': self.create_publisher(
                    Float32, f'{prefix}/stop_line_normalized', 1
                ),
                'detected': self.create_publisher(
                    Bool, f'{prefix}/board_detected', 1
                ),
                'trigger': self.create_publisher(
                    Bool, f'{prefix}/stop_trigger', 1
                ),
                'edge': self.create_publisher(
                    Float32, f'{prefix}/trailing_edge_px', 1
                ),
                'distance': self.create_publisher(
                    Float32, f'{prefix}/distance_to_stop_px', 1
                ),
            }

        # Legacy aliases remain mapped to the assembly station so existing
        # launch commands and Unity integrations do not break.
        self._legacy_publishers = {
            'line': self.create_publisher(
                Float32, '/vision/conveyor/stop_line_normalized', 1
            ),
            'detected': self.create_publisher(
                Bool, '/vision/conveyor/board_detected', 1
            ),
            'trigger': self.create_publisher(
                Bool, '/vision/conveyor/stop_trigger', 1
            ),
            'edge': self.create_publisher(
                Float32, '/vision/conveyor/trailing_edge_px', 1
            ),
            'distance': self.create_publisher(
                Float32, '/vision/conveyor/distance_to_stop_px', 1
            ),
        }
        self._ready_pub = self.create_publisher(
            Bool, '/vision/conveyor/stop_line_ready', 1
        )
        self._spacing_valid_pub = self.create_publisher(
            Bool, '/vision/conveyor/station_spacing_valid', 1
        )
        self._spacing_ratio_pub = self.create_publisher(
            Float32, '/vision/conveyor/station_spacing_board_lengths', 1
        )
        self._board_count_pub = self.create_publisher(
            Int32, '/vision/conveyor/board_count', 1
        )
        self._subscription = self.create_subscription(
            CompressedImage, image_topic, self._image_cb, SENSOR_QOS
        )

        self.get_logger().info(
            f'NO MOTION dual stop-line overlay: {image_topic} -> {annotated_topic}'
        )
        self.get_logger().info(
            'Assembly line='
            f'{self._stations["assembly"].line.position:.5f}, inspection line='
            f'{self._stations["inspection"].line.position:.5f}, '
            f'separation={self._normalized_separation:.5f}; no /cmd_vel publisher'
        )

    @staticmethod
    def _make_station(name, display_name, config, color):
        return StopStation(
            name=name,
            display_name=display_name,
            line=NormalizedLine(
                axis=str(config.get('axis', 'x')).lower(),
                position=float(config.get('position', 0.50)),
                span_start=float(config.get('span_start', 0.18)),
                span_end=float(config.get('span_end', 0.82)),
            ),
            color=color,
        )

    def _update_station_state(
        self,
        station: StopStation,
        relevant_detection: BoardDetection | None,
        stop_line_px: float,
        spacing_valid: bool,
    ) -> float:
        if not spacing_valid:
            station.crossing_frames = 0
            station.rearm_frames = 0
            station.missing_frames = 0
            station.trigger_latched = False
            return float('nan')

        if relevant_detection is None:
            station.missing_frames += 1
            station.crossing_frames = 0
            station.rearm_frames = 0
            if station.missing_frames >= self._reset_missing_frames:
                station.trigger_latched = False
            return float('nan')

        station.missing_frames = 0
        distance_px = station_distance_px(
            relevant_detection.trailing_edge_px,
            stop_line_px,
            self._travel_direction,
        )
        crossed = distance_px <= 0.0
        station.crossing_frames = (
            min(station.crossing_frames + 1, self._stable_frames_required)
            if crossed
            else 0
        )
        if station.crossing_frames >= self._stable_frames_required:
            station.trigger_latched = True

        if not crossed and distance_px >= self._rearm_margin_px:
            station.rearm_frames = min(
                station.rearm_frames + 1, self._rearm_frames_required
            )
            if station.rearm_frames >= self._rearm_frames_required:
                station.trigger_latched = False
        else:
            station.rearm_frames = 0
        return distance_px

    def _publish_station(
        self,
        station: StopStation,
        detection: BoardDetection | None,
        distance_px: float,
        spacing_valid: bool,
        *,
        legacy: bool,
    ) -> None:
        publishers = self._station_publishers[station.name]
        publishers['line'].publish(Float32(data=float(station.line.position)))
        publishers['detected'].publish(Bool(data=detection is not None))
        publishers['trigger'].publish(
            Bool(data=bool(station.trigger_latched and spacing_valid))
        )
        if detection is not None:
            publishers['edge'].publish(
                Float32(data=float(detection.trailing_edge_px))
            )
        if np.isfinite(distance_px):
            publishers['distance'].publish(Float32(data=float(distance_px)))

        if not legacy:
            return
        self._legacy_publishers['line'].publish(
            Float32(data=float(station.line.position))
        )
        self._legacy_publishers['detected'].publish(
            Bool(data=detection is not None)
        )
        self._legacy_publishers['trigger'].publish(
            Bool(data=bool(station.trigger_latched and spacing_valid))
        )
        if detection is not None:
            self._legacy_publishers['edge'].publish(
                Float32(data=float(detection.trailing_edge_px))
            )
        if np.isfinite(distance_px):
            self._legacy_publishers['distance'].publish(
                Float32(data=float(distance_px))
            )

    def _draw_station_line(
        self,
        overlay,
        station: StopStation,
        point1,
        point2,
        thickness: int,
    ) -> None:
        cv2.line(
            overlay, point1, point2, (12, 18, 24), thickness + 6, cv2.LINE_AA
        )
        cv2.line(
            overlay, point1, point2, station.color, thickness, cv2.LINE_AA
        )
        if station.line.axis == 'x':
            label_origin = (max(8, point1[0] - 145), max(150, point1[1] - 12))
        else:
            label_origin = (max(8, point1[0]), max(150, point1[1] - 12))
        cv2.putText(
            overlay,
            station.display_name,
            label_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.57,
            (12, 18, 24),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            overlay,
            station.display_name,
            label_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.57,
            station.color,
            2,
            cv2.LINE_AA,
        )

    def _draw_travel_arrow(self, overlay, width, height) -> None:
        positive = direction_is_positive(self._travel_direction)
        color = (0, 210, 255)
        if travel_axis(self._travel_direction) == 'x':
            y = int(round(height * 0.92))
            start = (int(width * (0.08 if positive else 0.25)), y)
            end = (int(width * (0.25 if positive else 0.08)), y)
            text_origin = (min(start[0], end[0]), y - 16)
        else:
            x = int(round(width * 0.94))
            start = (x, int(height * (0.68 if positive else 0.88)))
            end = (x, int(height * (0.88 if positive else 0.68)))
            text_origin = (max(8, x - 95), min(start[1], end[1]) - 12)
        cv2.arrowedLine(
            overlay, start, end, color, 4, cv2.LINE_AA, tipLength=0.12
        )
        cv2.putText(
            overlay,
            'BELT',
            text_origin,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            color,
            2,
            cv2.LINE_AA,
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
        detections = detect_dark_boards(
            image,
            search_bounds=self._search_bounds,
            **self._detector_settings,
        )
        separation_px = station_separation_px(
            self._stations['assembly'].line,
            self._stations['inspection'].line,
            width,
            height,
        )
        spacing_valid = True
        spacing_ratio = float('nan')
        required_spacing_px = 0.0
        if detections:
            maximum_board_length = max(
                detection.travel_length_px for detection in detections
            )
            spacing_valid, spacing_ratio, required_spacing_px = spacing_is_safe(
                separation_px,
                maximum_board_length,
                self._minimum_board_lengths,
                self._minimum_clearance_px,
            )

        station_geometry = {}
        station_results = {}
        for name, station in self._stations.items():
            point1, point2 = normalized_line_to_pixels(
                station.line, width, height
            )
            stop_px = line_position_px(station.line, width, height)
            relevant = closest_detection_to_station(
                detections, stop_px, self._travel_direction
            )
            distance_px = self._update_station_state(
                station, relevant, stop_px, spacing_valid
            )
            station_geometry[name] = (point1, point2, stop_px)
            station_results[name] = (relevant, distance_px)

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (width, 138), (12, 18, 24), -1)
        cv2.putText(
            overlay,
            'DUAL STOP-LINE MONITOR | NO MOTOR COMMAND',
            (24, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.80,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        if not spacing_valid:
            spacing_text = (
                f'SPACING FAULT | have {separation_px:.0f}px, '
                f'need {required_spacing_px:.0f}px'
            )
        elif np.isfinite(spacing_ratio):
            spacing_text = f'SPACING OK | {spacing_ratio:.2f} board lengths'
        else:
            spacing_text = 'SPACING OK | waiting for board size'
        spacing_color = (60, 235, 80) if spacing_valid else (0, 0, 255)
        cv2.putText(
            overlay,
            f'BOARDS {len(detections)} | {spacing_text}',
            (24, 72),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.66,
            spacing_color,
            2,
            cv2.LINE_AA,
        )

        status_chunks = []
        for station in self._stations.values():
            relevant, distance_px = station_results[station.name]
            if station.trigger_latched and spacing_valid:
                state_text = 'STOP'
            elif relevant is None:
                state_text = 'WAIT'
            else:
                state_text = f'{distance_px:.0f}px'
            status_chunks.append(f'{station.display_name}: {state_text}')
        cv2.putText(
            overlay,
            '   |   '.join(status_chunks),
            (24, 106),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.64,
            (220, 225, 232),
            2,
            cv2.LINE_AA,
        )

        for detection in detections:
            points = np.rint(detection.points).astype(np.int32)
            cv2.polylines(overlay, [points], True, (255, 120, 40), 4, cv2.LINE_AA)
            center = tuple(int(round(value)) for value in detection.center_px)
            cv2.drawMarker(
                overlay,
                center,
                (255, 255, 255),
                cv2.MARKER_CROSS,
                24,
                3,
                cv2.LINE_AA,
            )

        thickness = 6
        for name, station in self._stations.items():
            point1, point2, _ = station_geometry[name]
            self._draw_station_line(
                overlay, station, point1, point2, thickness
            )
            relevant, _ = station_results[name]
            if relevant is not None:
                if station.line.axis == 'x':
                    marker_point = (
                        int(round(relevant.trailing_edge_px)),
                        int(round(relevant.center_px[1])),
                    )
                else:
                    marker_point = (
                        int(round(relevant.center_px[0])),
                        int(round(relevant.trailing_edge_px)),
                    )
                cv2.drawMarker(
                    overlay,
                    marker_point,
                    station.color,
                    cv2.MARKER_DIAMOND,
                    24,
                    3,
                    cv2.LINE_AA,
                )

        self._draw_travel_arrow(overlay, width, height)

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

        assembly = self._stations['assembly']
        assembly_detection, assembly_distance = station_results['assembly']
        self._publish_station(
            assembly,
            assembly_detection,
            assembly_distance,
            spacing_valid,
            legacy=True,
        )
        inspection = self._stations['inspection']
        inspection_detection, inspection_distance = station_results['inspection']
        self._publish_station(
            inspection,
            inspection_detection,
            inspection_distance,
            spacing_valid,
            legacy=False,
        )
        self._board_count_pub.publish(Int32(data=len(detections)))
        self._spacing_valid_pub.publish(Bool(data=spacing_valid))
        self._spacing_ratio_pub.publish(Float32(data=float(spacing_ratio)))
        self._ready_pub.publish(Bool(data=spacing_valid))


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
