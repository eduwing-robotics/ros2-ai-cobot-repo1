import numpy as np
import pytest

import opencv_inspectors as inspector


def components():
    # True dot plus small same-x fragments; three surviving opposite pins.
    return [
        {"x": 40., "y": 177., "area": 310., "circularity": .90},
        *[{"x": 39., "y": y, "area": 20., "circularity": .8}
          for y in (40., 100., 220.)],
        *[{"x": 131., "y": y, "area": 120., "circularity": .86}
          for y in (153., 172., 191.)],
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_large_dot_survives_fragments_and_remaining_pins(monkeypatch, reverse):
    blobs = components()
    if reverse:
        blobs = [dict(c, x=170-c["x"], y=240-c["y"]) for c in blobs]
    monkeypatch.setattr(inspector, "_white_components", lambda image: (None, blobs))
    result = inspector.check_gpu_hbm_dot(np.zeros((240, 170, 3), np.uint8),
                                         suppress_pin_columns=True)
    assert result.status == ("FAIL" if reverse else "PASS")
    assert result.measured["winner"] == ("upper_right" if reverse else "lower_left")
    assert result.authority == "ADVISORY_ONLY"


def test_remaining_pin_column_without_dot_abstains(monkeypatch):
    monkeypatch.setattr(inspector, "_white_components", lambda image: (None, components()[4:]))
    result = inspector.check_gpu_hbm_dot(np.zeros((240, 170, 3), np.uint8),
                                         suppress_pin_columns=True)
    assert result.status == "UNKNOWN"


@pytest.mark.parametrize("reverse", [False, True])
def test_size_position_disagreement_abstains_symmetrically(monkeypatch, reverse):
    blobs = [
        {"x":33.,"y":43.,"area":180.5,"circularity":.84},
        {"x":52.,"y":176.,"area":195.5,"circularity":.88},
    ]
    if reverse:
        blobs = [dict(c,x=170-c["x"],y=240-c["y"]) for c in blobs]
    monkeypatch.setattr(inspector,"_white_components",lambda image:(None,blobs))
    r=inspector.check_gpu_hbm_dot(np.zeros((240,170,3),np.uint8),suppress_pin_columns=True)
    assert r.status == "UNKNOWN"
    assert r.reason == "WHITE_DOT_SIZE_POSITION_CONFLICT"
    assert r.measured["recapture_recommended"] is True


def test_conflict_cannot_promote_expected_corner(monkeypatch):
    blobs=[{"x":31.,"y":197.,"area":180.,"circularity":.84},
           {"x":118.,"y":64.,"area":195.,"circularity":.88}]
    monkeypatch.setattr(inspector,"_white_components",lambda image:(None,blobs))
    r=inspector.check_gpu_hbm_dot(np.zeros((240,170,3),np.uint8),suppress_pin_columns=True)
    assert r.measured["winner"] == "lower_left"
    assert r.status == "UNKNOWN"

@pytest.mark.parametrize('reverse', [False, True])
def test_large_end_pin_and_round_dot_conflict_abstains(monkeypatch, reverse):
    blobs = [
        dict(x=146.27, y=44.95, area=270., circularity=.56554),
        dict(x=58.66, y=175.52, area=229.5, circularity=.89171),
    ]
    if reverse:
        blobs = [dict(c, x=170-c['x'], y=240-c['y']) for c in blobs]
    monkeypatch.setattr(inspector, '_white_components', lambda image: (None, blobs))
    result = inspector.check_gpu_hbm_dot(
        np.zeros((240, 170, 3), np.uint8), suppress_pin_columns=True)
    assert result.status == 'UNKNOWN'
    assert result.reason == 'WHITE_DOT_SHAPE_POSITION_CONFLICT'
    assert result.measured['recapture_recommended']
