#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from full_cycle_motion import (  # noqa: E402
    CANONICAL_WAYPOINT_COUNT,
    MotionPlanError,
    PRESERVE_PICK_TCP_ORIENTATION,
    build_canonical_slot_waypoints,
    validate_j6_operational_envelope,
    validate_joint_path,
)


class FullCycleMotionTest(unittest.TestCase):
    def setUp(self):
        self.start = [-554.549, -69.469, 188.46, -180.0, 0.0, -90.167]
        self.pick = [-518.238, -197.904, -48.637, -180.0, 0.0, 89.828]
        self.place = [36.338, -512.544, 88.461, 180.0, 0.0, -179.247]

    def test_canonical_slot_has_fourteen_waypoints_and_50mm_slow_zones(self):
        waypoints = build_canonical_slot_waypoints(
            self.start,
            self.pick,
            self.place,
            350.0,
            part_type="gpu",
            orientation_policy_mode="align_actual_carried_axis_to_current_slot_axis",
        )

        self.assertEqual(len(waypoints), CANONICAL_WAYPOINT_COUNT)
        self.assertEqual(
            [waypoint.label for waypoint in waypoints],
            [
                "pre_pick_safe_vertical",
                "pick_combined_xy_abc",
                "pick_hover_100mm_vertical",
                "pick_approach_50mm_vertical",
                "pick_final_50mm_vertical",
                "post_grasp_lift_50mm_vertical",
                "post_grasp_proof_lift_100mm_vertical",
                "carry_safe_vertical",
                "place_combined_xy_abc",
                "place_hover_100mm_vertical",
                "place_approach_50mm_vertical",
                "place_final_50mm_vertical",
                "post_release_lift_50mm_vertical",
                "post_release_lift_100mm_vertical",
            ],
        )
        self.assertFalse(
            any("rotate" in waypoint.label.lower() for waypoint in waypoints)
        )
        self.assertEqual(waypoints[1].tcp[:2], tuple(self.pick[:2]))
        self.assertEqual(waypoints[1].tcp[3:], tuple(self.pick[3:]))
        self.assertEqual(
            [waypoints[index].tcp[2] for index in (2, 3, 4, 5, 6)],
            [
                self.pick[2] + 100.0,
                self.pick[2] + 50.0,
                self.pick[2],
                self.pick[2] + 50.0,
                self.pick[2] + 100.0,
            ],
        )
        self.assertEqual(waypoints[8].tcp[:2], tuple(self.place[:2]))
        self.assertEqual(waypoints[8].tcp[3:], tuple(self.place[3:]))
        self.assertEqual(
            [waypoints[index].tcp[2] for index in (9, 10, 11, 12, 13)],
            [
                self.place[2] + 100.0,
                self.place[2] + 50.0,
                self.place[2],
                self.place[2] + 50.0,
                self.place[2] + 100.0,
            ],
        )

    def test_hbm_align_policy_carries_planned_rotation_at_safe_z(self):
        hbm_pick = [-560.0, -20.0, -50.0, -180.0, 0.0, 91.948]
        hbm_place = [60.0, -490.0, 88.0, -180.0, 0.0, -179.247]
        waypoints = build_canonical_slot_waypoints(
            self.start,
            hbm_pick,
            hbm_place,
            350.0,
            part_type="hbm",
            orientation_policy_mode="align_actual_carried_axis_to_current_slot_axis",
        )

        self.assertEqual(waypoints[1].tcp[3:], tuple(hbm_pick[3:]))
        self.assertEqual(waypoints[8].label, "place_combined_xy_abc")
        self.assertEqual(waypoints[8].tcp[3:], tuple(hbm_place[3:]))
        self.assertNotEqual(waypoints[1].tcp[3:], waypoints[8].tcp[3:])

    def test_j6_minus_188_is_rejected(self):
        with self.assertRaisesRegex(MotionPlanError, "outside operational envelope"):
            validate_j6_operational_envelope([-188.049])

    def test_known_safe_j6_values_are_accepted(self):
        self.assertEqual(
            validate_j6_operational_envelope([-8.646, 177.770]),
            (-8.646, 177.770),
        )

    def test_177_point_544_degree_joint_step_is_rejected(self):
        with self.assertRaisesRegex(MotionPlanError, "177.544 deg"):
            validate_joint_path(
                [[0.0, 0.0, 0.0, 0.0, 0.0, 177.544]],
                initial_joints_deg=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            )


if __name__ == "__main__":
    unittest.main()


def test_controller_tcp_normalizes_unwrapped_angles_without_changing_rotation():
    import pytest
    from scipy.spatial.transform import Rotation
    from full_cycle_motion import normalize_controller_tcp
    import numpy as np
    pose=[-151.369,-319.741,350,179.999,0.001,-209.999858]
    normalized=normalize_controller_tcp(pose)
    assert normalized[:3]==tuple(pose[:3])
    assert normalized[5]==pytest.approx(150.000142)
    assert np.allclose(Rotation.from_euler('xyz',pose[3:],degrees=True).as_matrix(),
                       Rotation.from_euler('xyz',normalized[3:],degrees=True).as_matrix())
    assert normalize_controller_tcp([0,0,0,180,0,-180])==(0,0,0,180,0,-180)
