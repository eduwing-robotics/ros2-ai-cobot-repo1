from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import queue
import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Point32, PolygonStamped
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, Float32, Int32, String

from .config_utils import default_path, load_yaml
from .conveyor_arrival import LiveArrival, clear_belt_region


SENSOR_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
)

# The Unity ROS-TCP subscriber requests RELIABLE delivery by default.  A
# BEST_EFFORT image publisher cannot match that subscription, which leaves the
# rqt sensor-data view working while Unity receives no frames.  Reliable is
# safe for this optional monitoring stream because its publication is isolated
# from the stop-line status messages below.
OVERLAY_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
)


def timestamp_age_seconds(
    now_nanoseconds: int, stamp_seconds: int, stamp_nanoseconds: int
) -> float:
    """Return source-frame age; unverifiable timestamps have infinite age."""
    values = (now_nanoseconds, stamp_seconds, stamp_nanoseconds)
    if not all(np.isfinite(value) for value in values):
        return float('inf')
    if stamp_seconds < 0 or not 0 <= stamp_nanoseconds < 1_000_000_000:
        return float('inf')
    stamp = int(stamp_seconds) * 1_000_000_000 + int(stamp_nanoseconds)
    if stamp <= 0 or now_nanoseconds <= 0 or stamp > now_nanoseconds:
        return float('inf')
    return (int(now_nanoseconds) - stamp) / 1_000_000_000.0


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
    long_axis_angle_deg: float


@dataclass
class VisualBoardTrack:
    detection: BoardDetection
    missing_frames: int = 0


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


def smooth_board_detection(
    previous: BoardDetection,
    current: BoardDetection,
    *,
    center_alpha: float,
    shape_alpha: float,
) -> BoardDetection:
    """Smooth a perspective body quadrilateral while preserving its live edge."""
    center_alpha = float(center_alpha)
    shape_alpha = float(shape_alpha)
    if not 0.0 < center_alpha <= 1.0:
        raise ValueError('center_alpha must satisfy 0 < alpha <= 1')
    if not 0.0 < shape_alpha <= 1.0:
        raise ValueError('shape_alpha must satisfy 0 < alpha <= 1')

    previous_center = np.asarray(previous.center_px, dtype=np.float32)
    current_center = np.asarray(current.center_px, dtype=np.float32)
    center = (
        previous_center * (1.0 - center_alpha)
        + current_center * center_alpha
    )

    previous_points = np.asarray(previous.points, dtype=np.float32).reshape(4, 2)
    current_points = np.asarray(current.points, dtype=np.float32).reshape(4, 2)
    candidates = []
    for source in (current_points, current_points[::-1]):
        for shift in range(4):
            candidate = np.roll(source, shift, axis=0)
            error = float(np.sum((candidate - previous_points) ** 2))
            candidates.append((error, candidate))
    aligned_current = min(candidates, key=lambda item: item[0])[1]

    previous_offsets = previous_points - previous_center
    current_offsets = aligned_current - current_center
    offsets = (
        previous_offsets * (1.0 - shape_alpha)
        + current_offsets * shape_alpha
    )
    points = np.asarray(center + offsets, dtype=np.float32)

    angle_delta = (
        current.long_axis_angle_deg - previous.long_axis_angle_deg + 90.0
    ) % 180.0 - 90.0
    angle = previous.long_axis_angle_deg + shape_alpha * angle_delta
    angle = (angle + 90.0) % 180.0 - 90.0
    return BoardDetection(
        points=points,
        center_px=(float(center[0]), float(center[1])),
        # Never smooth the control-critical edge. A smoothed moving edge would
        # delay the stop command even though the overlay looked steadier.
        trailing_edge_px=current.trailing_edge_px,
        travel_length_px=current.travel_length_px,
        area_fraction=current.area_fraction,
        aspect_ratio=current.aspect_ratio,
        rectangularity=current.rectangularity,
        long_axis_angle_deg=float(angle),
    )


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


def _refine_body_quad_from_edges(
    contour: np.ndarray, body_points: np.ndarray
) -> np.ndarray:
    """Snap a coarse body box to four robust outer-edge lines.

    Only the end portions of each side participate in the fit. This keeps the
    central fixture grip tab and a nearby dark conveyor guide from pulling a
    PCB edge outward, while still allowing the four image edges to form a mild
    perspective quadrilateral instead of forcing an inaccurate rectangle.
    """
    contour_points = np.asarray(contour, dtype=np.float32).reshape(-1, 2)
    body_points = np.asarray(body_points, dtype=np.float32).reshape(4, 2)
    body_edges = np.roll(body_points, -1, axis=0) - body_points
    body_lengths = np.linalg.norm(body_edges, axis=1)
    minimum_length = float(np.min(body_lengths))
    if minimum_length <= 4.0 or contour_points.shape[0] < 16:
        return body_points

    proximity = float(np.clip(minimum_length * 0.14, 4.0, 14.0))
    fitted_lines = []
    for start, edge, length in zip(body_points, body_edges, body_lengths):
        length = float(length)
        tangent = edge / max(length, 1e-6)
        relative = contour_points - start
        along = relative @ tangent
        perpendicular = np.abs(
            relative[:, 0] * tangent[1] - relative[:, 1] * tangent[0]
        )
        normalized_along = along / max(length, 1e-6)
        end_sections = (
            ((normalized_along >= 0.08) & (normalized_along <= 0.38))
            | ((normalized_along >= 0.62) & (normalized_along <= 0.92))
        )
        nearby = contour_points[end_sections & (perpendicular <= proximity)]
        if nearby.shape[0] < 8:
            fitted_lines.append((start, tangent))
            continue

        vx, vy, px, py = np.asarray(
            cv2.fitLine(nearby, cv2.DIST_HUBER, 0, 0.01, 0.01)
        ).reshape(-1)
        direction = np.asarray((vx, vy), dtype=np.float32)
        direction /= max(float(np.linalg.norm(direction)), 1e-6)
        if float(direction @ tangent) < 0.0:
            direction *= -1.0
        fitted_lines.append(
            (np.asarray((px, py), dtype=np.float32), direction)
        )

    refined = []
    for index in range(4):
        previous_point, previous_direction = fitted_lines[(index - 1) % 4]
        current_point, current_direction = fitted_lines[index]
        denominator = float(np.cross(previous_direction, current_direction))
        if abs(denominator) < 1e-3:
            return body_points
        offset = current_point - previous_point
        distance = float(np.cross(offset, current_direction) / denominator)
        refined.append(previous_point + previous_direction * distance)
    refined = np.asarray(refined, dtype=np.float32)

    diagonal = float(np.linalg.norm(np.ptp(body_points, axis=0)))
    maximum_corner_shift = max(8.0, diagonal * 0.14)
    if float(np.max(np.linalg.norm(refined - body_points, axis=1))) > maximum_corner_shift:
        return body_points
    if not cv2.isContourConvex(np.rint(refined).astype(np.int32)):
        return body_points
    original_area = abs(float(cv2.contourArea(body_points)))
    refined_area = abs(float(cv2.contourArea(refined)))
    if not original_area * 0.72 <= refined_area <= original_area * 1.28:
        return body_points
    return refined


