import pytest
import cv2
import numpy as np

from vision_server.conveyor_roi import (
    NormalizedLine,
    detect_dark_board,
    normalized_line_to_pixels,
)


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
