from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
import vision_server.conveyor_roi as roi_module
from vision_server.conveyor_controller import (
    bounded_heartbeat_timeout,
    signed_speed,
    station_trigger_topic,
)
from vision_server.conveyor_roi import (
    BoardDetection,
    ConveyorStopLine,
    detect_dark_board,
    detect_dark_boards,
    fit_dominant_body_box,
    normalized_line_to_pixels,
    NormalizedLine,
    StopStation,
    smooth_board_detection,
    spacing_is_safe,
    station_separation_px,
    timestamp_age_seconds,
    trigger_boundary_crossed,
    validate_station_layout,
)
import yaml


def _board_detection(center, long_length, short_length, angle_deg, trailing_edge):
    radians = np.radians(angle_deg)
    long_axis = np.array((np.cos(radians), np.sin(radians)), dtype=np.float32)
    short_axis = np.array((-long_axis[1], long_axis[0]), dtype=np.float32)
    center_array = np.asarray(center, dtype=np.float32)
    half_long = long_axis * (long_length * 0.5)
    half_short = short_axis * (short_length * 0.5)
    points = np.asarray(
        [
            center_array - half_long - half_short,
            center_array + half_long - half_short,
            center_array + half_long + half_short,
            center_array - half_long + half_short,
        ],
        dtype=np.float32,
    )
    return BoardDetection(
        points=points,
        center_px=tuple(float(value) for value in center),
        trailing_edge_px=float(trailing_edge),
        travel_length_px=float(long_length),
        area_fraction=0.03,
        aspect_ratio=float(long_length / short_length),
        rectangularity=0.9,
        long_axis_angle_deg=float(angle_deg),
    )


def test_physical_belt_forward_can_use_robot_negative_x():
    assert signed_speed(0.10, 'negative_x') == pytest.approx(-0.10)


def test_robot_positive_x_direction_is_preserved():
    assert signed_speed(0.05, 'positive_x') == pytest.approx(0.05)


def test_vision_heartbeat_timeout_is_bounded_for_motion_safety():
    assert bounded_heartbeat_timeout(0.25) == pytest.approx(0.25)
    with pytest.raises(ValueError, match='heartbeat timeout'):
        bounded_heartbeat_timeout(0.05)
    with pytest.raises(ValueError, match='heartbeat timeout'):
        bounded_heartbeat_timeout(1.5)


def test_stale_control_frame_age_uses_source_timestamp():
    now_ns = 10_500_000_000
    assert timestamp_age_seconds(now_ns, 10, 400_000_000) == pytest.approx(0.1)
    assert timestamp_age_seconds(now_ns, 0, 0) == float('inf')
    # Missing/future source times cannot prove that a control image is fresh.
    assert timestamp_age_seconds(now_ns, 11, 0) == float('inf')


def test_station_trigger_topics_are_explicit():
    assert station_trigger_topic('assembly') == (
        '/vision/conveyor/assembly/stop_trigger'
    )
    assert station_trigger_topic('inspection') == (
        '/vision/conveyor/inspection/stop_trigger'
    )
    with pytest.raises(ValueError):
        station_trigger_topic('unknown')


def test_stop_trigger_can_lead_visible_line_by_one_frame():
    assert not trigger_boundary_crossed(6.1, 6.0)
    assert trigger_boundary_crossed(6.0, 6.0)
    assert trigger_boundary_crossed(-1.0, 6.0)
    assert not trigger_boundary_crossed(float('nan'), 6.0)
    with pytest.raises(ValueError, match='trigger lead'):
        trigger_boundary_crossed(0.0, -1.0)


def test_vertical_stop_line_at_seventy_percent():
    line = NormalizedLine(axis='x', position=0.70, span_start=0.18, span_end=0.82)
    assert normalized_line_to_pixels(line, 1920, 1080) == (
        (1343, 194),
        (1343, 885),
    )


def test_horizontal_stop_line_is_supported():
    line = NormalizedLine(axis='y', position=0.50, span_start=0.10, span_end=0.90)
    assert normalized_line_to_pixels(line, 100, 50) == ((10, 24), (89, 24))