def fit_dominant_body_box(
    contour: np.ndarray,
    *,
    span_ratio: float = 0.68,
    extension_ratio: float = 1.08,
    extension_fraction: float = 0.15,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Fit the rectangular PCB body while rejecting the fixture handle.

    The handle is connected to the PCB, so a plain ``minAreaRect`` includes it.
    After an in-plane rotation the handle may protrude along either body axis.
    We inspect both rectified scan-line profiles and replace only an outlier
    boundary with the profile's median body boundary. The returned polygon is
    always a regular oriented rectangle so shadows or one noisy contour corner
    cannot visibly shear the board outline.
    """
    span_ratio = float(span_ratio)
    if not 0.40 <= span_ratio <= 0.95:
        raise ValueError('span_ratio must be between 0.40 and 0.95')
    extension_ratio = float(extension_ratio)
    if not 1.01 <= extension_ratio <= 1.50:
        raise ValueError('extension_ratio must be between 1.01 and 1.50')
    extension_fraction = float(extension_fraction)
    if not 0.05 <= extension_fraction <= 0.90:
        raise ValueError('extension_fraction must be between 0.05 and 0.90')

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

    def profile(primary_values, secondary_values):
        primary_min = float(np.floor(np.min(primary_values)))
        bins = np.rint(primary_values - primary_min).astype(np.int32)
        bin_count = int(np.max(bins)) + 1
        minimum = np.full(bin_count, np.inf, dtype=np.float32)
        maximum = np.full(bin_count, -np.inf, dtype=np.float32)
        np.minimum.at(minimum, bins, secondary_values)
        np.maximum.at(maximum, bins, secondary_values)
        spans = maximum - minimum
        valid = np.isfinite(spans) & (spans > 0.0)
        return minimum, maximum, spans, valid

    # Profile A scans across the short axis and measures long-axis width.
    # Profile B scans across the long axis and measures short-axis width.
    minimum_long, maximum_long, long_spans, long_valid = profile(
        short_values, long_values
    )
    minimum_short, maximum_short, short_spans, short_valid = profile(
        long_values, short_values
    )
    if not np.any(long_valid) or not np.any(short_valid):
        return preliminary_box, tuple(float(value) for value in preliminary_center)

    long_min, long_max = np.quantile(long_values, (0.003, 0.997))
    short_min, short_max = np.quantile(short_values, (0.003, 0.997))

    def body_bounds(minimum, maximum, spans, valid):
        reference = float(np.median(spans[valid]))
        body_like = valid & (spans >= reference * span_ratio)
        if int(np.count_nonzero(body_like)) < 4:
            body_like = valid
        outlier = valid & (spans > reference * extension_ratio)
        outlier_fraction = float(np.count_nonzero(outlier)) / float(
            np.count_nonzero(valid)
        )
        if outlier_fraction >= extension_fraction:
            return (
                float(np.median(minimum[body_like])),
                float(np.median(maximum[body_like])),
                True,
            )
        return 0.0, 0.0, False

    # A large span in Profile A is a handle extending along the long axis.
    clipped_min, clipped_max, clipped = body_bounds(
        minimum_long, maximum_long, long_spans, long_valid
    )
    if clipped:
        long_min, long_max = clipped_min, clipped_max

    # A large span in Profile B is a handle extending along the short axis.
    clipped_min, clipped_max, clipped = body_bounds(
        minimum_short, maximum_short, short_spans, short_valid
    )
    if clipped:
        short_min, short_max = clipped_min, clipped_max

    center_long = float((long_min + long_max) * 0.5)
    center_short = float((short_min + short_max) * 0.5)
    center = origin + long_axis * center_long + short_axis * center_short
    corners = []
    for long_coordinate, short_coordinate in (
        (long_min, short_min),
        (long_max, short_min),
        (long_max, short_max),
        (long_min, short_max),
    ):
        corners.append(
            origin
            + long_axis * float(long_coordinate)
            + short_axis * float(short_coordinate)
        )
    regular_points = np.asarray(corners, dtype=np.float32)
    refined_points = _refine_body_quad_from_edges(contour, regular_points)
    refined_center = np.mean(refined_points, axis=0)
    return refined_points, (
        float(refined_center[0]),
        float(refined_center[1]),
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
    body_extension_ratio: float = 1.08,
    body_extension_fraction: float = 0.15,
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
        # Keep every boundary pixel: the robust four-line fit needs uniform
        # samples along the true PCB edges. CHAIN_APPROX_SIMPLE overweights
        # chamfers and grip-tab corners and made the fitted angle jump.
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
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
            extension_ratio=body_extension_ratio,
            extension_fraction=body_extension_fraction,
        )
        # Report orientation from the body-only polygon, not from the raw
        # PCB-plus-handle contour used for candidate filtering.
        body_edges = np.roll(points, -1, axis=0) - points
        body_edge_lengths = np.linalg.norm(body_edges, axis=1)
        body_long_axis = body_edges[int(np.argmax(body_edge_lengths))]
        long_axis_angle = float(
            np.degrees(np.arctan2(body_long_axis[1], body_long_axis[0]))
        )
        while long_axis_angle >= 90.0:
            long_axis_angle -= 180.0
        while long_axis_angle < -90.0:
            long_axis_angle += 180.0
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
                long_axis_angle_deg=long_axis_angle,
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


def trigger_boundary_crossed(distance_px: float, lead_px: float) -> bool:
    """Return true when a board reaches the latency-compensated trigger edge."""
    distance_px = float(distance_px)
    lead_px = float(lead_px)
    if not np.isfinite(distance_px):
        return False
    if not np.isfinite(lead_px) or lead_px < 0.0:
        raise ValueError('trigger lead must be finite and >= 0 px')
    return distance_px <= lead_px


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
        # The camera publisher also uses OpenCV. Avoid two Python processes
        # each creating a worker for every CPU, which caused periodic frame
        # stalls even though average CPU usage looked acceptable.
        cv2.setNumThreads(2)
        self._hud_fonts = self._load_hud_fonts()
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
            'body_extension_ratio': float(
                detector.get('body_extension_ratio', 1.08)
            ),
            'body_extension_fraction': float(
                detector.get('body_extension_fraction', 0.15)
            ),
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
        self._trigger_lead_px = max(
            0.0, float(detector.get('stop_trigger_lead_px', 0.0))
        )
        self._track_center_alpha = float(
            detector.get('tracking_center_alpha', 0.75)
        )
        self._track_shape_alpha = float(
            detector.get('tracking_shape_alpha', 0.25)
        )
        if not 0.0 < self._track_center_alpha <= 1.0:
            raise ValueError('tracking_center_alpha must satisfy 0 < alpha <= 1')
        if not 0.0 < self._track_shape_alpha <= 1.0:
            raise ValueError('tracking_shape_alpha must satisfy 0 < alpha <= 1')
        self._track_match_distance_px = max(
            1.0, float(detector.get('tracking_match_distance_px', 80.0))
        )
        self._track_hold_frames = max(
            0, int(detector.get('tracking_hold_frames', 3))
        )
        self._visual_tracks: list[VisualBoardTrack] = []
        self._last_spacing_ratio = float('nan')

        self._jpeg_quality = int(np.clip(config.get('jpeg_quality', 90), 50, 100))
        self._processing_max_width = max(
            0, int(config.get('processing_max_width', 0))
        )
        self._annotated_max_width = max(
            0, int(config.get('annotated_max_width', 0))
        )
        self._annotated_fps = float(config.get('annotated_fps', 15.0))
        if not np.isfinite(self._annotated_fps) or self._annotated_fps <= 0.0:
            raise ValueError('annotated_fps must be finite and > 0')
        self._annotated_period = 1.0 / self._annotated_fps
        self._last_annotated_at = 0.0
        self._render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='stop_overlay')
        self._render_future = None
        # Optional station telemetry can be delayed by a slow ROS subscriber
        # (for example a Unity dashboard).  Keep it off the image callback so
        # the stop trigger and ready status are never held up by UI traffic.
        # A single latest-frame batch is sufficient for display.
        self._telemetry_queue = queue.Queue(maxsize=1)
        self._telemetry_stop = threading.Event()
        self._telemetry_thread = None
        self._max_frame_age_seconds = float(
            config.get('max_frame_age_seconds', 0.20)
        )
        if (
            not np.isfinite(self._max_frame_age_seconds)
            or self._max_frame_age_seconds <= 0.0
        ):
            raise ValueError('max_frame_age_seconds must be finite and > 0')
        image_topic = str(config.get('image_topic', '/camera2/image_raw/compressed'))
        annotated_topic = str(
            config.get(
                'annotated_topic', '/vision/conveyor/stop_image/compressed'
            )
        )

        self._image_pub = self.create_publisher(
            CompressedImage, annotated_topic, OVERLAY_QOS
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
                'polygon': self.create_publisher(
                    PolygonStamped,
                    f'{prefix}/board_polygon_normalized',
                    SENSOR_QOS,
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
        self._empty_belt_region = config.get('empty_belt_region')
        self._empty_upstream_margin_px = float(
            config.get('empty_upstream_margin_px', 5.0)
        )
        if (not np.isfinite(self._empty_upstream_margin_px)
                or self._empty_upstream_margin_px < 0.0):
            raise ValueError('empty_upstream_margin_px must be finite and >= 0')
        arrival_config = config.get('arrival_observation', {})
        self._arrival = LiveArrival(max_age=self._max_frame_age_seconds, **arrival_config)
        self._arrival_publishers = {
            station: self.create_publisher(
                String, f'/vision/conveyor/{station}/arrival_observation', 1)
            for station in self._stations
        }
        self._motor_subscription = self.create_subscription(
            String, '/conveyor/state', self._arrival_motor_callback, 1)
        # Expire evidence even when the camera stops publishing entirely.
        self.create_timer(0.05, self._publish_arrivals)

        self._telemetry_thread = threading.Thread(
            target=self._telemetry_loop,
            name='stop_telemetry',
            daemon=True,
        )
        self._telemetry_thread.start()

        self.get_logger().info(
            f'NO MOTION dual stop-line overlay: {image_topic} -> {annotated_topic}'
        )
        self.get_logger().info(
            'Assembly line='
            f'{self._stations["assembly"].line.position:.5f}, inspection line='
            f'{self._stations["inspection"].line.position:.5f}, '
            f'separation={self._normalized_separation:.5f}, '
            f'trigger lead={self._trigger_lead_px:.1f}px; no /cmd_vel publisher'
        )
        self.get_logger().info(
            f'Control is published before UI; stale-frame cutoff='
            f'{self._max_frame_age_seconds:.3f}s, overlay={self._annotated_fps:g} FPS'
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
        # The live detector runs at 15 FPS. Trigger slightly before the visible
        # line to compensate one capture/transport interval while keeping the
        # displayed line at the actual desired stop position.
        crossed = trigger_boundary_crossed(distance_px, self._trigger_lead_px)
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

    def _update_visual_tracks(
        self, detections: list[BoardDetection]
    ) -> list[BoardDetection]:
        unmatched_track_indices = set(range(len(self._visual_tracks)))
        updated_tracks: list[VisualBoardTrack] = []
        axis_index = 0 if travel_axis(self._travel_direction) == 'x' else 1

        for detection in sorted(
            detections, key=lambda item: item.center_px[axis_index]
        ):
            best_index = None
            best_distance = float('inf')
            current_center = np.asarray(detection.center_px, dtype=np.float32)
            for index in unmatched_track_indices:
                previous_center = np.asarray(
                    self._visual_tracks[index].detection.center_px,
                    dtype=np.float32,
                )
                distance = float(np.linalg.norm(current_center - previous_center))
                if distance < best_distance:
                    best_index = index
                    best_distance = distance

            if (
                best_index is not None
                and best_distance <= self._track_match_distance_px
            ):
                previous = self._visual_tracks[best_index].detection
                stabilized = smooth_board_detection(
                    previous,
                    detection,
                    center_alpha=self._track_center_alpha,
                    shape_alpha=self._track_shape_alpha,
                )
                unmatched_track_indices.remove(best_index)
            else:
                stabilized = detection
            updated_tracks.append(VisualBoardTrack(stabilized))

        for index in unmatched_track_indices:
            previous_track = self._visual_tracks[index]
            missing_frames = previous_track.missing_frames + 1
            if missing_frames <= self._track_hold_frames:
                updated_tracks.append(
                    VisualBoardTrack(previous_track.detection, missing_frames)
                )

        updated_tracks.sort(
            key=lambda track: track.detection.center_px[axis_index]
        )
        self._visual_tracks = updated_tracks
        return [track.detection for track in updated_tracks]

    def _telemetry_loop(self) -> None:
        """Publish latest non-critical station telemetry outside image callback."""
        while not self._telemetry_stop.is_set():
            try:
                batch = self._telemetry_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                for item in batch:
                    (
                        station,
                        detection,
                        distance_px,
                        spacing_valid,
                        source_header,
                        image_width,
                        image_height,
                        legacy,
                    ) = item
                    self._publish_station(
                        station,
                        detection,
                        distance_px,
                        spacing_valid,
                        source_header,
                        image_width,
                        image_height,
                        legacy=legacy,
                        include_trigger=False,
                    )
            except Exception as exc:  # pragma: no cover - ROS middleware edge
                self.get_logger().warning(
                    f'Asynchronous station telemetry failed: {type(exc).__name__}'
                )
            finally:
                self._telemetry_queue.task_done()

    def _enqueue_station_telemetry(self, batch) -> None:
        """Replace stale dashboard data without ever blocking the camera callback."""
        if not batch:
            return
        try:
            # Keep one coherent assembly+inspection snapshot.  Dropping an old
            # visual frame is preferable to delaying control status publication.
            while True:
                self._telemetry_queue.get_nowait()
                self._telemetry_queue.task_done()
        except queue.Empty:
            pass
        try:
            self._telemetry_queue.put_nowait(tuple(batch))
        except queue.Full:
            # The worker won the race and is publishing the previous batch;
            # the next camera frame will replace it.
            pass

    def _publish_station(
        self,
        station: StopStation,
        detection: BoardDetection | None,
        distance_px: float,
        spacing_valid: bool,
        source_header,
        image_width: int,
        image_height: int,
        *,
        legacy: bool,
        defer_optional: bool = False,
        include_trigger: bool = True,
    ):
        publishers = self._station_publishers[station.name]
        trigger = Bool(data=bool(station.trigger_latched and spacing_valid))
        if include_trigger:
            publishers['trigger'].publish(trigger)
            if legacy:
                self._legacy_publishers['trigger'].publish(trigger)

        if defer_optional:
            # Copy all state that is mutated by the next frame before handing
            # it to the worker.  ROS message headers are tiny and copyable.
            return (
                copy.deepcopy(station),
                copy.deepcopy(detection),
                float(distance_px),
                bool(spacing_valid),
                copy.deepcopy(source_header),
                int(image_width),
                int(image_height),
                bool(legacy),
            )

        publishers['line'].publish(Float32(data=float(station.line.position)))
        publishers['detected'].publish(Bool(data=detection is not None))
        if detection is not None:
            publishers['edge'].publish(
                Float32(data=float(detection.trailing_edge_px))
            )
            polygon = PolygonStamped()
            polygon.header.stamp = source_header.stamp
            polygon.header.frame_id = 'camera2_normalized_image'
            width_scale = max(1.0, float(image_width - 1))
            height_scale = max(1.0, float(image_height - 1))
            polygon.polygon.points = [
                Point32(
                    x=float(point[0]) / width_scale,
                    y=float(point[1]) / height_scale,
                    z=0.0,
                )
                for point in detection.points
            ]
            publishers['polygon'].publish(polygon)
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
    ) -> None:
        vector = np.asarray(point2, dtype=np.float32) - np.asarray(
            point1, dtype=np.float32
        )
        length = float(np.linalg.norm(vector))
        if length <= 0.0:
            return
        direction = vector / length
        ui_scale = max(0.75, overlay.shape[1] / 960.0)
        segment_px = 10.0 * ui_scale
        gap_px = 7.0 * ui_scale
        shadow_thickness = max(2, int(round(3 * ui_scale)))
        line_thickness = max(1, int(round(ui_scale)))
        for start in np.arange(0.0, length, segment_px + gap_px):
            end = min(start + segment_px, length)
            segment_start = tuple(
                np.rint(np.asarray(point1) + direction * start).astype(int)
            )
            segment_end = tuple(
                np.rint(np.asarray(point1) + direction * end).astype(int)
            )
            cv2.line(
                overlay,
                segment_start,
                segment_end,
                (12, 18, 24),
                shadow_thickness,
                cv2.LINE_AA,
            )
            cv2.line(
                overlay,
                segment_start,
                segment_end,
                station.color,
                line_thickness,
                cv2.LINE_AA,
            )

        # A small geometric notch marks the calibrated line. Station names
        # remain in the lower process HUD, keeping text off the conveyor.
        notch_half = max(5, int(round(8 * ui_scale)))
        notch_depth = max(4, int(round(6 * ui_scale)))
        if station.line.axis == 'x':
            cv2.line(
                overlay,
                (point1[0] - notch_half, point1[1]),
                (point1[0] + notch_half, point1[1]),
                station.color,
                max(1, line_thickness),
                cv2.LINE_AA,
            )
            notch = np.asarray(
                [
                    (point1[0] - notch_depth, point1[1] - notch_depth),
                    (point1[0] + notch_depth, point1[1] - notch_depth),
                    (point1[0], point1[1] + 1),
                ],
                dtype=np.int32,
            )
        else:
            cv2.line(
                overlay,
                (point1[0], point1[1] - notch_half),
                (point1[0], point1[1] + notch_half),
                station.color,
                max(1, line_thickness),
                cv2.LINE_AA,
            )
            notch = np.asarray(
                [
                    (point1[0] - notch_depth, point1[1] - notch_depth),
                    (point1[0] - notch_depth, point1[1] + notch_depth),
                    (point1[0] + 1, point1[1]),
                ],
                dtype=np.int32,
            )
        cv2.fillConvexPoly(overlay, notch, station.color, cv2.LINE_AA)

    @staticmethod
    def _draw_rounded_box(
        image,
        point1,
        point2,
        color,
        *,
        radius: int = 12,
        thickness: int = -1,
    ) -> None:
        x1, y1 = point1
        x2, y2 = point2
        radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        if thickness < 0:
            cv2.rectangle(image, (x1 + radius, y1), (x2 - radius, y2), color, -1)
            cv2.rectangle(image, (x1, y1 + radius), (x2, y2 - radius), color, -1)
            for center in (
                (x1 + radius, y1 + radius),
                (x2 - radius, y1 + radius),
                (x1 + radius, y2 - radius),
                (x2 - radius, y2 - radius),
            ):
                cv2.circle(image, center, radius, color, -1, cv2.LINE_AA)
            return

        cv2.line(
            image, (x1 + radius, y1), (x2 - radius, y1), color, thickness, cv2.LINE_AA
        )
        cv2.line(
            image, (x1 + radius, y2), (x2 - radius, y2), color, thickness, cv2.LINE_AA
        )
        cv2.line(
            image, (x1, y1 + radius), (x1, y2 - radius), color, thickness, cv2.LINE_AA
        )
        cv2.line(
            image, (x2, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA
        )
        for center, start_angle, end_angle in (
            ((x1 + radius, y1 + radius), 180, 270),
            ((x2 - radius, y1 + radius), 270, 360),
            ((x2 - radius, y2 - radius), 0, 90),
            ((x1 + radius, y2 - radius), 90, 180),
        ):
            cv2.ellipse(
                image,
                center,
                (radius, radius),
                0,
                start_angle,
                end_angle,
                color,
                thickness,
                cv2.LINE_AA,
            )

    @staticmethod
    def _load_hud_fonts():
        if not hasattr(cv2, 'freetype'):
            return None
        font_paths = (
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Medium.ttf',
        )
        try:
            fonts = []
            for font_path in font_paths:
                font = cv2.freetype.createFreeType2()
                font.loadFontData(fontFileName=font_path, id=0)
                fonts.append(font)
            return tuple(fonts)
        except (cv2.error, OSError):
            return None

    def _draw_hud_text(
        self,
        image,
        text: str,
        origin,
        font_height: int,
        color,
        *,
        medium: bool = False,
    ) -> None:
        font_height = max(8, int(font_height))
        if self._hud_fonts is not None:
            font = self._hud_fonts[1 if medium else 0]
            font.putText(
                image,
                text,
                origin,
                font_height,
                color,
                -1,
                cv2.LINE_AA,
                False,
            )
            return
        cv2.putText(
            image,
            text,
            (origin[0], origin[1] + font_height),
            cv2.FONT_HERSHEY_DUPLEX,
            font_height / 30.0,
            color,
            1,
            cv2.LINE_AA,
        )

    def _draw_card_dashboard(
        self,
        overlay,
        detections: list[BoardDetection],
        station_results,
        spacing_valid: bool,
        spacing_ratio: float,
        separation_px: float,
        required_spacing_px: float,
    ) -> None:
        height, width = overlay.shape[:2]
        ui_scale = max(0.75, width / 960.0)

        def px(value: float) -> int:
            return int(round(value * ui_scale))

        panel_height = max(px(100), int(round(height * 0.19)))
        panel_top = height - panel_height
        panel = overlay[panel_top:height]
        shade = np.full_like(panel, (7, 11, 18))
        cv2.addWeighted(panel, 0.08, shade, 0.92, 0.0, panel)
        cv2.line(
            overlay,
            (0, panel_top),
            (width - 1, panel_top),
            (42, 54, 72),
            max(1, px(1)),
            cv2.LINE_AA,
        )
        cv2.line(
            overlay,
            (0, panel_top),
            (px(118), panel_top),
            (255, 178, 55),
            max(1, px(2)),
            cv2.LINE_AA,
        )

        if not spacing_valid:
            system_state = 'SYSTEM INTERLOCK'
            system_color = (50, 75, 245)
            spacing_text = f'{separation_px:.0f}/{required_spacing_px:.0f}px'
        elif np.isfinite(spacing_ratio):
            system_state = 'SYSTEM READY'
            system_color = (85, 225, 125)
            spacing_text = f'{spacing_ratio:.2f}x'
        else:
            system_state = 'SYSTEM READY'
            system_color = (85, 225, 125)
            spacing_text = '--'

        margin = px(12)
        gap = px(8)
        card_top = panel_top + px(10)
        card_bottom = height - px(10)
        summary_width = int(round(width * 0.24))
        station_width = (width - margin * 2 - gap * 2 - summary_width) // 2
        cards = {
            'summary': (margin, margin + summary_width),
            'assembly': (
                margin + summary_width + gap,
                margin + summary_width + gap + station_width,
            ),
            'inspection': (
                margin + summary_width + gap * 2 + station_width,
                width - margin,
            ),
        }
        for x1, x2 in cards.values():
            self._draw_rounded_box(
                overlay,
                (x1, card_top),
                (x2, card_bottom),
                (19, 27, 39),
                radius=px(11),
            )
            self._draw_rounded_box(
                overlay,
                (x1, card_top),
                (x2, card_bottom),
                (48, 62, 82),
                radius=px(11),
                thickness=max(1, px(1)),
            )

        summary_x1, _ = cards['summary']
        summary_x = summary_x1 + px(15)
        cv2.line(
            overlay,
            (summary_x1 + px(12), card_top),
            (summary_x1 + px(72), card_top),
            system_color,
            max(1, px(2)),
            cv2.LINE_AA,
        )
        cv2.circle(
            overlay,
            (summary_x + px(4), card_top + px(17)),
            px(3),
            system_color,
            -1,
            cv2.LINE_AA,
        )
        self._draw_hud_text(
            overlay,
            'KSMC  //  CELL 01',
            (summary_x + px(14), card_top + px(11)),
            px(10),
            (158, 171, 190),
            medium=True,
        )
        self._draw_hud_text(
            overlay,
            system_state,
            (summary_x, card_top + px(31)),
            px(18),
            system_color,
            medium=True,
        )
        positive = direction_is_positive(self._travel_direction)
        flow = '>>>' if positive else '<<<'
        self._draw_hud_text(
            overlay,
            f'LIVE  |  {len(detections):02d} BOARDS  |  SPACE {spacing_text}  |  {flow}',
            (summary_x, card_top + px(63)),
            px(9),
            (148, 161, 180),
        )

        for station in self._stations.values():
            detection, distance_px = station_results[station.name]
            if station.trigger_latched and spacing_valid:
                state = 'TARGET LOCKED'
            elif detection is None:
                state = 'WAITING'
            elif distance_px <= 35.0:
                state = 'APPROACH'
            else:
                state = 'TRACKING'
            yaw = (
                f'{detection.long_axis_angle_deg:+.1f} deg'
                if detection is not None
                else '--'
            )
            offset = f'{distance_px:+.0f} px' if np.isfinite(distance_px) else '--'
            x1, x2 = cards[station.name]
            content_x = x1 + px(17)
            station_number = '01' if station.name == 'assembly' else '02'
            cv2.line(
                overlay,
                (x1 + px(12), card_top),
                (x1 + px(84), card_top),
                station.color,
                max(1, px(2)),
                cv2.LINE_AA,
            )
            self._draw_hud_text(
                overlay,
                f'STATION {station_number}  //  {station.display_name}',
                (content_x, card_top + px(11)),
                px(10),
                (158, 171, 190),
                medium=True,
            )
            cv2.circle(
                overlay,
                (x2 - px(19), card_top + px(17)),
                px(4),
                station.color if detection is not None else (92, 102, 118),
                -1,
                cv2.LINE_AA,
            )
            self._draw_hud_text(
                overlay,
                station_number,
                (x2 - px(50), card_top + px(27)),
                px(30),
                (31, 42, 58),
                medium=True,
            )
            self._draw_hud_text(
                overlay,
                state,
                (content_x, card_top + px(31)),
                px(18),
                station.color if state == 'TARGET LOCKED' else (235, 239, 245),
                medium=True,
            )
            self._draw_hud_text(
                overlay,
                f'EDGE  {offset}    //    YAW  {yaw}',
                (content_x, card_top + px(63)),
                px(9),
                (148, 161, 180),
            )

    def _draw_dashboard(
        self,
        overlay,
        detections: list[BoardDetection],
        station_results,
        spacing_valid: bool,
        spacing_ratio: float,
        separation_px: float,
        required_spacing_px: float,
    ) -> None:
        height, width = overlay.shape[:2]
        ui_scale = max(0.75, width / 960.0)

        def px(value: float) -> int:
            return int(round(value * ui_scale))

        panel_height = max(px(104), int(round(height * 0.195)))
        panel_top = height - panel_height
        panel = overlay[panel_top:height]
        shade = np.full_like(panel, (6, 11, 19))
        cv2.addWeighted(panel, 0.07, shade, 0.93, 0.0, panel)

        # Low-contrast technical grid and a segmented status rail keep the HUD
        # structured without introducing another set of boxed cards.
        grid_color = (14, 23, 36)
        for x in range(0, width, max(1, px(32))):
            cv2.line(
                overlay,
                (x, panel_top),
                (x, height - 1),
                grid_color,
                1,
                cv2.LINE_AA,
            )
        cv2.line(
            overlay,
            (0, panel_top),
            (width - 1, panel_top),
            (42, 57, 78),
            max(1, px(1)),
            cv2.LINE_AA,
        )

        brand_end = px(190)
        metrics_start = width - px(205)
        cv2.line(
            overlay,
            (brand_end, panel_top + px(12)),
            (brand_end, height - px(12)),
            (43, 57, 76),
            1,
            cv2.LINE_AA,
        )
        cv2.line(
            overlay,
            (metrics_start, panel_top + px(12)),
            (metrics_start, height - px(12)),
            (43, 57, 76),
            1,
            cv2.LINE_AA,
        )

        if not spacing_valid:
            system_state = 'SYSTEM INTERLOCK'
            system_color = (55, 78, 245)
            spacing_text = f'{separation_px:.0f}/{required_spacing_px:.0f}'
        elif np.isfinite(spacing_ratio):
            system_state = 'SYSTEM READY'
            system_color = (82, 226, 126)
            spacing_text = f'{spacing_ratio:.2f}x'
        else:
            system_state = 'SYSTEM READY'
            system_color = (82, 226, 126)
            spacing_text = '--'

        # Brand and controller state.
        brand_x = px(20)
        self._draw_hud_text(
            overlay,
            'KSMC',
            (brand_x, panel_top + px(13)),
            px(22),
            (242, 247, 252),
            medium=True,
        )
        cv2.line(
            overlay,
            (brand_x, panel_top + px(43)),
            (brand_x + px(44), panel_top + px(43)),
            (255, 179, 52),
            max(1, px(2)),
            cv2.LINE_AA,
        )
        self._draw_hud_text(
            overlay,
            'VISION ASSEMBLY CELL',
            (brand_x, panel_top + px(49)),
            px(8),
            (139, 154, 175),
            medium=True,
        )
        cv2.circle(
            overlay,
            (brand_x + px(4), panel_top + px(73)),
            px(3),
            system_color,
            -1,
            cv2.LINE_AA,
        )
        self._draw_hud_text(
            overlay,
            system_state,
            (brand_x + px(13), panel_top + px(66)),
            px(10),
            system_color,
            medium=True,
        )
        self._draw_hud_text(
            overlay,
            'LIVE  //  ROS DOMAIN 05',
            (brand_x, panel_top + px(87)),
            px(8),
            (108, 123, 145),
        )

        # Central process flow. The two nodes mirror the physical stop lines
        # without putting station text over the conveyor image.
        flow_left = brand_end + px(28)
        flow_right = metrics_start - px(28)
        flow_span = flow_right - flow_left
        node_positions = {
            'assembly': flow_left + int(round(flow_span * 0.28)),
            'inspection': flow_left + int(round(flow_span * 0.72)),
        }
        node_y = panel_top + px(48)
        node_radius = px(15)
        assembly_x = node_positions['assembly']
        inspection_x = node_positions['inspection']
        cv2.line(
            overlay,
            (assembly_x + node_radius, node_y),
            (inspection_x - node_radius, node_y),
            (48, 66, 88),
            max(1, px(3)),
            cv2.LINE_AA,
        )
        cv2.line(
            overlay,
            (assembly_x + node_radius, node_y),
            (inspection_x - node_radius, node_y),
            (88, 178, 175),
            max(1, px(1)),
            cv2.LINE_AA,
        )
        for fraction in (0.40, 0.50, 0.60):
            arrow_x = int(round(assembly_x + (inspection_x - assembly_x) * fraction))
            chevron = np.asarray(
                [
                    (arrow_x - px(3), node_y - px(4)),
                    (arrow_x + px(2), node_y),
                    (arrow_x - px(3), node_y + px(4)),
                ],
                dtype=np.int32,
            )
            cv2.polylines(
                overlay,
                [chevron],
                False,
                (255, 181, 58),
                max(1, px(1)),
                cv2.LINE_AA,
            )

        for station in self._stations.values():
            detection, distance_px = station_results[station.name]
            if station.trigger_latched and spacing_valid:
                state = 'LOCKED'
            elif detection is None:
                state = 'WAIT'
            elif distance_px <= 35.0:
                state = 'APPROACH'
            else:
                state = 'TRACK'
            station_number = '01' if station.name == 'assembly' else '02'
            short_name = 'ASSEMBLY' if station.name == 'assembly' else 'INSPECTION'
            node_x = node_positions[station.name]
            self._draw_hud_text(
                overlay,
                f'{station_number}  {short_name}',
                (node_x - px(38), panel_top + px(10)),
                px(9),
                (158, 173, 193),
                medium=True,
            )
            glow_color = tuple(int(channel * 0.22) for channel in station.color)
            cv2.circle(
                overlay,
                (node_x, node_y),
                px(20),
                glow_color,
                -1,
                cv2.LINE_AA,
            )
            cv2.circle(
                overlay,
                (node_x, node_y),
                node_radius,
                (13, 21, 31),
                -1,
                cv2.LINE_AA,
            )
            cv2.circle(
                overlay,
                (node_x, node_y),
                node_radius,
                station.color,
                max(1, px(2)),
                cv2.LINE_AA,
            )
            self._draw_hud_text(
                overlay,
                station_number,
                (node_x - px(7), node_y - px(7)),
                px(11),
                (238, 244, 250),
                medium=True,
            )

            yaw = (
                f'{detection.long_axis_angle_deg:+.1f}'
                if detection is not None
                else '--'
            )
            offset = f'{distance_px:+.0f}' if np.isfinite(distance_px) else '--'
            pill_half = px(77)
            pill_top = panel_top + px(72)
            pill_bottom = panel_top + px(94)
            self._draw_rounded_box(
                overlay,
                (node_x - pill_half, pill_top),
                (node_x + pill_half, pill_bottom),
                (17, 25, 36),
                radius=px(9),
            )
            self._draw_rounded_box(
                overlay,
                (node_x - pill_half, pill_top),
                (node_x + pill_half, pill_bottom),
                tuple(int(channel * 0.55) for channel in station.color),
                radius=px(9),
                thickness=1,
            )
            self._draw_hud_text(
                overlay,
                f'{state}  |  {offset}px  |  {yaw}deg',
                (node_x - pill_half + px(9), pill_top + px(6)),
                px(8),
                station.color if state == 'LOCKED' else (184, 195, 211),
                medium=True,
            )

        # Compact production metrics on the right.
        metric_x = metrics_start + px(18)
        self._draw_hud_text(
            overlay,
            'BOARDS',
            (metric_x, panel_top + px(13)),
            px(8),
            (128, 143, 165),
            medium=True,
        )
        self._draw_hud_text(
            overlay,
            f'{len(detections):02d}',
            (metric_x, panel_top + px(28)),
            px(25),
            (242, 247, 252),
            medium=True,
        )
        spacing_x = metric_x + px(72)
        self._draw_hud_text(
            overlay,
            'SPACING',
            (spacing_x, panel_top + px(13)),
            px(8),
            (128, 143, 165),
            medium=True,
        )
        self._draw_hud_text(
            overlay,
            spacing_text,
            (spacing_x, panel_top + px(32)),
            px(16),
            system_color,
            medium=True,
        )
        cv2.line(
            overlay,
            (metric_x, panel_top + px(66)),
            (width - px(18), panel_top + px(66)),
            (42, 56, 75),
            1,
            cv2.LINE_AA,
        )
        positive = direction_is_positive(self._travel_direction)
        flow_text = 'FORWARD  >>>' if positive else 'REVERSE  <<<'
        self._draw_hud_text(
            overlay,
            'PCB FLOW',
            (metric_x, panel_top + px(76)),
            px(8),
            (128, 143, 165),
            medium=True,
        )
        self._draw_hud_text(
            overlay,
            flow_text,
            (metric_x, panel_top + px(88)),
            px(10),
            (255, 181, 58),
            medium=True,
        )

    def _arrival_motor_callback(self, message: String) -> None:
        try:
            payload = json.loads(message.data)
        except (ValueError, TypeError):
            payload = None
        self._arrival.set_motor(payload, self.get_clock().now().nanoseconds)

    def _publish_arrivals(self) -> None:
        now = self.get_clock().now().nanoseconds
        for station, publisher in self._arrival_publishers.items():
            publisher.publish(String(data=json.dumps(
                self._arrival.snapshot(station, now), separators=(',', ':'), allow_nan=False)))

    def _update_arrivals(self, message, detections, width, height, spacing_valid, image=None):
        if not spacing_valid:
            self._arrival.invalidate('UNSAFE_STATION_SPACING')
        else:
            scale = 960.0 / width
            observations = {}
            for name, station in self._stations.items():
                stop_px = line_position_px(station.line, width, height)
                candidates = []
                for detection in detections:
                    distance = station_distance_px(
                        detection.trailing_edge_px, stop_px, self._travel_direction) * scale
                    if abs(distance) <= self._arrival.tolerance_px:
                        points = detection.points
                        # Never qualify an image-clipped board as arrived.
                        if (np.min(points[:, 0]) <= 0 or np.max(points[:, 0]) >= width-1
                                or np.min(points[:, 1]) <= 0 or np.max(points[:, 1]) >= height-1):
                            candidates.append([float('nan')]*5)
                            continue
                        candidates.append([distance, detection.center_px[0]*scale,
                                           detection.center_px[1]*scale,
                                           float(np.ptp(points[:, 0]))*scale,
                                           float(np.ptp(points[:, 1]))*scale])
                observations[name] = candidates
            stamp = message.header.stamp.sec*1_000_000_000 + message.header.stamp.nanosec
            # Calibrated belt interior across both station footprints. The wider
            # detector search includes rails/tools and is not empty-belt evidence.
            bounds = getattr(self, '_empty_belt_region', None)
            ignored_upstream_ids = set()
            ignored_upstream_polygons = []
            if (bounds and self._travel_direction in ('positive_x', 'negative_x')
                    and all(s.line.axis == 'x' for s in self._stations.values())):
                assembly_stop_px = line_position_px(
                    self._stations['assembly'].line, width, height
                )
                upstream_margin_px = float(
                    getattr(self, '_empty_upstream_margin_px', 5.0)
                )
                for detection in detections:
                    points = np.asarray(detection.points, dtype=np.float32)
                    if (points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 3
                            or not np.isfinite(points).all()
                            or np.min(points[:, 0]) <= 0 or np.max(points[:, 0]) >= width - 1
                            or np.min(points[:, 1]) <= 0 or np.max(points[:, 1]) >= height - 1):
                        continue
                    if self._travel_direction == 'positive_x':
                        fully_upstream = (
                            assembly_stop_px - float(detection.trailing_edge_px)
                            >= upstream_margin_px
                        )
                    else:
                        fully_upstream = (
                            float(detection.trailing_edge_px) - assembly_stop_px
                            >= upstream_margin_px
                        )
                    if fully_upstream:
                        ignored_upstream_ids.add(id(detection))
                        ignored_upstream_polygons.append(points)
            clear = bool(
                bounds and self._travel_direction == 'positive_x'
                and all(s.line.axis == 'x' for s in self._stations.values())
                and clear_belt_region(
                    image, **bounds, ignore_polygons=ignored_upstream_polygons
                )
            )
            if clear and any(
                    id(detection) not in ignored_upstream_ids
                    and np.max(detection.points[:, 0]) >= bounds['x_start'] * width
                    and np.min(detection.points[:, 0]) <= bounds['x_end'] * width
                    for detection in detections):
                clear = False
            self._arrival.observe(stamp, self.get_clock().now().nanoseconds, observations,
                                  regions_clear=clear)
        self._publish_arrivals()

    def _reject_frame(self, reason: str) -> None:
        self._ready_pub.publish(Bool(data=False))
        self._arrival.invalidate('INVALID_CAMERA_FRAME')
        self._publish_arrivals()
        # Invalid frames break consecutive evidence, but must not clear an
        # already latched station stop or count as a board leaving the scene.
        for station in self._stations.values():
            station.crossing_frames = 0
            station.rearm_frames = 0
        self.get_logger().error(reason, throttle_duration_sec=1.0)

    def _frame_is_fresh(self, message: CompressedImage) -> bool:
        frame_age = timestamp_age_seconds(
            self.get_clock().now().nanoseconds,
            message.header.stamp.sec,
            message.header.stamp.nanosec,
        )
        if not np.isfinite(frame_age) or frame_age > self._max_frame_age_seconds:
            # A delayed frame must not advance stop-line or arrival evidence.
            # Ignore it without toggling the status bit: a short DDS scheduling
            # delay is not itself a motion fault.  The remote controller keeps
            # an independent bounded motion deadline.
            self._arrival.invalidate('STALE_CAMERA_FRAME')
            self._publish_arrivals()
            for station in self._stations.values():
                station.crossing_frames = 0
                station.rearm_frames = 0
            self.get_logger().warning(
                f'Skipping stale S22 control frame: age={frame_age:.3f}s '
                f'> {self._max_frame_age_seconds:.3f}s',
                throttle_duration_sec=1.0,
            )
            return False
        return True

    def _image_cb(self, message: CompressedImage) -> None:
        marks = [('entry', time.monotonic())]
        try:
            ConveyorStopLine._process_image(self, message, marks)
        finally:
            marks.append(('exit', time.monotonic()))
            if marks[-1][1]-marks[0][1] > .075:
                stages = {b[0]: round((b[1]-a[1])*1000, 2)
                          for a, b in zip(marks, marks[1:])}
                self.get_logger().warning('S22 slow callback ms: ' + json.dumps(stages))

    def _process_image(self, message: CompressedImage, marks) -> None:
        if not self._frame_is_fresh(message):
            return

        encoded = np.frombuffer(message.data, dtype=np.uint8)
        try:
            image = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if encoded.size else None
        except cv2.error:
            image = None
        if image is None:
            self._reject_frame('Failed to decode camera2 compressed frame')
            return

        # Detection, UI drawing, and JPEG output all use the final 960 px
        # frame. Drawing at 1280 and then shrinking the completed overlay
        # doubled the per-frame work and let the monitor lag behind the live
        # stop decision without adding any detail to the 960 px output.
        processing_image = image
        if (
            self._processing_max_width
            and processing_image.shape[1] > self._processing_max_width
        ):
            scale = self._processing_max_width / float(processing_image.shape[1])
            processing_image = cv2.resize(
                processing_image,
                (
                    self._processing_max_width,
                    max(1, int(round(processing_image.shape[0] * scale))),
                ),
                interpolation=cv2.INTER_AREA,
            )
        display_image = processing_image

        height, width = processing_image.shape[:2]
        marks.append(("decode_resize", time.monotonic()))
        detections = detect_dark_boards(
            processing_image,
            search_bounds=self._search_bounds,
            **self._detector_settings,
        )
        marks.append(("detect", time.monotonic()))
        if any(
            not np.isfinite(detection.trailing_edge_px)
            or not np.isfinite(detection.travel_length_px)
            or detection.travel_length_px <= 0.0
            or not np.all(np.isfinite(detection.points))
            or not np.all(np.isfinite(detection.center_px))
            for detection in detections
        ):
            self._reject_frame('Rejecting invalid S22 board geometry')
            return
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

        # A frame can expire during decode/detection. Do not use it for control
        # evidence just because it was fresh at callback entry.
        if not self._frame_is_fresh(message):
            return

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

        # Publish all control-critical messages before drawing the dashboard
        # or encoding its JPEG. UI load and slow viewers must never postpone
        # the physical stop trigger.
        assembly = self._stations['assembly']
        assembly_detection, assembly_distance = station_results['assembly']
        assembly_telemetry = self._publish_station(
            assembly,
            assembly_detection,
            assembly_distance,
            spacing_valid,
            message.header,
            width,
            height,
            legacy=True,
            defer_optional=True,
        )
        inspection = self._stations['inspection']
        inspection_detection, inspection_distance = station_results[
            'inspection'
        ]
        inspection_telemetry = self._publish_station(
            inspection,
            inspection_detection,
            inspection_distance,
            spacing_valid,
            message.header,
            width,
            height,
            legacy=False,
            defer_optional=True,
        )
        if hasattr(self, '_telemetry_queue'):
            self._enqueue_station_telemetry(
                (assembly_telemetry, inspection_telemetry)
            )
        self._board_count_pub.publish(Int32(data=len(detections)))
        self._spacing_valid_pub.publish(Bool(data=spacing_valid))
        self._spacing_ratio_pub.publish(Float32(data=float(spacing_ratio)))
        self._ready_pub.publish(Bool(data=spacing_valid))
        marks.append(("control_publish", time.monotonic()))
        self._update_arrivals(message, detections, width, height, spacing_valid, processing_image)
        marks.append(("arrival_publish", time.monotonic()))

        if np.isfinite(spacing_ratio):
            self._last_spacing_ratio = spacing_ratio

        if self._image_pub.get_subscription_count() <= 0:
            return
        # At most one render is outstanding: never queue old dashboard frames.
        if self._render_future is not None:
            if not self._render_future.done():
                return
            try:
                self._render_future.result()
            except Exception as exc:
                self.get_logger().warning(f'Overlay rendering failed: {type(exc).__name__}')
        now = time.monotonic()
        if now - self._last_annotated_at < self._annotated_period:
            return
        self._last_annotated_at = now
        # Freeze the station state so rendering cannot race the next control frame.
        renderer = copy.copy(self)
        renderer._stations = copy.deepcopy(self._stations)
        renderer._visual_tracks = copy.deepcopy(self._visual_tracks)
        renderer._last_annotated_at = 0.0
        self._render_future = self._render_executor.submit(
            renderer._render_overlay, message, display_image, detections,
            station_geometry, station_results, spacing_valid, spacing_ratio,
            separation_px, required_spacing_px, width, height)

    def _render_overlay(self, message, display_image, detections, station_geometry,
                        station_results, spacing_valid, spacing_ratio,
                        separation_px, required_spacing_px, width, height):
        # The overlay is observability, not control. Skip all drawing when no
        # one watches it and cap it independently when a viewer is connected.
        if self._image_pub.get_subscription_count() <= 0:
            self._visual_tracks = []
            return
        render_started_at = time.monotonic()
        if (
            self._last_annotated_at > 0.0
            and render_started_at - self._last_annotated_at
            < self._annotated_period
        ):
            return
        if render_started_at - self._last_annotated_at > 1.0:
            self._visual_tracks = []
        self._last_annotated_at = render_started_at
        display_detections = self._update_visual_tracks(detections)

        display_station_results = {}
        for name, station in self._stations.items():
            _, _, stop_px = station_geometry[name]
            display_relevant = closest_detection_to_station(
                display_detections, stop_px, self._travel_direction
            )
            _, live_distance = station_results[name]
            if np.isfinite(live_distance):
                display_distance = live_distance
            elif display_relevant is not None:
                display_distance = station_distance_px(
                    display_relevant.trailing_edge_px,
                    stop_px,
                    self._travel_direction,
                )
            else:
                display_distance = float('nan')
            display_station_results[name] = (
                display_relevant,
                display_distance,
            )

        display_spacing_ratio = (
            spacing_ratio
            if np.isfinite(spacing_ratio)
            else self._last_spacing_ratio
        )

        display_height, display_width = display_image.shape[:2]
        x_scale = display_width / float(width)
        y_scale = display_height / float(height)
        overlay = display_image.copy()

        for detection in display_detections:
            nearest_station = min(
                self._stations.values(),
                key=lambda station: abs(
                    station_distance_px(
                        detection.trailing_edge_px,
                        station_geometry[station.name][2],
                        self._travel_direction,
                    )
                ),
            )
            points = np.rint(
                detection.points * np.asarray((x_scale, y_scale))
            ).astype(np.int32)
            cv2.polylines(
                overlay,
                [points],
                True,
                nearest_station.color,
                1,
                cv2.LINE_AA,
            )
            center = (
                int(round(detection.center_px[0] * x_scale)),
                int(round(detection.center_px[1] * y_scale)),
            )
            cv2.drawMarker(
                overlay,
                center,
                (255, 255, 255),
                cv2.MARKER_CROSS,
                max(8, int(round(10 * x_scale))),
                1,
                cv2.LINE_AA,
            )

        for name, station in self._stations.items():
            point1, point2 = normalized_line_to_pixels(
                station.line, display_width, display_height
            )
            self._draw_station_line(overlay, station, point1, point2)
            relevant, _ = display_station_results[name]
            if relevant is not None:
                if station.line.axis == 'x':
                    marker_point = (
                        int(round(relevant.trailing_edge_px * x_scale)),
                        int(round(relevant.center_px[1] * y_scale)),
                    )
                else:
                    marker_point = (
                        int(round(relevant.center_px[0] * x_scale)),
                        int(round(relevant.trailing_edge_px * y_scale)),
                    )
                cv2.drawMarker(
                    overlay,
                    marker_point,
                    station.color,
                    cv2.MARKER_DIAMOND,
                    max(8, int(round(9 * x_scale))),
                    1,
                    cv2.LINE_AA,
                )

        self._draw_dashboard(
            overlay,
            display_detections,
            display_station_results,
            spacing_valid,
            display_spacing_ratio,
            separation_px,
            required_spacing_px,
        )

        if (
            self._annotated_max_width
            and overlay.shape[1] > self._annotated_max_width
        ):
            scale = self._annotated_max_width / float(overlay.shape[1])
            overlay = cv2.resize(
                overlay,
                (
                    self._annotated_max_width,
                    int(round(overlay.shape[0] * scale)),
                ),
                interpolation=cv2.INTER_AREA,
            )

        success, output = cv2.imencode(
            '.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        if not success:
            self.get_logger().warning(
                'Could not encode the optional stop-line overlay',
                throttle_duration_sec=3.0,
            )
            return

        annotated = CompressedImage()
        annotated.header = message.header
        annotated.format = 'jpeg'
        annotated.data = output.tobytes()
        self._image_pub.publish(annotated)

    def destroy_node(self):
        self._telemetry_stop.set()
        if self._telemetry_thread is not None:
            self._telemetry_thread.join(timeout=0.25)
        self._render_executor.shutdown(wait=True, cancel_futures=True)
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ConveyorStopLine()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
