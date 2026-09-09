from pathlib import Path
import json
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from capture_assembly_slot_coordinates import (  # noqa: E402
    apply_component_slot_overrides,
    angle_image_deg,
    board_source_corners,
    ordered_image_quad,
    project_points,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]


def test_image_quad_ordering():
    unordered = np.float32([[0.8, 0.7], [0.2, 0.2], [0.8, 0.2], [0.2, 0.7]])
    ordered = ordered_image_quad(unordered)
    assert np.allclose(
        ordered,
        [[0.2, 0.2], [0.8, 0.2], [0.8, 0.7], [0.2, 0.7]],
    )


def test_current_fixture_maps_plus_x_left_and_plus_y_up():
    destination = np.float32([
        [100.0, 100.0], [500.0, 100.0], [500.0, 420.0], [100.0, 420.0]
    ])
    homography = cv2.getPerspectiveTransform(
        board_source_corners(139.0, 110.0), destination
    )
    center, plus_x, plus_y = project_points(
        homography, [[0.0, 0.0], [20.0, 0.0], [0.0, 20.0]]
    )
    assert plus_x[0] < center[0]
    assert plus_y[1] < center[1]


def test_long_axis_image_angle_tracks_board_mapping():
    destination = np.float32([
        [100.0, 100.0], [500.0, 100.0], [500.0, 420.0], [100.0, 420.0]
    ])
    homography = cv2.getPerspectiveTransform(
        board_source_corners(139.0, 110.0), destination
    )
    assert abs(abs(angle_image_deg(homography, (0.0, 0.0), 0.0)) - 180.0) < 1e-3
    assert abs(angle_image_deg(homography, (0.0, 0.0), 90.0) + 90.0) < 1e-3


def test_physical_overrides_put_inductors_and_smd_in_real_slots():
    layout = json.loads(
        (PROJECT_DIR / "vision_assembly/config/board_layout_from_unity.json")
        .read_text(encoding="utf-8")
    )
    physical = json.loads(
        (PROJECT_DIR / "vision_assembly/config/physical_board.json")
        .read_text(encoding="utf-8")
    )
    merged, applied = apply_component_slot_overrides(layout, physical)
    slots = {item["slot_id"]: item for item in merged["placements"]}

    assert set(applied) == {
        "inductor_01", "inductor_02",
        "smd_capacitor_01", "smd_capacitor_02", "smd_capacitor_03",
        "smd_capacitor_04", "smd_capacitor_05",
    }
    assert slots["inductor_01"]["center_board_mm"] == {
        "x": -59.674, "y": -32.872,
    }
    assert slots["inductor_02"]["center_board_mm"]["y"] == -44.297

    # Agreed numbering: S1 is the only horizontal slot. S2-S5 are the
    # right-side vertical column ordered from bottom to top (+Y).
    assert slots["smd_capacitor_01"]["long_axis_deg_in_board"] == 0.0
    assert slots["smd_capacitor_01"]["nominal_size_mm"]["x"] > \
        slots["smd_capacitor_01"]["nominal_size_mm"]["y"]
    vertical = [slots[f"smd_capacitor_{index:02d}"] for index in range(2, 6)]
    assert all(item["long_axis_deg_in_board"] == 90.0 for item in vertical)
    assert [item["center_board_mm"]["y"] for item in vertical] == sorted(
        item["center_board_mm"]["y"] for item in vertical
    )
