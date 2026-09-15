from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from smd_terminal_axis import terminal_axis_from_bgr, terminal_axis_from_obb, unwrap_axis_angles_deg


def axis_error(first: float, second: float) -> float:
    return abs((float(first) - float(second) + 90.0) % 180.0 - 90.0)


def synthetic_smd(angle_deg: float, *, square_body: bool = False) -> np.ndarray:
    image = np.full((180, 180, 3), (135, 145, 145), dtype=np.uint8)
    center = np.array([90.0, 90.0])
    angle = math.radians(angle_deg)
    along = np.array([math.cos(angle), math.sin(angle)])
    across = np.array([-along[1], along[0]])
    body_half_length = 22.0 if not square_body else 17.0
    body_half_width = 14.0 if not square_body else 17.0

    def polygon(long_low: float, long_high: float, half_width: float) -> np.ndarray:
        return np.rint(
            [
                center + along * long_low - across * half_width,
                center + along * long_high - across * half_width,
                center + along * long_high + across * half_width,
                center + along * long_low + across * half_width,
            ]
        ).astype(np.int32)

    cv2.fillConvexPoly(image, polygon(-body_half_length, body_half_length, body_half_width), (75, 105, 145))
    cv2.fillConvexPoly(image, polygon(-33.0, -body_half_length, 13.0), (175, 175, 175))
    cv2.fillConvexPoly(image, polygon(body_half_length, 33.0, 13.0), (175, 175, 175))
    return cv2.GaussianBlur(image, (5, 5), 0.8)


@pytest.mark.parametrize("angle", [-18.0, -7.0, 0.0, 11.0, 23.0])
def test_terminal_axis_tracks_physical_white_end_direction(angle: float) -> None:
    result = terminal_axis_from_bgr(synthetic_smd(angle), [90.0, 90.0])
    assert axis_error(result["angle_canonical_deg"], angle) < 2.0
    assert result["axis_ratio"] > 1.15
    assert len(result["terminal_saturation_medians"]) == 2


def test_terminal_axis_rejects_square_colour_body() -> None:
    with pytest.raises(ValueError, match="too square"):
        terminal_axis_from_bgr(synthetic_smd(7.0, square_body=True), [90.0, 90.0])


@pytest.mark.parametrize("angle", [-89.0, -52.0, 0.0, 37.0, 88.0])
def test_terminal_axis_from_obb_uses_long_side(angle: float) -> None:
    points = cv2.boxPoints(((90.0, 90.0), (64.0, 32.0), angle)).astype(np.float32)
    result = terminal_axis_from_obb(points)
    assert axis_error(result["angle_canonical_deg"], angle) < 0.01
    assert result["axis_ratio"] == pytest.approx(2.0, abs=0.01)
    endpoints = np.asarray(result["endpoints_canonical_pixel"])
    assert np.linalg.norm(endpoints[1] - endpoints[0]) == pytest.approx(64.0, abs=0.1)


def test_terminal_axis_from_obb_rejects_near_square_box() -> None:
    points = cv2.boxPoints(((90.0, 90.0), (35.0, 32.0), 20.0)).astype(np.float32)
    with pytest.raises(ValueError, match="too square"):
        terminal_axis_from_obb(points)


def test_axis_unwrap_treats_plus_and_minus_89_as_same_axis() -> None:
    values = [-89.4, 89.1, -88.7, 89.8]
    unwrapped = unwrap_axis_angles_deg(values)
    assert float(np.ptp(unwrapped)) < 3.0
    assert axis_error(float(np.median(unwrapped)), 90.0) < 2.0

from smd_terminal_axis import terminal_axis_from_source_obb

@pytest.mark.parametrize('angle',[-89.,-52.,0.,37.,88.])
@pytest.mark.parametrize('scales',[(3.2,1.8),(.5,2.5)])
def test_source_axis_invariant_to_nonuniform_section_stretch(angle,scales):
    source=cv2.boxPoints(((120.,90.),(64.,28.),angle)).astype(np.float32)
    H=np.array([[scales[0],.1,30.],[0.,scales[1],20.],[0.,0.,1.]])
    canonical=cv2.perspectiveTransform(source.reshape(-1,1,2),H)[:,0]
    result=terminal_axis_from_source_obb(canonical,np.linalg.inv(H))
    assert result['axis_ratio']==pytest.approx(64/28,abs=.001)
    assert axis_error(result['angle_source_image_deg'],angle)<.001
    back=cv2.perspectiveTransform(np.float32(result['endpoints_canonical_pixel']).reshape(-1,1,2),np.linalg.inv(H))[:,0]
    assert back==pytest.approx(np.array(result['endpoints_source_pixel']),abs=.001)


def test_source_square_is_rejected_even_when_display_stretch_looks_elongated():
    source=cv2.boxPoints(((50.,50.),(32.,32.),0.)).astype(np.float32)
    H=np.diag([3.,1.,1.]);canonical=cv2.perspectiveTransform(source.reshape(-1,1,2),H)[:,0]
    assert terminal_axis_from_obb(canonical)['axis_ratio']>2
    with pytest.raises(ValueError,match='too square'):
        terminal_axis_from_source_obb(canonical,np.linalg.inv(H))


@pytest.mark.parametrize('H',[np.zeros((3,3)),np.full((3,3),np.nan),np.eye(2)])
def test_source_geometry_rejects_invalid_homography(H):
    with pytest.raises(ValueError):terminal_axis_from_source_obb(np.array([[0,0],[10,0],[10,20],[0,20]]),H)
