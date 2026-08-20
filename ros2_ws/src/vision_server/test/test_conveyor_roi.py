from pathlib import Path

import cv2
import numpy as np
import pytest
from vision_server.conveyor_controller import signed_speed, station_trigger_topic
from vision_server.conveyor_roi import (
    detect_dark_board,
    detect_dark_boards,
    fit_dominant_body_box,
    normalized_line_to_pixels,
    NormalizedLine,
    spacing_is_safe,
    station_separation_px,
    validate_station_layout,
)
import yaml


def test_physical_belt_forward_can_use_robot_negative_x():
    assert signed_speed(0.10, 'negative_x') == pytest.approx(-0.10)


def test_robot_positive_x_direction_is_preserved():
    assert signed_speed(0.05, 'positive_x') == pytest.approx(0.05)


def test_station_trigger_topics_are_explicit():
    assert station_trigger_topic('assembly') == (
        '/vision/conveyor/assembly/stop_trigger'
    )
    assert station_trigger_topic('inspection') == (
        '/vision/conveyor/inspection/stop_trigger'
    )
    with pytest.raises(ValueError):
        station_trigger_topic('unknown')


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
        min_aspect_ratio=1.25,
        max_aspect_ratio=1.90,
        min_rectangularity=0.78,
        travel_direction='positive_x',
    )
    assert len(detections) == 1
    assert detections[0].center_px == pytest.approx((500.0, 575.0), abs=2.0)


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
    assert separation == pytest.approx(0.40544964)
    assert spacing['minimum_board_lengths'] >= 1.0
