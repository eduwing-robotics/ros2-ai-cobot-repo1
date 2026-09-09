import numpy as np
import pytest

from audit_hbm_pin_columns import locate_columns


def test_columns_preserve_original_coordinates_and_input():
    rgb = np.zeros((240, 170, 3), np.uint8)
    for x in (45, 130):
        for y in range(30, 160, 18):
            rgb[y:y+4, x:x+3] = 220
    before = rgb.copy()
    result = locate_columns(rgb)
    assert np.array_equal(rgb, before)
    assert result['left']['fit']['x_intercept'] == pytest.approx(46)
    assert result['right']['fit']['x_intercept'] == pytest.approx(131)
    assert all(s['status'] == 'UNKNOWN' for s in result.values())


def test_logo_dot_and_insufficient_anchors_abstain():
    rgb = np.zeros((240, 170, 3), np.uint8)
    rgb[95:110, 60:110] = 240
    rgb[185:200, 32:47] = 240
    for y in (35, 65, 95):
        rgb[y:y+4, 130:133] = 230
    assert all(s['fit'] is None for s in locate_columns(rgb).values())


def test_dark_crop_not_normal():
    assert all(s['status'] == 'UNKNOWN' and s['fit'] is None
               for s in locate_columns(np.zeros((240,170,3), np.uint8)).values())


def test_bad_input():
    with pytest.raises(ValueError):
        locate_columns(np.zeros((240,170,3), float))
