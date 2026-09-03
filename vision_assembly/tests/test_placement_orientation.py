#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from placement_orientation import (  # noqa: E402
    plan_carried_part_orientation,
    slot_axis_base_angle_deg,
)


BOARD_ROTATION = np.array(
    [
        [-0.9997149134, 0.0057151063, 0.0231825258],
        [0.0062933407, 0.9996689682, 0.0249469011],
        [-0.0230322775, 0.0250856846, -0.9994199431],
    ]
)


class PlacementOrientationTest(unittest.TestCase):
    def test_board_axis_transform(self):
        self.assertAlmostEqual(slot_axis_base_angle_deg(BOARD_ROTATION, 0.0), 179.6393, places=3)
        self.assertAlmostEqual(slot_axis_base_angle_deg(BOARD_ROTATION, 90.0), 89.6724, places=3)

    def test_pm01_uses_confirmed_c180_tie_break(self):
        target_axis = slot_axis_base_angle_deg(BOARD_ROTATION, 90.0)
        plan = plan_carried_part_orientation(
            [-179.996, 0.005, 88.189], target_axis, "tool_y", 180.0,
            preferred_tcp_c_deg=180.0,
        )
        self.assertAlmostEqual(plan["rotation_delta_deg"], 91.4834, places=2)
        self.assertAlmostEqual(abs(plan["target_tcp_abc_deg"][2]), 179.6724, places=2)

    def test_hbm_avoids_unnecessary_quarter_turn(self):
        target_axis = slot_axis_base_angle_deg(BOARD_ROTATION, 90.0)
        plan = plan_carried_part_orientation(
            [-180.0, 0.0, 92.007], target_axis, "tool_y", 90.0
        )
        self.assertLess(abs(plan["rotation_delta_deg"]), 3.0)
        self.assertAlmostEqual(plan["rotation_delta_deg"], -2.3346, places=2)

    def test_inductor_preserves_matching_pick_axis(self):
        target_axis = slot_axis_base_angle_deg(BOARD_ROTATION, -90.0)
        plan = plan_carried_part_orientation(
            [-180.0, 0.0, 0.583], target_axis, "tool_y", 180.0
        )
        self.assertLess(abs(plan["rotation_delta_deg"]), 1.0)

    def test_vrm_rotates_when_axis_really_differs(self):
        target_axis = slot_axis_base_angle_deg(BOARD_ROTATION, 90.0)
        plan = plan_carried_part_orientation(
            [-180.0, 0.0, 92.0], target_axis, "tool_y", 180.0
        )
        self.assertGreater(abs(plan["rotation_delta_deg"]), 85.0)


if __name__ == "__main__":
    unittest.main()