def test_invalid_line_axis_is_rejected():
    line = NormalizedLine(axis='z', position=0.5, span_start=0.1, span_end=0.9)
    with pytest.raises(ValueError):
        normalized_line_to_pixels(line, 1920, 1080)


def test_dark_horizontal_board_trailing_edge_is_detected():
    image = np.full((600, 1000, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (380, 220), (780, 480), (25, 25, 25), -1)
    detection = detect_dark_board(
        image,
        search_bounds=(0.25, 0.90, 0.20, 0.90),
        dark_threshold=105,
        close_kernel_px=13,
        min_area_fraction=0.05,
        max_area_fraction=0.30,
        min_aspect_ratio=1.10,
        max_aspect_ratio=2.20,
        min_rectangularity=0.60,
        travel_direction='positive_x',
    )
    assert detection is not None
    assert detection.trailing_edge_px == pytest.approx(380.0, abs=1.0)
    assert detection.travel_length_px == pytest.approx(400.0, abs=2.0)


def test_two_boards_can_be_detected_independently():
    image = np.full((600, 1200, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (100, 210), (400, 390), (25, 25, 25), -1)
    cv2.rectangle(image, (700, 210), (1000, 390), (25, 25, 25), -1)
    detections = detect_dark_boards(
        image,
        search_bounds=(0.02, 0.98, 0.20, 0.90),
        dark_threshold=105,
        close_kernel_px=13,
        min_area_fraction=0.03,
        max_area_fraction=0.30,
        min_aspect_ratio=1.10,
        max_aspect_ratio=2.20,
        min_rectangularity=0.60,
        travel_direction='positive_x',
    )

    assert len(detections) == 2
    assert [item.trailing_edge_px for item in detections] == pytest.approx(
        [100.0, 700.0], abs=1.0
    )


def test_fixture_handle_does_not_shift_main_body_center():
    contour = np.array(
        [
            [200, 150],
            [340, 150],
            [340, 100],
            [460, 100],
            [460, 150],
            [600, 150],
            [600, 450],
            [200, 450],
        ],
        dtype=np.int32,
    ).reshape(-1, 1, 2)
    points, center = fit_dominant_body_box(contour, span_ratio=0.68)

    assert center == pytest.approx((400.0, 300.0), abs=2.0)
    assert np.min(points[:, 1]) == pytest.approx(150.0, abs=2.0)
    assert np.max(points[:, 1]) == pytest.approx(450.0, abs=2.0)
    edges = np.roll(points, -1, axis=0) - points
    assert abs(float(np.dot(edges[0], edges[1]))) < 1e-3
    assert np.linalg.norm(edges[0]) == pytest.approx(
        np.linalg.norm(edges[2]), abs=1e-3
    )
    assert np.linalg.norm(edges[1]) == pytest.approx(
        np.linalg.norm(edges[3]), abs=1e-3
    )


def test_fixture_handle_is_rejected_after_ninety_degree_rotation():
    contour = np.array(
        [
            [200, 150],
            [340, 150],
            [340, 100],
            [460, 100],
            [460, 150],
            [600, 150],
            [600, 450],
            [200, 450],
        ],
        dtype=np.float32,
    )
    rotation = cv2.getRotationMatrix2D((400, 275), 90.0, 1.0)
    contour = cv2.transform(contour[None, :, :], rotation)[0]

    points, center = fit_dominant_body_box(contour)

    # The physical PCB body is x=275..575, y=75..475 after rotation; the
    # handle must not move the reported centre or extend the body box.
    assert center == pytest.approx((425.0, 275.0), abs=2.0)
    assert np.min(points[:, 0]) == pytest.approx(275.0, abs=3.0)
    assert np.max(points[:, 0]) == pytest.approx(575.0, abs=3.0)
    assert np.min(points[:, 1]) == pytest.approx(75.0, abs=3.0)
    assert np.max(points[:, 1]) == pytest.approx(475.0, abs=3.0)


def test_perspective_board_edges_ignore_grip_tab_and_dark_belt_guide():
    contour = np.asarray(
        [
            [212, 164],
            [191, 251],
            [292, 276],
            [292, 286],
            [262, 286],
            [262, 300],
            [280, 300],
            [284, 291],
            [308, 293],
            [304, 276],
            [325, 192],
            [294, 184],
            [283, 169],
            [271, 165],
            [239, 170],
        ],
        dtype=np.float32,
    )
    mask = np.zeros((360, 400), dtype=np.uint8)
    cv2.fillPoly(mask, [np.rint(contour).astype(np.int32)], 255)
    dense_contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    points, _ = fit_dominant_body_box(dense_contours[0])
    expected_corners = np.asarray(
        [[212, 164], [191, 251], [304, 276], [325, 192]], dtype=np.float32
    )

    for expected in expected_corners:
        assert np.min(np.linalg.norm(points - expected, axis=1)) < 5.0


def test_display_smoothing_keeps_quad_convex_and_live_stop_edge():
    previous = _board_detection((100, 200), 120, 80, 0, 40)
    current = _board_detection((108, 196), 128, 76, 8, 47)

    result = smooth_board_detection(
        previous,
        current,
        center_alpha=0.75,
        shape_alpha=0.25,
    )

    assert result.center_px == pytest.approx((106.0, 197.0), abs=1e-3)
    assert result.long_axis_angle_deg == pytest.approx(2.0, abs=1e-3)
    assert result.trailing_edge_px == pytest.approx(47.0)
    edges = np.roll(result.points, -1, axis=0) - result.points
    assert cv2.isContourConvex(np.rint(result.points).astype(np.int32))
    assert np.linalg.norm(edges[0]) == pytest.approx(
        np.linalg.norm(edges[2]), abs=1e-3
    )
    assert np.linalg.norm(edges[1]) == pytest.approx(
        np.linalg.norm(edges[3]), abs=1e-3
    )


def test_display_smoothing_preserves_a_perspective_quadrilateral():
    previous = _board_detection((100, 200), 120, 80, 0, 40)
    current = _board_detection((100, 200), 120, 80, 0, 41)
    perspective_points = np.asarray(
        [[42, 158], [161, 163], [157, 241], [40, 237]], dtype=np.float32
    )
    current = BoardDetection(
        points=perspective_points,
        center_px=tuple(np.mean(perspective_points, axis=0)),
        trailing_edge_px=current.trailing_edge_px,
        travel_length_px=current.travel_length_px,
        area_fraction=current.area_fraction,
        aspect_ratio=current.aspect_ratio,
        rectangularity=current.rectangularity,
        long_axis_angle_deg=current.long_axis_angle_deg,
    )

    result = smooth_board_detection(
        previous,
        current,
        center_alpha=1.0,
        shape_alpha=1.0,
    )

    assert min(
        np.max(np.abs(np.roll(result.points, shift, axis=0) - perspective_points))
        for shift in range(4)
    ) == pytest.approx(0.0)


def test_display_angle_smoothing_wraps_across_obb_boundary():
    previous = _board_detection((100, 200), 120, 80, 89, 40)
    current = _board_detection((100, 200), 120, 80, -89, 41)

    result = smooth_board_detection(
        previous,
        current,
        center_alpha=1.0,
        shape_alpha=0.5,
    )

    assert abs(result.long_axis_angle_deg) == pytest.approx(90.0, abs=1e-3)
    assert result.trailing_edge_px == pytest.approx(41.0)


def test_visual_tracker_holds_three_missing_frames_before_hiding_board():
    tracker = SimpleNamespace(
        _visual_tracks=[],
        _travel_direction='positive_x',
        _track_match_distance_px=80.0,
        _track_center_alpha=0.75,
        _track_shape_alpha=0.25,
        _track_hold_frames=3,
    )
    detection = _board_detection((100, 200), 120, 80, 5, 40)

    assert len(ConveyorStopLine._update_visual_tracks(tracker, [detection])) == 1
    assert len(ConveyorStopLine._update_visual_tracks(tracker, [])) == 1
    assert len(ConveyorStopLine._update_visual_tracks(tracker, [])) == 1
    assert len(ConveyorStopLine._update_visual_tracks(tracker, [])) == 1
    assert ConveyorStopLine._update_visual_tracks(tracker, []) == []


def test_y_axis_travel_uses_horizontal_trailing_edge():
    image = np.full((800, 600, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (210, 150), (390, 450), (25, 25, 25), -1)
    detection = detect_dark_board(
        image,
        search_bounds=(0.20, 0.90, 0.05, 0.90),
        dark_threshold=105,
        close_kernel_px=13,
        min_area_fraction=0.05,
        max_area_fraction=0.30,
        min_aspect_ratio=1.10,
        max_aspect_ratio=2.20,
        min_rectangularity=0.60,
        travel_direction='positive_y',
    )
    assert detection is not None
    assert detection.trailing_edge_px == pytest.approx(150.0, abs=1.0)
    assert detection.travel_length_px == pytest.approx(300.0, abs=2.0)


def test_objects_outside_fixed_conveyor_band_are_ignored():
    image = np.full((1000, 1400, 3), 230, dtype=np.uint8)
    cv2.rectangle(image, (300, 450), (700, 700), (25, 25, 25), -1)
    # TurtleBot-like dark rectangular body below the conveyor belt band.
    cv2.rectangle(image, (850, 790), (1250, 980), (25, 25, 25), -1)
    detections = detect_dark_boards(
        image,
        search_bounds=(0.02, 0.98, 0.42, 0.76),
        dark_threshold=105,
        close_kernel_px=13,
        min_area_fraction=0.03,
        max_area_fraction=0.30,
        min_aspect_ratio=1.05,
        max_aspect_ratio=2.20,
        min_rectangularity=0.78,
        travel_direction='positive_x',
    )
    assert len(detections) == 1
    assert detections[0].center_px == pytest.approx((500.0, 575.0), abs=2.0)


def test_shipped_detector_separates_two_pcbs_from_the_gray_belt():
    config_path = Path(__file__).parents[1] / 'config' / 'conveyor_roi.yaml'
    config = yaml.safe_load(config_path.read_text())['conveyor_roi']
    detector = config['board_detection']

    # Dark clutter exists above and below the belt just like the current S22
    # view. Only the two near-black PCB bodies inside the gray belt band may
    # pass the shipped ROI and shape filters.
    image = np.full((540, 960, 3), 25, dtype=np.uint8)
    cv2.rectangle(image, (0, 140), (959, 340), (145, 145, 145), -1)
    cv2.rectangle(image, (316, 182), (419, 263), (25, 25, 25), -1)
    cv2.rectangle(image, (545, 182), (649, 263), (20, 20, 20), -1)
    # Fixture handles and light assembled components.
    cv2.rectangle(image, (355, 166), (380, 183), (25, 25, 25), -1)
    cv2.rectangle(image, (584, 166), (610, 183), (20, 20, 20), -1)
    cv2.rectangle(image, (565, 195), (628, 209), (220, 220, 220), -1)

    detections = detect_dark_boards(
        image,
        search_bounds=(
            detector['search_x_start'],
            detector['search_x_end'],
            detector['search_y_start'],
            detector['search_y_end'],
        ),
        dark_threshold=detector['dark_threshold'],
        close_kernel_px=detector['close_kernel_px'],
        min_area_fraction=detector['min_area_fraction'],
        max_area_fraction=detector['max_area_fraction'],
        min_aspect_ratio=detector['min_aspect_ratio'],
        max_aspect_ratio=detector['max_aspect_ratio'],
        min_rectangularity=detector['min_rectangularity'],
        travel_direction=detector['travel_direction'],
        body_span_ratio=detector['body_span_ratio'],
        body_extension_ratio=detector['body_extension_ratio'],
        body_extension_fraction=detector['body_extension_fraction'],
    )

    assert len(detections) == 2
    assert [item.trailing_edge_px for item in detections] == pytest.approx(
        [316.0, 545.0], abs=2.0
    )


def test_inspection_line_must_be_downstream_and_well_separated():
    assembly = NormalizedLine('x', 0.30, 0.20, 0.90)
    inspection = NormalizedLine('x', 0.75, 0.20, 0.90)
    assert validate_station_layout(
        assembly, inspection, 'positive_x', 0.25
    ) == pytest.approx(0.45)
    assert station_separation_px(assembly, inspection, 1001, 600) == pytest.approx(
        450.0
    )

    with pytest.raises(ValueError, match='downstream'):
        validate_station_layout(inspection, assembly, 'positive_x', 0.25)
    with pytest.raises(ValueError, match='too close'):
        validate_station_layout(
            assembly,
            NormalizedLine('x', 0.40, 0.20, 0.90),
            'positive_x',
            0.25,
        )


def test_negative_direction_reverses_station_order():
    assembly = NormalizedLine('x', 0.80, 0.20, 0.90)
    inspection = NormalizedLine('x', 0.30, 0.20, 0.90)
    assert validate_station_layout(
        assembly, inspection, 'negative_x', 0.25
    ) == pytest.approx(0.50)


def test_station_spacing_requires_one_board_plus_clearance():
    safe, ratio, required = spacing_is_safe(690.0, 500.0, 1.10, 20.0)
    assert safe
    assert ratio == pytest.approx(1.38)
    assert required == pytest.approx(570.0)

    safe, _, required = spacing_is_safe(550.0, 500.0, 1.10, 20.0)
    assert not safe
    assert required == pytest.approx(570.0)


def test_shipped_dual_station_config_is_ordered_and_separated():
    config_path = Path(__file__).parents[1] / 'config' / 'conveyor_roi.yaml'
    config = yaml.safe_load(config_path.read_text())['conveyor_roi']
    lines = config['stop_lines']
    assembly = NormalizedLine(**lines['assembly'])
    inspection = NormalizedLine(**lines['inspection'])
    spacing = config['station_spacing']

    separation = validate_station_layout(
        assembly,
        inspection,
        config['board_detection']['travel_direction'],
        spacing['minimum_normalized_separation'],
    )
    assert separation == pytest.approx(0.32219772)
    assert spacing['minimum_board_lengths'] >= 1.0


@pytest.mark.parametrize('now,sec,nsec', [
    (0, 0, 0), (10_000_000_000, -1, 0),
    (10_000_000_000, 9, -1), (10_000_000_000, 9, 1_000_000_000),
    (float('nan'), 9, 0), (10_000_000_000, float('inf'), 0),
    (10_000_000_000, 9, float('nan')),
])
def test_invalid_source_timestamp_has_unusable_age(now, sec, nsec):
    assert timestamp_age_seconds(now, sec, nsec) == float('inf')


class FrameHarness:
    """Plain Python callback state with in-memory publishers; no ROS init."""

    _image_cb = ConveyorStopLine._image_cb
    _reject_frame = ConveyorStopLine._reject_frame
    _frame_is_fresh = ConveyorStopLine._frame_is_fresh
    _update_station_state = ConveyorStopLine._update_station_state

    def __init__(self):
        self._stations = {
            name: StopStation(name, name, NormalizedLine('x', pos, 0.1, 0.9), (0, 0, 0))
            for name, pos in [('assembly', 0.2), ('inspection', 0.8)]
        }
        self._ready_pub = SimpleNamespace(publish=Mock())
        self._spacing_valid_pub = SimpleNamespace(publish=Mock())
        self._spacing_ratio_pub = SimpleNamespace(publish=Mock())
        self._board_count_pub = SimpleNamespace(publish=Mock())
        self._image_pub = SimpleNamespace(get_subscription_count=lambda: 0)
        self._publish_station = Mock()
        self._processing_max_width = 0
        self._max_frame_age_seconds = 0.15
        self._search_bounds = (0.0, 1.0, 0.0, 1.0)
        self._detector_settings = {}
        self._travel_direction = 'positive_x'
        self._minimum_board_lengths = 1.1
        self._minimum_clearance_px = 20.0
        self._stable_frames_required = 2
        self._rearm_frames_required = 2
        self._reset_missing_frames = 15
        self._trigger_lead_px = 20.0
        self._rearm_margin_px = 30.0
        self.now_ns = 10_000_000_000
        self.get_clock = lambda: SimpleNamespace(
            now=lambda: SimpleNamespace(nanoseconds=self.now_ns)
        )
        self.get_logger = Mock(return_value=Mock())


@pytest.fixture
def frame_harness(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('offline conveyor tests must never initialize ROS')

    monkeypatch.setattr(roi_module.rclpy, 'init', forbidden)
    monkeypatch.setattr(roi_module.Node, '__init__', forbidden)
    monkeypatch.setattr(roi_module, 'detect_dark_boards', Mock(return_value=[]))
    return FrameHarness()


def synthetic_frame():
    success, data = cv2.imencode('.jpg', np.full((40, 60, 3), 230, dtype=np.uint8))
    assert success
    return SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=10, nanosec=0)),
        data=data.tobytes(),
    )


@pytest.mark.parametrize('stamp', [(0, 0), (11, 0), (9, 0)])
def test_unverifiable_or_stale_frame_never_refreshes_control(frame_harness, stamp):
    message = synthetic_frame()
    message.header.stamp.sec, message.header.stamp.nanosec = stamp
    frame_harness._image_cb(message)
    assert frame_harness._ready_pub.publish.call_args.args[0].data is False
    frame_harness._publish_station.assert_not_called()
    roi_module.detect_dark_boards.assert_not_called()


@pytest.mark.parametrize('failure', ['empty', 'decode_none', 'decode_error'])
def test_decode_failure_breaks_consecutive_evidence_but_preserves_latched_stop(frame_harness, monkeypatch, failure):
    message = synthetic_frame()
    station = frame_harness._stations['assembly']
    station.trigger_latched = True
    station.crossing_frames = station.rearm_frames = 1
    if failure == 'empty':
        message.data = b''
    elif failure == 'decode_none':
        monkeypatch.setattr(roi_module.cv2, 'imdecode', Mock(return_value=None))
    else:
        monkeypatch.setattr(roi_module.cv2, 'imdecode', Mock(side_effect=cv2.error('bad frame')))
    frame_harness._image_cb(message)
    assert station.trigger_latched
    assert station.crossing_frames == station.rearm_frames == 0
    assert frame_harness._ready_pub.publish.call_args.args[0].data is False
    frame_harness._publish_station.assert_not_called()


def test_frame_expiring_during_detection_cannot_publish_fresh_ready(frame_harness):
    def delayed_detection(*args, **kwargs):
        frame_harness.now_ns += 151_000_000
        return []

    roi_module.detect_dark_boards.side_effect = delayed_detection
    frame_harness._image_cb(synthetic_frame())
    assert frame_harness._ready_pub.publish.call_args.args[0].data is False
    frame_harness._publish_station.assert_not_called()


@pytest.mark.parametrize('field,bad', [
    ('trailing_edge_px', float('nan')),
    ('travel_length_px', float('inf')), ('travel_length_px', 0.0),
    ('center_px', (float('nan'), 20.0)),
    ('points', np.full((4, 2), float('nan'))),
])
def test_invalid_detection_cannot_authorize_motion(frame_harness, field, bad):
    detection = _board_detection((25, 20), 10, 8, 0, 20)
    roi_module.detect_dark_boards.return_value = [replace(detection, **{field: bad})]
    frame_harness._image_cb(synthetic_frame())
    assert frame_harness._ready_pub.publish.call_args.args[0].data is False
    frame_harness._publish_station.assert_not_called()


def test_fresh_empty_belt_keeps_existing_ready_and_station_heartbeat_semantics(frame_harness):
    frame_harness._image_cb(synthetic_frame())
    assert frame_harness._ready_pub.publish.call_args.args[0].data is True
    assert frame_harness._publish_station.call_count == 2
    assert frame_harness._board_count_pub.publish.call_args.args[0].data == 0
