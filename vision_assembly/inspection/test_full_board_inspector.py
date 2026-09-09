from pathlib import Path
import math
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from full_board_inspector import (  # noqa: E402
    apply_projection_and_visibility_policy,
    board_alignment_mask,
    circle_white_fraction,
    detect_dot_corner,
    detect_polarity_dot,
    geometric_rotation_tolerance_deg,
    inspect_inductor_mark,
    inspect_hbm_presence,
    inspect_leg_side,
    slot_geometry,
)


WHITE = {
    "lab_l_min": 130,
    "hsv_s_max": 105,
    "open_kernel_px": 1,
    "dot_min_radius_mm": 0.42,
    "dot_winner_margin_mm": 0.22,
    "dot_geometry_scale": 1.0,
    "dot_anchor_penalty": 0.8,
    "inductor_mark_contrast_min": 7.0,
    "inductor_mark_angle_tolerance_deg": 50.0,
}
LEGS = {
    "minimum_reference_peaks": 8,
    "maximum_reference_peaks": 9,
    "peak_min_distance_px": 9,
    "peak_profile_min": 0.022,
    "left_keep_fraction": 0.9,
    "reference_peak_radius_px": 3,
    "sample_peak_radius_px": 5,
    "missing_evidence_ratio": 0.2,
    "uncertain_evidence_ratio": 0.3,
    "maximum_lateral_shift_mm": 0.7,
    "maximum_extra_width_mm": 0.8,
    "max_profile_shift_px": 6,
    "sample_peak_search_radius_px": 6,
}


def _leg_row(
    missing=None, fallen=None, varied=False,
    vertical_shift=0, horizontal_shift=0,
):
    image = np.zeros((180, 44, 3), dtype=np.uint8)
    for index, center_y in enumerate(range(12, 174, 18), start=1):
        if index == missing:
            continue
        center_x = (33 if index == fallen else 22) + horizontal_shift
        axes = (4 + (index % 2), 3 + ((index + 1) % 2)) if varied else (5, 4)
        cv2.ellipse(
            image, (center_x, center_y + vertical_shift), axes, 0, 0, 360,
            (230, 230, 230), -1, cv2.LINE_AA,
        )
    return image


def test_slot_geometry_applies_verified_s22_axis_mapping():
    placement = {
        "center_board_mm": {"x": 20.0, "y": 10.0},
        "nominal_size_mm": {"x": 10.0, "y": 20.0},
    }
    result = slot_geometry(
        placement, (1100, 1390, 3), (139.0, 110.0),
        {
            "image_x_from_board_x_sign": -1.0,
            "image_y_from_board_y_sign": 1.0,
        },
    )
    assert result == (495.0, 650.0, 100.0, 200.0)


def test_board_alignment_mask_excludes_movable_component_areas():
    layout = {
        "placements": [{
            "center_board_mm": {"x": 0.0, "y": 0.0},
            "nominal_size_mm": {"x": 20.0, "y": 10.0},
        }]
    }
    mask = board_alignment_mask(
        layout, (100, 200, 3), (200.0, 100.0), {}, 2.0
    )
    assert mask[50, 100] == 0
    assert mask[5, 5] == 255


def test_unity_clearance_produces_tight_long_part_rotation_limit():
    limit = geometric_rotation_tolerance_deg([12.13001, 59.9891], [13.13001, 60.9891])
    assert 0.8 < limit < 1.1


def test_leg_blob_size_variation_is_not_a_defect():
    result = inspect_leg_side(
        _leg_row(), _leg_row(varied=True), "right", (0, 0, 44, 180),
        LEGS, WHITE, 10.0,
    )
    assert result.status == "PASS"
    assert not result.missing_indices
    assert not result.fallen_indices


def test_missing_white_leg_fails():
    result = inspect_leg_side(
        _leg_row(), _leg_row(missing=5), "right", (0, 0, 44, 180),
        LEGS, WHITE, 10.0,
    )
    assert result.status == "FAIL"
    assert result.missing_indices == [5]


def test_laterally_fallen_white_leg_fails():
    result = inspect_leg_side(
        _leg_row(), _leg_row(fallen=4), "right", (0, 0, 44, 180),
        LEGS, WHITE, 10.0,
    )
    assert result.status == "FAIL"
    assert result.fallen_indices == [4]


def test_whole_pin_row_vertical_shift_is_registered_before_pin_checks():
    result = inspect_leg_side(
        _leg_row(), _leg_row(vertical_shift=4), "right", (0, 0, 44, 180),
        LEGS, WHITE, 10.0,
    )
    assert result.status == "PASS"
    assert result.profile_shift_px == 4
    assert result.profile_alignment_score > 0.9


def test_profile_registration_does_not_hide_a_missing_pin():
    result = inspect_leg_side(
        _leg_row(), _leg_row(missing=5, vertical_shift=4),
        "right", (0, 0, 44, 180), LEGS, WHITE, 10.0,
    )
    assert result.status == "FAIL"
    assert result.missing_indices == [5]


def test_hbm_common_lateral_projection_shift_is_removed():
    settings = dict(
        LEGS,
        remove_common_lateral_trend=True,
        maximum_lateral_shift_mm=0.9,
    )
    result = inspect_leg_side(
        _leg_row(), _leg_row(horizontal_shift=9),
        "right", (0, 0, 44, 180), settings, WHITE, 10.0,
    )
    assert result.status == "PASS"
    assert max(abs(value) for value in result.lateral_shift_mm) < 0.1


