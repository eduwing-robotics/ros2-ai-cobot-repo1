import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "calibration"
    / "scripts"
    / "move_object_approach.py"
)
SPEC = importlib.util.spec_from_file_location("move_object_approach", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("shortest", 87.0),
        ("positive", 87.0),
        ("negative", -93.0),
    ],
)
def test_symmetric_rotation_branch_from_close_view(branch, expected):
    assert MODULE.symmetric_angle_delta_deg(177.0, 90.0, branch) == pytest.approx(
        expected
    )


def test_negative_branch_flips_already_aligned_axis():
    assert MODULE.symmetric_angle_delta_deg(177.0, 177.0, "negative") == pytest.approx(
        -180.0
    )
