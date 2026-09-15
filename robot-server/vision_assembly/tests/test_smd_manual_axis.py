import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from smd_manual_axis import (
    canonical_axis_angle_deg,
    directed_axis_angle_deg,
    load_manual_axes,
    resolve_manual_axis,
)


def payload():
    return {
        "schema_version": 1,
        "mode": "operator_two_terminal_axes",
        "timestamp_unix": time.time(),
        "set_index": 1,
        "canonical_size": [1200, 720],
        "parts": [
            {
                "instance_index": index,
                "detection_center_canonical_pixel": [100.0 * index, 100.0],
                "terminal_endpoints_canonical_pixel": [
                    [100.0 * index - 20.0, 90.0],
                    [100.0 * index + 20.0, 110.0],
                ],
                "directed_axis_canonical_deg": 26.5651,
            }
            for index in range(1, 6)
        ],
    }


def test_axis_angle_preserves_direction_and_canonicalizes_line():
    assert directed_axis_angle_deg(np.array([0, 0]), np.array([10, 10])) == pytest.approx(45.0)
    assert directed_axis_angle_deg(np.array([10, 10]), np.array([0, 0])) == pytest.approx(-135.0)
    assert canonical_axis_angle_deg(-135.0) == pytest.approx(45.0)
    assert canonical_axis_angle_deg(120.0) == pytest.approx(-60.0)


def test_manual_axis_load_and_center_translation(tmp_path):
    path = tmp_path / "axes.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    loaded = load_manual_axes(
        path, set_index=1, canonical_size=(1200, 720), required_count=5, max_age_sec=60
    )
    resolved = resolve_manual_axis(
        loaded, 2, np.array([202.0, 97.0]), center_tolerance_px=5.0
    )
    assert resolved["angle_canonical_deg"] == pytest.approx(26.5651, abs=1e-3)
    np.testing.assert_allclose(
        resolved["endpoints_canonical_pixel"], [[182.0, 87.0], [222.0, 107.0]]
    )


def test_manual_axis_rejects_moved_part(tmp_path):
    path = tmp_path / "axes.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    loaded = load_manual_axes(
        path, set_index=1, canonical_size=(1200, 720), required_count=5, max_age_sec=60
    )
    with pytest.raises(ValueError, match="relabel required"):
        resolve_manual_axis(loaded, 1, np.array([120.0, 100.0]), center_tolerance_px=5.0)