def test_hbm_common_shift_removal_keeps_a_single_fallen_pin_failure():
    settings = dict(
        LEGS,
        remove_common_lateral_trend=True,
        maximum_lateral_shift_mm=0.9,
    )
    result = inspect_leg_side(
        _leg_row(), _leg_row(fallen=4, horizontal_shift=4),
        "right", (0, 0, 44, 180), settings, WHITE, 10.0,
    )
    assert result.status == "FAIL"
    assert result.fallen_indices == [4]


def test_dot_corner_uses_lower_left_absolute_rule():
    image = np.zeros((200, 120, 3), dtype=np.uint8)
    cv2.circle(image, (34, 164), 9, (240, 240, 240), -1, cv2.LINE_AA)
    corner, scores = detect_dot_corner(
        image, (60.0, 100.0, 80.0, 160.0), WHITE, (10.0, 10.0)
    )
    assert corner == "lower_left"
    assert scores["lower_left"] > 0.6


def test_reference_dot_anchor_rejects_larger_external_board_pad():
    geometry = (70.0, 120.0, 90.0, 150.0)
    settings = dict(WHITE, dot_geometry_scale=1.18)
    reference = np.zeros((240, 140, 3), dtype=np.uint8)
    sample = reference.copy()
    cv2.circle(reference, (42, 174), 8, (240, 240, 240), -1, cv2.LINE_AA)
    cv2.circle(sample, (42, 174), 8, (240, 240, 240), -1, cv2.LINE_AA)
    cv2.circle(sample, (101, 198), 10, (240, 240, 240), -1, cv2.LINE_AA)
    reference_detection = detect_polarity_dot(
        reference, geometry, 0.0, settings, (10.0, 10.0)
    )
    reference_xy = reference_detection["normalized_xy"]
    detection = detect_polarity_dot(
        sample,
        geometry,
        0.0,
        settings,
        (10.0, 10.0),
        (abs(reference_xy[0]), abs(reference_xy[1])),
    )
    assert detection["corner"] == "lower_left"
    assert detection["winner_margin"] > 0.0


def test_hbm_presence_uses_both_white_dot_and_center_logo():
    geometry = (60.0, 100.0, 80.0, 150.0)
    settings = dict(
        WHITE,
        dot_geometry_scale=1.18,
        hbm_logo_present_ratio_min=0.3,
        hbm_logo_missing_ratio_max=0.08,
    )
    reference = np.zeros((210, 120, 3), dtype=np.uint8)
    cv2.circle(reference, (36, 154), 8, (240, 240, 240), -1, cv2.LINE_AA)
    cv2.rectangle(reference, (49, 94), (71, 106), (0, 105, 220), -1)
    present = reference.copy()
    missing = np.zeros_like(reference)
    present_check = inspect_hbm_presence(
        reference, present, geometry, geometry, 0.0, settings, (10.0, 10.0)
    )
    missing_check = inspect_hbm_presence(
        reference, missing, geometry, geometry, 0.0, settings, (10.0, 10.0)
    )
    assert present_check.status == "PASS"
    assert missing_check.status == "FAIL"
    assert missing_check.reason == "HBM_DOT_AND_CENTER_LOGO_ABSENT"


def _inductor(mark_side):
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    cv2.circle(image, (60, 60), 40, (235, 235, 235), -1, cv2.LINE_AA)
    x = 43 if mark_side == "left" else 77
    cv2.ellipse(image, (x, 60), (5, 22), 0, 0, 360, (25, 25, 25), -1)
    return image


def test_inductor_black_mark_side_controls_direction():
    area = math.pi * 40.0 * 40.0
    good = inspect_inductor_mark(
        _inductor("left"), (60.0, 60.0, 80.0, 80.0), WHITE, area
    )
    bad = inspect_inductor_mark(
        _inductor("right"), (60.0, 60.0, 80.0, 80.0), WHITE, area
    )
    assert good.status == "PASS"
    assert bad.status == "FAIL"
    assert abs(good.measured["angle_error_deg"]) <= 50.0
    assert abs(bad.measured["angle_error_deg"]) > 50.0


def test_inductor_presence_uses_white_disc_instead_of_hough_radius():
    area = math.pi * 40.0 * 40.0
    present = circle_white_fraction(_inductor("left"), [60.0, 60.0], area)
    missing = circle_white_fraction(
        np.full((120, 120, 3), 35, dtype=np.uint8), [60.0, 60.0], area
    )
    assert present > 0.5
    assert missing < 0.1


def _mock_component(slot, raw_delta):
    return {
        "slot_id": slot,
        "component_type": "Power Module",
        "center_delta_mm": list(raw_delta),
        "checks": [
            {
                "name": "presence", "status": "PASS", "reason": "present",
                "measured": {}, "limit": {},
            },
            {
                "name": "position", "status": "FAIL", "reason": "raw",
                "measured": {},
                "limit": {"x_mm": 0.75, "y_mm": 0.75},
            },
            {
                "name": "orientation_axis", "status": "PASS", "reason": "axis",
                "measured": {}, "limit": {},
            },
        ],
        "secondary_required": [],
        "s22_visible_status": "FAIL",
        "final_status": "FAIL",
    }


def test_common_oblique_projection_bias_is_removed_before_cad_limit():
    components = [
        _mock_component("p1", (0.5, 0.9)),
        _mock_component("p2", (0.6, 1.0)),
        _mock_component("p3", (0.4, 0.8)),
    ]
    config = {
        "measurement_uncertainty": {"common_projection_bias_max_mm": 1.5}
    }
    biases = apply_projection_and_visibility_policy(components, config)
    assert np.allclose(biases["Power Module"], [0.5, 0.9])
    assert all(item["s22_visible_status"] == "PASS" for item in components)
