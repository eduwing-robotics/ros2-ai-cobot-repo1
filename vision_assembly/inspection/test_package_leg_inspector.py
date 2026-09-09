from pathlib import Path
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from package_leg_inspector import (  # noqa: E402
    inspect_side,
    reference_peaks,
    slot_geometry,
)


TYPE_SETTINGS = {
    "minimum_reference_peaks": 8,
    "minimum_local_match": 0.5,
    "maximum_reference_peaks": 9,
    "peak_min_distance_px": 9,
    "peak_profile_min": 0.025,
    "left_keep_fraction": 0.90,
    "reference_peak_radius_px": 2,
    "sample_peak_radius_px": 4,
    "missing_peak_ratio": 0.34,
    "weak_peak_ratio": 0.60,
    "maximum_weak_pass": 2,
    "pass_profile_correlation": 0.68,
    "pass_profile_deficit": 0.32,
    "fail_missing_count": 1,
}
WHITE_SETTINGS = {
    "lab_l_min": 110,
    "hsv_s_max": 160,
    "open_kernel_px": 2,
    "profile_sigma_px": 1.2,
}


def synthetic_row(missing=None):
    image = np.zeros((180, 44, 3), dtype=np.uint8)
    for index, center_y in enumerate(range(12, 174, 18), start=1):
        if index == missing:
            continue
        cv2.ellipse(image, (22, center_y), (5, 4), 0, 0, 360,
                    (225, 225, 225), -1, cv2.LINE_AA)
    return image


def test_reference_peaks_finds_periodic_white_legs():
    profile = np.zeros(180, dtype=np.float32)
    for center_y in range(12, 174, 18):
        profile[center_y] = 0.5
    profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 7), 1.2).ravel()
    assert len(reference_peaks(profile, "right", TYPE_SETTINGS)) == 9


def test_inspect_side_passes_matching_row():
    row = synthetic_row()
    result = inspect_side(
        row, row.copy(), "right", (100, 200, 144, 380),
        TYPE_SETTINGS, WHITE_SETTINGS, 0.99,
    )
    assert result.status == "PASS"
    assert not result.missing_indices


def test_inspect_side_fails_one_missing_leg():
    reference = synthetic_row()
    sample = synthetic_row(missing=5)
    result = inspect_side(
        reference, sample, "right", (100, 200, 144, 380),
        TYPE_SETTINGS, WHITE_SETTINGS, 0.99,
    )
    assert result.status == "FAIL"
    assert result.missing_indices


def test_deformed_but_nonmissing_row_requests_recheck():
    reference = synthetic_row()
    sample = np.zeros_like(reference)
    cv2.rectangle(sample, (18, 4), (26, 176), (225, 225, 225), -1)
    result = inspect_side(
        reference, sample, "right", (100, 200, 144, 380),
        TYPE_SETTINGS, WHITE_SETTINGS, 0.99,
    )
    assert result.status == "RECHECK"
    assert result.reason == "LEG_PATTERN_UNCERTAIN"


def test_hidden_reference_side_requests_recheck():
    blank = np.zeros((180, 44, 3), dtype=np.uint8)
    result = inspect_side(
        blank, blank.copy(), "left", (100, 200, 144, 380),
        TYPE_SETTINGS, WHITE_SETTINGS, 0.99,
    )
    assert result.status == "RECHECK"
    assert result.reason == "REFERENCE_SIDE_NOT_VISIBLE"


def test_slot_geometry_uses_board_metric_frame():
    placement = {
        "center_board_mm": {"x": 0.0, "y": 0.0},
        "nominal_size_mm": {"x": 27.8, "y": 22.0},
    }
    assert slot_geometry(placement, (1100, 1390, 3), (139.0, 110.0)) == (
        695.0, 550.0, 278.0, 220.0
    )
